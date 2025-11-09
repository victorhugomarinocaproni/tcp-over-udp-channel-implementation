"""
Selective Repeat (SR): Protocolo com ACKs individuais e bufferização
Características:
- Janela de envio e recepção de tamanho N
- ACKs individuais para cada pacote
- Retransmissão seletiva apenas dos pacotes perdidos
- Receptor bufferiza pacotes fora de ordem
"""
import socket
import threading
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.packet import RDTPacket, PacketType
from utils.simulator import UnreliableChannel
from utils.logger import ProtocolLogger


class SRSender:
    """Remetente Selective Repeat com timers individuais"""
    
    def __init__(self, port, window_size = 5, channel = None, timeout = 1.0):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.window_size = window_size
        self.channel = channel
        self.timeout_value = timeout
        
        self.logger = ProtocolLogger(f'SR-Sender-{port}')
        
        # Variáveis de controle
        self.base = 0
        self.next_seq_num = 0
        
        # Buffer: {seq_num: (packet, timer, acked, send_time)}
        self.send_buffer = {}
        self.lock = threading.Lock()
        
        # Thread para receber ACKs
        self.running = False
        self.ack_thread = None
        self.peer_address = None
        
        # Estatísticas
        self.packets_sent = 0
        self.retransmissions = 0
        self.timeouts = 0
        self.acks_received = 0
        self.start_time = None
        self.total_bytes_sent = 0
    
    def start(self, dest_address):
        """Inicia o remetente SR"""
        self.peer_address = dest_address
        self.running = True
        self.start_time = time.time()
        
        self.ack_thread = threading.Thread(target = self._ack_receive_loop)
        self.ack_thread.daemon = True
        self.ack_thread.start()
        
        self.logger.info(f"Remetente SR iniciado (janela={self.window_size})")
    
    def send(self, data):
        """Envia dados usando protocolo SR"""
        if isinstance(data, str):
            data = data.encode()
        
        self.total_bytes_sent += len(data)
        
        # Aguardar se a janela estiver cheia
        while self.next_seq_num >= self.base + self.window_size:
            time.sleep(0.01)
        
        # Criar pacote
        packet = RDTPacket(PacketType.DATA, seq_num = self.next_seq_num, data = data)
        
        with self.lock:
            # Adicionar ao buffer
            self.send_buffer[self.next_seq_num] = {
                'packet': packet,
                'timer': None,
                'acked': False,
                'send_time': time.time()
            }
            
            # Enviar pacote e iniciar timer individual
            self._send_packet(packet)
            self.packets_sent += 1
            self._start_timer(self.next_seq_num)
            
            self.logger.send(f"{packet} - Dados: {data[:20]}")
            self.next_seq_num += 1
    
    def _send_packet(self, packet):
        """Envia pacote através do canal"""
        packet_bytes = packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, self.peer_address)
        else:
            self.socket.sendto(packet_bytes, self.peer_address)
    
    def _start_timer(self, seq_num):
        """Inicia timer individual para um pacote"""
        if seq_num in self.send_buffer:
            if self.send_buffer[seq_num]['timer']:
                self.send_buffer[seq_num]['timer'].cancel()
            
            timer = threading.Timer(
                self.timeout_value,
                self._on_timeout,
                args=(seq_num,)
            )
            timer.daemon = True
            timer.start()
            self.send_buffer[seq_num]['timer'] = timer
    
    def _on_timeout(self, seq_num):
        """
        Callback quando timer de um pacote expira
        Retransmite APENAS esse pacote
        """
        with self.lock:
            if seq_num in self.send_buffer and not self.send_buffer[seq_num]['acked']:
                packet = self.send_buffer[seq_num]['packet']
                
                self.logger.timeout(f"Seq{seq_num} - Retransmitindo seletivamente")
                self.timeouts += 1
                self.retransmissions += 1
                
                # Retransmitir apenas este pacote
                self._send_packet(packet)
                
                # Reiniciar timer
                self._start_timer(seq_num)
    
    def _ack_receive_loop(self):
        """Thread que recebe ACKs individuais"""
        self.socket.settimeout(0.1)
        
        while self.running:
            try:
                packet_bytes, _ = self.socket.recvfrom(1024)
                ack_packet = RDTPacket.deserialize(packet_bytes)
                
                if ack_packet is None or ack_packet.is_corrupt():
                    continue
                
                if ack_packet.type == PacketType.ACK:
                    self._handle_ack(ack_packet)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro recebendo ACK: {e}")
    
    def _handle_ack(self, ack_packet):
        """
        Processa ACK individual
        
        Args:
            ack_packet: Pacote ACK recebido
        """
        ack_num = ack_packet.seq_num
        
        with self.lock:
            # ACK individual
            if ack_num in self.send_buffer and not self.send_buffer[ack_num]['acked']:
                self.logger.receive(f"{ack_packet} - ACK individual")
                self.acks_received += 1
                
                # Marcar como confirmado
                self.send_buffer[ack_num]['acked'] = True
                
                # Cancelar timer
                if self.send_buffer[ack_num]['timer']:
                    self.send_buffer[ack_num]['timer'].cancel()
                
                # Se for o base, avançar janela
                if ack_num == self.base:
                    # Avançar base até o próximo pacote não confirmado
                    while self.base in self.send_buffer and self.send_buffer[self.base]['acked']:
                        del self.send_buffer[self.base]
                        self.base += 1
                    
                    self.logger.info(f"Janela avançada para base={self.base}")
    
    def wait_for_completion(self, timeout=10.0):
        """Aguarda todos os pacotes serem confirmados"""
        start = time.time()
        while self.base < self.next_seq_num:
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)
        return True
    
    def get_statistics(self):
        """Retorna estatísticas"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        throughput = (self.total_bytes_sent / elapsed) if elapsed > 0 else 0
        
        return {
            'packets_sent': self.packets_sent,
            'retransmissions': self.retransmissions,
            'timeouts': self.timeouts,
            'acks_received': self.acks_received,
            'window_size': self.window_size,
            'retransmission_rate': self.retransmissions / self.packets_sent if self.packets_sent > 0 else 0,
            'total_bytes': self.total_bytes_sent,
            'elapsed_time': elapsed,
            'throughput_bps': throughput,
            'utilization': (self.packets_sent / (self.packets_sent + self.retransmissions)) if (self.packets_sent + self.retransmissions) > 0 else 0
        }
    
    def stop(self):
        """Para o remetente"""
        self.running = False
        
        with self.lock:
            # Cancelar todos os timers
            for seq_num in self.send_buffer:
                if self.send_buffer[seq_num]['timer']:
                    self.send_buffer[seq_num]['timer'].cancel()
        
        if self.ack_thread:
            self.ack_thread.join(timeout=1.0)
        self.socket.close()


class SRReceiver:
    """Receptor Selective Repeat com buffer para pacotes fora de ordem"""
    
    def __init__(self, port, window_size=5, channel=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.window_size = window_size
        self.channel = channel
        
        self.logger = ProtocolLogger(f'SR-Receiver-{port}')
        
        # Base da janela de recepção
        self.rcv_base = 0
        
        # Buffer para pacotes fora de ordem: {seq_num: data}
        self.receive_buffer = {}
        
        # Mensagens entregues em ordem
        self.delivered_messages = []
        
        # Estatísticas
        self.packets_received = 0
        self.buffered_packets = 0
        self.out_of_window_packets = 0
        self.corrupted_packets = 0
        self.acks_sent = 0
        
        # Thread
        self.running = False
        self.receive_thread = None
    
    def start(self):
        """Inicia o receptor"""
        self.running = True
        self.receive_thread = threading.Thread(target = self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        self.logger.info(f"Receptor SR iniciado (janela={self.window_size})")
    
    def _receive_loop(self):
        """Loop principal de recepção"""
        while self.running:
            try:
                packet_bytes, sender_addr = self.socket.recvfrom(2048)
                self.packets_received += 1
                
                packet = RDTPacket.deserialize(packet_bytes)
                
                if packet is None:
                    continue
                
                self.logger.receive(f"{packet}")

                if packet.is_corrupt():
                    self.logger.corrupt(f"{packet}")
                    self.corrupted_packets += 1
                    continue
                
                seq_num = packet.seq_num

                # Verificar se está dentro da janela
                if self.rcv_base <= seq_num < self.rcv_base + self.window_size:
                    # Dentro da janela - enviar ACK individual
                    self._send_ack(sender_addr, seq_num)
                    
                    if seq_num == self.rcv_base:
                        # Pacote esperado - entregar
                        self.logger.deliver(f"Seq{seq_num} - Dados: {packet.data[:30]}")
                        self.delivered_messages.append(packet.data)
                        self.rcv_base += 1
                        
                        # Entregar pacotes bufferizados consecutivos
                        while self.rcv_base in self.receive_buffer:
                            data = self.receive_buffer.pop(self.rcv_base)
                            self.logger.deliver(f"Seq{self.rcv_base} - Do buffer")
                            self.delivered_messages.append(data)
                            self.rcv_base += 1
                        
                        self.logger.info(f"Janela avançada para rcv_base={self.rcv_base}")
                    
                    elif seq_num > self.rcv_base:
                        # Pacote fora de ordem mas dentro da janela - bufferizar
                        if seq_num not in self.receive_buffer:
                            self.logger.warning(f"Seq{seq_num} - Bufferizando (fora de ordem)")
                            self.receive_buffer[seq_num] = packet.data
                            self.buffered_packets += 1
                
                elif seq_num < self.rcv_base:
                    # Pacote já recebido - reenviar ACK
                    self.logger.warning(f"Seq{seq_num} - Já recebido, reenviando ACK")
                    self._send_ack(sender_addr, seq_num)
                
                else:
                    # Fora da janela
                    self.out_of_window_packets += 1
                    self.logger.warning(f"Seq{seq_num} - Fora da janela!")
                    
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro: {e}")
    
    def _send_ack(self, dest_addr, seq_num):
        """Envia ACK individual para um pacote específico"""
        ack_packet = RDTPacket(PacketType.ACK, seq_num = seq_num)
        self.logger.send(f"{ack_packet} - ACK individual")
        
        packet_bytes = ack_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.acks_sent += 1
    
    def get_messages(self):
        """Retorna mensagens entregues em ordem"""
        return self.delivered_messages
    
    def get_statistics(self):
        """Retorna estatísticas"""
        return {
            'packets_received': self.packets_received,
            'buffered_packets': self.buffered_packets,
            'out_of_window_packets': self.out_of_window_packets,
            'corrupted_packets': self.corrupted_packets,
            'acks_sent': self.acks_sent,
            'messages_delivered': len(self.delivered_messages),
            'buffer_size_current': len(self.receive_buffer)
        }
    
    def stop(self):
        """Para o receptor"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.socket.close()


