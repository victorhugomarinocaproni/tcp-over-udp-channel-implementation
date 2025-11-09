"""
rdt3.0: Adiciona timer para lidar com perda de pacotes
Características:
- Timer para detectar perda de pacotes ou ACKs
- Retransmissão automática em caso de timeout
- Protocolo completo: lida com corrupção, perda e duplicação
"""
import socket
import threading
import time
import sys
sys.path.append('../..')

from utils.packet import RDTPacket, PacketType
from utils.simulator import UnreliableChannel
from utils.logger import ProtocolLogger


class RDT30Sender:
    """Remetente do protocolo rdt3.0 com timer"""
    
    def __init__(self, port, channel=None, timeout=2.0):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        self.timeout_value = timeout
        
        self.logger = ProtocolLogger(f'RDT3.0-Sender-{port}')
        
        # Estado e número de sequência
        self.seq_num = 0
        self.peer_address = None
        
        # Timer
        self.timer = None
        self.timer_running = False
        self.lock = threading.Lock()
        
        # Estatísticas
        self.packets_sent = 0
        self.retransmissions = 0
        self.timeouts = 0
        self.acks_received = 0
        self.start_time = None
        self.total_bytes_sent = 0
    
    def send(self, data, dest_address):
        """
        Envia dados usando protocolo rdt3.0 com timer
        
        Args:
            data: Bytes ou string a enviar
            dest_address: Tupla (host, port) do destinatário
        """
        if isinstance(data, str):
            data = data.encode()
        
        self.peer_address = dest_address
        self.total_bytes_sent += len(data)
        
        # Criar pacote
        packet = RDTPacket(PacketType.DATA, seq_num=self.seq_num, data=data)
        
        if self.start_time is None:
            self.start_time = time.time()
        
        # Loop com timer
        ack_received = False
        
        while not ack_received:
            # Enviar pacote e iniciar timer
            self.logger.send(f"{packet} - Dados: {data[:20]}")
            self._send_packet(packet)
            self.packets_sent += 1
            
            self._start_timer(packet)
            
            # Aguardar ACK
            response = self._wait_for_ack()
            
            # Parar timer
            self._stop_timer()
            
            if response == 'TIMEOUT':
                self.logger.timeout(f"Seq{self.seq_num} - Retransmitindo")
                self.timeouts += 1
                self.retransmissions += 1
                continue
            
            if response is None:
                continue
            
            if response.is_corrupt():
                self.logger.corrupt(f"{response} - Retransmitindo")
                self.retransmissions += 1
                continue
            
            if response.type == PacketType.ACK and response.seq_num == self.seq_num:
                self.logger.receive(f"{response} - Pacote confirmado")
                self.acks_received += 1
                ack_received = True
                
                # Alternar número de sequência
                self.seq_num = 1 - self.seq_num
    
    def _send_packet(self, packet):
        """Envia pacote através do canal"""
        packet_bytes = packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, self.peer_address)
        else:
            self.socket.sendto(packet_bytes, self.peer_address)
    
    def _start_timer(self, packet):
        """Inicia o timer"""
        with self.lock:
            if self.timer:
                self.timer.cancel()
            
            self.timer_running = True
            self.timer = threading.Timer(self.timeout_value, self._on_timeout)
            self.timer.daemon = True
            self.timer.start()
    
    def _stop_timer(self):
        """Para o timer"""
        with self.lock:
            self.timer_running = False
            if self.timer:
                self.timer.cancel()
                self.timer = None
    
    def _on_timeout(self):
        """Callback quando o timer expira"""
        with self.lock:
            if self.timer_running:
                # Força o socket a desbloquear
                try:
                    self.socket.sendto(b'', self.peer_address)
                except:
                    pass
    
    def _wait_for_ack(self):
        """
        Aguarda ACK (com possibilidade de timeout)
        
        Returns:
            RDTPacket, 'TIMEOUT', ou None
        """
        self.socket.settimeout(self.timeout_value + 0.5)
        
        try:
            with self.lock:
                if not self.timer_running:
                    return 'TIMEOUT'
            
            packet_bytes, _ = self.socket.recvfrom(1024)
            
            # Verificar se ainda está aguardando
            with self.lock:
                if not self.timer_running:
                    return 'TIMEOUT'
            
            return RDTPacket.deserialize(packet_bytes)
            
        except socket.timeout:
            return 'TIMEOUT'
        finally:
            self.socket.settimeout(None)
    
    def get_statistics(self):
        """Retorna estatísticas do remetente"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        throughput = (self.total_bytes_sent / elapsed) if elapsed > 0 else 0
        
        return {
            'packets_sent': self.packets_sent,
            'retransmissions': self.retransmissions,
            'timeouts': self.timeouts,
            'acks_received': self.acks_received,
            'retransmission_rate': self.retransmissions / self.packets_sent if self.packets_sent > 0 else 0,
            'total_bytes': self.total_bytes_sent,
            'elapsed_time': elapsed,
            'throughput_bps': throughput
        }
    
    def close(self):
        """Fecha o socket"""
        self._stop_timer()
        self.socket.close()


class RDT30Receiver:
    """Receptor do protocolo rdt3.0"""
    
    def __init__(self, port, channel=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'RDT3.0-Receiver-{port}')
        
        # Estado
        self.expected_seq_num = 0
        self.last_ack_sent = 1
        
        # Buffer
        self.received_messages = []
        
        # Estatísticas
        self.packets_received = 0
        self.corrupted_packets = 0
        self.duplicated_packets = 0
        self.acks_sent = 0
        
        # Thread
        self.running = False
        self.receive_thread = None
    
    def start(self):
        """Inicia o receptor"""
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        self.logger.info(f"Receptor iniciado na porta {self.port}")
    
    def _receive_loop(self):
        """Loop principal de recepção"""
        while self.running:
            try:
                packet_bytes, sender_addr = self.socket.recvfrom(2048)
                
                if len(packet_bytes) == 0:
                    continue
                
                self.packets_received += 1
                packet = RDTPacket.deserialize(packet_bytes)
                
                if packet is None:
                    continue
                
                self.logger.receive(f"{packet}")
                
                # Verificar corrupção
                if packet.is_corrupt():
                    self.logger.corrupt(f"{packet} - Reenviando ACK{self.last_ack_sent}")
                    self.corrupted_packets += 1
                    self._send_ack(sender_addr, self.last_ack_sent)
                    continue
                
                # Verificar número de sequência
                if packet.seq_num == self.expected_seq_num:
                    # Pacote esperado
                    self.logger.deliver(f"Seq{packet.seq_num} - Dados: {packet.data[:30]}")
                    self.received_messages.append(packet.data)
                    
                    self._send_ack(sender_addr, self.expected_seq_num)
                    self.last_ack_sent = self.expected_seq_num
                    self.expected_seq_num = 1 - self.expected_seq_num
                else:
                    # Pacote duplicado
                    self.logger.warning(f"{packet} - Duplicado! Reenviando ACK{self.last_ack_sent}")
                    self.duplicated_packets += 1
                    self._send_ack(sender_addr, self.last_ack_sent)
                    
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro: {e}")
    
    def _send_ack(self, dest_addr, seq_num):
        """Envia ACK"""
        ack_packet = RDTPacket(PacketType.ACK, seq_num=seq_num)
        self.logger.send(f"{ack_packet}")
        
        packet_bytes = ack_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.acks_sent += 1
    
    def get_messages(self):
        """Retorna mensagens recebidas"""
        return self.received_messages
    
    def get_statistics(self):
        """Retorna estatísticas"""
        return {
            'packets_received': self.packets_received,
            'corrupted_packets': self.corrupted_packets,
            'duplicated_packets': self.duplicated_packets,
            'acks_sent': self.acks_sent,
            'messages_delivered': len(self.received_messages)
        }
    
    def stop(self):
        """Para o receptor"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.socket.close()


