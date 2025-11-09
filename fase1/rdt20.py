"""
rdt2.0: Transferência confiável sobre canal com erros de bits
Características:
- Usa ACK/NAK para confirmar recebimento
- Detecta corrupção com checksum
- Protocolo Stop-and-Wait
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


class RDT20Sender:
    """Remetente do protocolo rdt2.0"""
    
    def __init__(self, port, channel = None):
        """
        Inicializa o Remetente (Sender)
        
        Args:
            port: Porta local para bind
            channel: UnreliableChannel para simular erros (opcional)
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # --> Define o canal socket como Ipv4 e UDP
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'RDT2.0-Sender-{port}')
        
        # Estado
        self.state = 'WAIT_CALL'  # WAIT_CALL ou WAIT_ACK
        self.peer_address = None
        
        # Estatísticas
        self.packets_sent = 0
        self.retransmissions = 0
        self.acks_received = 0
        self.naks_received = 0
    
    def send(self, data, dest_address):
        """
        Envia dados usando protocolo rdt2.0 (Stop-and-Wait)
        
        Args:
            data: Bytes ou string a enviar
            dest_address: Tupla (host, port) do destinatário
        """
        if isinstance(data, str):
            data = data.encode()
        
        self.peer_address = dest_address
        
        # Criar pacote DATA
        packet = RDTPacket(PacketType.DATA, seq_num = 0, data = data)
        self.logger.send(f"{packet} - Dados: {data[:20]}")
        
        # Loop Stop-and-Wait
        while True:
            self.state = 'WAIT_ACK'
            
            # Enviar pacote
            self._send_packet(packet)
            self.packets_sent += 1
            
            # Aguardar ACK ou NAK
            response = self._wait_for_response()
            
            if response.is_corrupt():
                self.logger.corrupt(f"{response} - Retransmitindo")
                self.retransmissions += 1
                continue
            
            if response.type == PacketType.ACK:
                self.logger.receive(f"{response} - Pacote confirmado")
                self.acks_received += 1
                self.state = 'WAIT_CALL'
                break
            
            elif response.type == PacketType.NAK:
                self.logger.receive(f"{response} - Retransmissão solicitada")
                self.naks_received += 1
                self.retransmissions += 1
                continue
    
    def _send_packet(self, packet):
        """Envia pacote através do canal"""
        packet_bytes = packet.serialize()

        if self.channel:
            self.channel.send(packet_bytes, self.socket, self.peer_address)
        else:
            self.socket.sendto(packet_bytes, self.peer_address)
    
    def _wait_for_response(self):
        """
        Aguarda resposta (ACK ou NAK) do receptor
            
        Returns:
            RDTPacket
        """
        try:
            packet_bytes, _ = self.socket.recvfrom(1024)
            return RDTPacket.deserialize(packet_bytes)
        except Exception:
            ...
            # RDT 2.0 assume que pacotes podem ser corrompidos, mas não perdidos, portanto
            # não implementa validação de timeout
    
    def get_statistics(self):
        """Retorna estatísticas do remetente"""
        return {
            'packets_sent': self.packets_sent,
            'retransmissions': self.retransmissions,
            'acks_received': self.acks_received,
            'naks_received': self.naks_received
        }
    
    def close(self):
        """Fecha o socket"""
        self.socket.close()