# Exemplo de uso
if __name__ == "__main__":
    print("=" * 70)
    print("Teste do Protocolo Selective Repeat (SR)")
    print("=" * 70)
    
    # Canal com perda
    channel = UnreliableChannel(
        loss_rate=0.15,
        corrupt_rate=0.05,
        delay_range=(0.01, 0.15)
    )
    
    # Criar receptor e remetente
    receiver = SRReceiver(8001, window_size = 8, channel = channel)
    receiver.start()
    
    sender = SRSender(8000, window_size = 8, channel = channel, timeout = 1.0)
    sender.start(('localhost', 8001))
    
    # Enviar dados
    print(f"\nEnviando 50 mensagens com janela={sender.window_size}...")
    print("Canal: 15% perda, 5% corrupção\n")
    
    messages = [f"Pacote {i:03d}" for i in range(50)]
    
    for msg in messages:
        sender.send(msg)
        time.sleep(0.01)
    
    # Aguardar conclusão
    print("Aguardando confirmação...")
    success = sender.wait_for_completion(timeout = 15.0)
    
    time.sleep(1)
    
    # Resultados
    print("\n" + "=" * 70)
    print("RESULTADOS")
    print("=" * 70)
    
    print("\nRemetente:")
    stats_sender = sender.get_statistics()
    for key, value in stats_sender.items():
        if 'rate' in key or 'utilization' in key:
            print(f"  {key}: {value:.2%}")
        elif 'time' in key:
            print(f"  {key}: {value:.2f}s")
        elif 'throughput' in key:
            print(f"  {key}: {value:.2f} bytes/s")
        else:
            print(f"  {key}: {value}")
    
    print("\nReceptor:")
    stats_receiver = receiver.get_statistics()
    for key, value in stats_receiver.items():
        print(f"  {key}: {value}")
    
    received = receiver.get_messages()
    
    print(f"\n✓ Mensagens recebidas: {len(received)}/{len(messages)}")
    
    if len(received) == len(messages):
        print("✓ SUCESSO: Todas as mensagens entregues em ordem!")
    
    # Estatísticas do canal
    channel.print_statistics()
    
    # Limpar
    sender.stop()
    receiver.stop()