# Teste completo
if __name__ == "__main__":
    print("=" * 70)
    print("Teste do Protocolo rdt3.0 (com Timer e Tratamento de Perda)")
    print("=" * 70)
    
    # Criar canal com perda e corrupção
    channel = UnreliableChannel(
        loss_rate=0.15,
        corrupt_rate=0.10,
        delay_range=(0.05, 0.5)
    )
    
    # Criar receptor e remetente
    receiver = RDT30Receiver(5021, channel)
    receiver.start()
    
    sender = RDT30Sender(5020, channel, timeout=2.0)
    
    # Enviar mensagens
    messages = [f"Mensagem número {i}" for i in range(20)]
    
    print(f"\nEnviando {len(messages)} mensagens")
    print("Canal: 15% perda, 10% corrupção, atraso 50-500ms\n")
    
    start_time = time.time()
    
    for i, msg in enumerate(messages):
        sender.send(msg, ('localhost', 5021))
        if (i + 1) % 5 == 0:
            print(f"  {i + 1} mensagens enviadas...")
    
    elapsed = time.time() - start_time
    
    # Aguardar processamento final
    time.sleep(1)
    
    # Resultados
    print("\n" + "=" * 70)
    print("RESULTADOS")
    print("=" * 70)
    
    print("\nRemetente:")
    stats_sender = sender.get_statistics()
    for key, value in stats_sender.items():
        if 'rate' in key:
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
        all_correct = all(
            received[i].decode() == messages[i]
            for i in range(len(messages))
        )
        if all_correct:
            print("✓ SUCESSO: Todas as mensagens entregues corretamente!")
        else:
            print("✗ ERRO: Mensagens com conteúdo incorreto")
    else:
        print("✗ ERRO: Mensagens perdidas")
    
    # Estatísticas do canal
    channel.print_statistics()
    
    # Limpar
    receiver.stop()
    sender.close()
