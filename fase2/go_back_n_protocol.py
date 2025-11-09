"""
Go-Back-N (GBN): Protocolo com pipelining e ACKs cumulativos
Características:
- Janela de envio de tamanho N
- Múltiplos pacotes não confirmados em trânsito
- ACKs cumulativos (ACK n confirma todos até n)
- Retransmissão de toda a janela em caso de timeout
"""
import socket
import threading
import time
import sys
sys.path.append('../..')

from utils.packet import RDTPacket, PacketType
from utils.simulator import UnreliableChannel
from utils.logger import ProtocolLogger


class GBNSender:
    """Remetente Go-Back-N com janela deslizante"""
    
    def __init__(self, port, window_size=5, channel=None, timeout=1.0):
        """
        Inicializa o remetente GBN
        
        Args:
            port: Porta local
            window_size: Tamanho da janela de envio (N)
            channel: Canal não confiável (opcional)
            timeout: Timeout em segundos
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.window_size = window_size
        self.channel = channel
        self.timeout_value = timeout
        
        self.logger = ProtocolLogger(f'GBN-Sender-{port}')
        
        # Variáveis de controle da janela
        self.base = 0           # Número do pacote mais antigo não confirmado
        self.next_seq_num = 0   # Próximo número de sequência disponível
        self.send_buffer = []   # Buffer de pacotes enviados mas não confirmados
        
        # Timer único para o pacote base
        self.timer = None
        self.timer_running = False
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
        """
        Inicia o remetente e thread de recepção de ACKs
        
        Args:
            dest_address: Endereço do receptor (host, port)
        """
        self.peer_address = dest_address
        self.running = True
        self.start_time = time.time()
        
        # Thread para receber ACKs
        self.ack_thread = threading.Thread(target=self._ack_receive_loop)
        self.ack_thread.daemon = True
        self.ack_thread.start()
        
        self.logger.info(f"Remetente GBN iniciado (janela={self.window_size})")
    
    def send(self, data):
        """
        Envia dados usando protocolo GBN
        
        Args:
            data: Bytes ou string a enviar
        """
        if isinstance(data, str):
            data = data.encode()
        
        self.total_bytes_sent += len(data)
        
        # Aguardar se a janela estiver cheia
        while self.next_seq_num >= self.base + self.window_size:
            time.sleep(0.01)  # Aguardar ACKs
        
        # Criar e enviar pacote
        packet = RDTPacket(PacketType.DATA, seq_num=self.next_seq_num, data=data)
        
        with self.lock:
            self.send_buffer.append((self.next_seq_num, packet, time.time()))
            self._send_packet(packet)
            self.packets_sent += 1
            
            self.logger.send(f"{packet} - Dados: {data[:20]}")
            
            # Se for o primeiro pacote da janela, iniciar timer
            if self.base == self.next_seq_num:
                self._start_timer()
            
            self.next_seq_num += 1
    
    def _send_packet(self, packet):
        """Envia um pacote através do canal"""
        packet_bytes = packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, self.peer_address)
        else:
            self.socket.sendto(packet_bytes, self.peer_address)
    
    def _ack_receive_loop(self):
        """Thread que recebe ACKs do receptor"""
        self.socket.settimeout(0.1)
        
        while self.running:
            try:
                packet_bytes, _ = self.socket.recvfrom(1024)
                ack_packet = RDTPacket.deserialize(packet_bytes)
                
                if ack_packet is None or ack_packet.is_corrupt():
                    if ack_packet:
                        self.logger.corrupt(f"{ack_packet}")
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
        Processa ACK recebido (cumulativo)
        
        Args:
            ack_packet: Pacote ACK recebido
        """
        ack_num = ack_packet.seq_num
        self.logger.receive(f"{ack_packet} - ACK cumulativo")
        
        with self.lock:
            # ACK cumulativo: confirma todos os pacotes até ack_num
            if ack_num >= self.base:
                self.acks_received += 1
                
                # Remover pacotes confirmados do buffer
                self.send_buffer = [
                    (seq, pkt, t) for seq, pkt, t in self.send_buffer 
                    if seq > ack_num
                ]
                
                # Mover a base da janela
                old_base = self.base
                self.base = ack_num + 1
                
                self.logger.info(f"Janela avançada: base {old_base} -> {self.base}")
                
                # Gerenciar timer
                if self.base == self.next_seq_num:
                    # Todos os pacotes confirmados
                    self._stop_timer()
                else:
                    # Ainda há pacotes não confirmados, reiniciar timer
                    self._stop_timer()
                    self._start_timer()
    
    def _start_timer(self):
        """Inicia o timer para o pacote base"""
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
        """
        Callback quando o timer expira
        Retransmite todos os pacotes da janela
        """
        self.logger.timeout(f"Timer expirou! Retransmitindo janela [base={self.base}]")
        self.timeouts += 1
        
        with self.lock:
            # Retransmitir todos os pacotes não confirmados
            for seq_num, packet, send_time in self.send_buffer:
                self.logger.retransmit(f"{packet}")
                self._send_packet(packet)
                self.retransmissions += 1
            
            # Reiniciar timer
            if self.send_buffer:
                self._start_timer()
    
    def wait_for_completion(self, timeout=10.0):
        """
        Aguarda todos os pacotes serem confirmados
        
        Args:
            timeout: Tempo máximo de espera
            
        Returns:
            True se todos confirmados, False se timeout
        """
        start = time.time()
        while self.base < self.next_seq_num:
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)
        return True
    
    def get_statistics(self):
        """Retorna estatísticas do remetente"""
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
        self._stop_timer()
        if self.ack_thread:
            self.ack_thread.join(timeout=1.0)
        self.socket.close()
        self.logger.info("Remetente GBN encerrado")