class RDT20Receiver:
    """Receptor do protocolo rdt2.0"""
    
    def __init__(self, port, channel = None):
        """
        Inicializa o receptor
        
        Args:
            port: Porta local para bind
            channel: UnreliableChannel para simular erros (opcional)
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'RDT2.0-Receiver-{port}')
        
        # Buffer de mensagens recebidas
        self.received_messages = []
        
        # Estatísticas
        self.packets_received = 0
        self.corrupted_packets = 0
        self.acks_sent = 0
        self.naks_sent = 0
        
        # Thread de recepção
        self.running = False
        self.receive_thread = None
    
    def start(self):
        """Inicia o receptor em uma thread"""
        self.running = True
        self.receive_thread = threading.Thread(target = self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        self.logger.info(f"Receptor iniciado na porta {self.port}")
    
    def _receive_loop(self):
        """Loop principal de recepção"""
        while self.running:
            try:
                packet_bytes, sender_addr = self.socket.recvfrom(2048)
                self.packets_received += 1
                
                packet = RDTPacket.deserialize(packet_bytes)
                
                if packet is None:
                    self.logger.error("Pacote inválido recebido")
                    continue
                
                self.logger.receive(f"{packet}")
                
                # Verificar corrupção
                if packet.is_corrupt():
                    self.logger.corrupt(f"{packet} - Enviando NAK")
                    self.corrupted_packets += 1
                    self._send_nak(sender_addr)
                else:
                    # Pacote íntegro - entregar dados e enviar ACK
                    self.logger.deliver(f"Dados: {packet.data[:30]}")
                    self.received_messages.append(packet.data)
                    self._send_ack(sender_addr)
                    
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro no loop de recepção: {e}")
    
    def _send_ack(self, dest_addr):
        """Envia ACK ao remetente"""
        ack_packet = RDTPacket(PacketType.ACK, seq_num = 0)
        self.logger.send(f"{ack_packet}")
        
        packet_bytes = ack_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.acks_sent += 1
    
    def _send_nak(self, dest_addr):
        """Envia NAK ao remetente"""
        nak_packet = RDTPacket(PacketType.NAK, seq_num = 0)
        self.logger.send(f"{nak_packet}")
        
        packet_bytes = nak_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.naks_sent += 1
    
    def get_messages(self):
        """Retorna lista de mensagens recebidas"""
        return self.received_messages
    
    def get_statistics(self):
        """Retorna estatísticas do receptor"""
        return {
            'packets_received': self.packets_received,
            'corrupted_packets': self.corrupted_packets,
            'acks_sent': self.acks_sent,
            'naks_sent': self.naks_sent,
            'messages_delivered': len(self.received_messages)
        }
    
    def stop(self):
        """Para o receptor"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout = 1.0)
        self.socket.close()


# Exemplo de uso
if __name__ == "__main__":
    print("=" * 60)
    print("Teste do Protocolo rdt2.0")
    print("=" * 60)
    
    # Criar canal com 30% de corrupção
    channel = UnreliableChannel(
        loss_rate = 0.0,
        corrupt_rate = 0.3,
        delay_range = (0.01, 0.1)
    )
    
    # Criar receptor e remetente
    receiver = RDT20Receiver(5001, channel)
    receiver.start()
    
    sender = RDT20Sender(5000, channel)
    
    # Enviar mensagens
    messages = [f"Mensagem {i}" for i in range(10)]
    
    print(f"\nEnviando {len(messages)} mensagens...\n")
    
    for msg in messages:
        sender.send(msg, ('localhost', 5001))
        time.sleep(0.2)
    
    # Aguardar processamento
    time.sleep(2)
    
    # Exibir resultados
    print("\n" + "=" * 60)
    print("RESULTADOS")
    print("=" * 60)
    
    print("\nRemetente:")
    stats_sender = sender.get_statistics()
    for key, value in stats_sender.items():
        print(f"  {key}: {value}")
    
    print("\nReceptor:")
    stats_receiver = receiver.get_statistics()
    for key, value in stats_receiver.items():
        print(f"  {key}: {value}")
    
    print("\nMensagens recebidas:")
    received = receiver.get_messages()
    for i, msg in enumerate(received):
        print(f"  {i+1}. {msg.decode()}")
    
    print(f"\nVerificação: {len(received)} de {len(messages)} mensagens recebidas")
    
    # Estatísticas do canal
    channel.print_statistics()
    
    # Limpar
    receiver.stop()
    sender.close()