class GBNReceiver:
    """Receptor Go-Back-N"""
    
    def __init__(self, port, channel=None):
        """
        Inicializa o receptor GBN
        
        Args:
            port: Porta local
            channel: Canal não confiável (opcional)
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'GBN-Receiver-{port}')
        
        # Número de sequência esperado
        self.expected_seq_num = 0
        
        # Buffer de mensagens recebidas
        self.received_messages = []
        
        # Estatísticas
        self.packets_received = 0
        self.out_of_order_packets = 0
        self.corrupted_packets = 0
        self.acks_sent = 0
        
        # Thread de recepção
        self.running = False
        self.receive_thread = None
    
    def start(self):
        """Inicia o receptor"""
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        self.logger.info(f"Receptor GBN iniciado na porta {self.port}")
    
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
                
                # Verificar corrupção
                if packet.is_corrupt():
                    self.logger.corrupt(f"{packet} - Reenviando ACK{self.expected_seq_num - 1}")
                    self.corrupted_packets += 1
                    
                    # Reenviar ACK do último pacote correto
                    if self.expected_seq_num > 0:
                        self._send_ack(sender_addr, self.expected_seq_num - 1)
                    continue
                
                # Verificar número de sequência
                if packet.seq_num == self.expected_seq_num:
                    # Pacote esperado - entregar
                    self.logger.deliver(f"Seq{packet.seq_num} - Dados: {packet.data[:30]}")
                    self.received_messages.append(packet.data)
                    
                    # Enviar ACK cumulativo
                    self._send_ack(sender_addr, self.expected_seq_num)
                    self.expected_seq_num += 1
                    
                else:
                    # Pacote fora de ordem - descartar e reenviar último ACK
                    self.logger.warning(f"{packet} - Fora de ordem! Esperado: {self.expected_seq_num}")
                    self.out_of_order_packets += 1
                    
                    # Reenviar ACK do último pacote recebido em ordem
                    if self.expected_seq_num > 0:
                        self._send_ack(sender_addr, self.expected_seq_num - 1)
                    
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro: {e}")
    
    def _send_ack(self, dest_addr, seq_num):
        """
        Envia ACK cumulativo
        
        Args:
            dest_addr: Endereço do remetente
            seq_num: Número de sequência a confirmar
        """
        ack_packet = RDTPacket(PacketType.ACK, seq_num=seq_num)
        self.logger.send(f"{ack_packet} - ACK cumulativo até {seq_num}")
        
        packet_bytes = ack_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.acks_sent += 1
    
    def get_messages(self):
        """Retorna lista de mensagens recebidas em ordem"""
        return self.received_messages
    
    def get_statistics(self):
        """Retorna estatísticas do receptor"""
        return {
            'packets_received': self.packets_received,
            'out_of_order_packets': self.out_of_order_packets,
            'corrupted_packets': self.corrupted_packets,
            'acks_sent': self.acks_sent,
            'messages_delivered': len(self.received_messages)
        }
    
    def stop(self):
        """Para o receptor"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.socket.close()


# Exemplo de uso e comparação com Stop-and-Wait
if __name__ == "__main__":
    print("=" * 70)
    print("Teste do Protocolo Go-Back-N (GBN)")
    print("=" * 70)
    
    # Configurar canal com perda
    channel = UnreliableChannel(
        loss_rate=0.10,
        corrupt_rate=0.05,
        delay_range=(0.01, 0.1)
    )
    
    # Criar receptor e remetente
    receiver = GBNReceiver(7001, channel)
    receiver.start()
    
    sender = GBNSender(7000, window_size=5, channel=channel, timeout=1.0)
    sender.start(('localhost', 7001))
    
    # Enviar dados
    print(f"\nEnviando 50 mensagens com janela={sender.window_size}...")
    print("Canal: 10% perda, 5% corrupção\n")
    
    messages = [f"Pacote {i:03d}" for i in range(50)]
    
    for msg in messages:
        sender.send(msg)
        time.sleep(0.01)  # Pequeno delay para não sobrecarregar
    
    # Aguardar conclusão
    print("Aguardando confirmação de todos os pacotes...")
    success = sender.wait_for_completion(timeout=15.0)
    
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
        print("✓ SUCESSO: Todas as mensagens entregues!")
    else:
        print(f"✗ AVISO: {len(messages) - len(received)} mensagens perdidas")
    
    # Estatísticas do canal
    channel.print_statistics()
    
    # Limpar
    sender.stop()
    receiver.stop()
