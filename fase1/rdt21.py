"""
rdt2.1: Adiciona números de sequência para lidar com ACKs/NAKs corrompidos
Características:
- Números de sequência alternantes (0 e 1)
- Detecta e descarta pacotes duplicados
- Remetente retransmite se ACK corrompido ou incorreto
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


class RDT21Sender:
    """Remetente do protocolo rdt2.1 com números de sequência"""
    
    def __init__(self, port, channel = None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'RDT2.1-Sender-{port}')
        
        # Estado e número de sequência
        self.seq_num = 0  # Alterna entre 0 e 1
        self.peer_address = None
        
        # Estatísticas
        self.packets_sent = 0
        self.retransmissions = 0
        self.acks_received = 0
        self.duplicated_acks = 0
        self.naks_received = 0
    


    def send(self, data, dest_address):
        """
        Envia dados usando protocolo rdt2.1 com números de sequência

        Args:
            data: Bytes ou string a enviar
            dest_address: Tupla (host, port) do destinatário
        """
        if isinstance(data, str):
            data = data.encode()

        self.peer_address = dest_address

        # Criar pacote com número de sequência atual
        packet = RDTPacket(PacketType.DATA, seq_num = self.seq_num, data = data)
        self.logger.send(f"{packet} - Dados: {data[:20]}")

        # Loop Stop-and-Wait com Números de Sequência (SeqNum)
        while True:
            # Enviar pacote
            self._send_packet(packet)
            self.packets_sent += 1

            response = self._wait_for_response()

            if response.is_corrupt():
                self.logger.corrupt(f"{response} - Retransmitindo")
                self.retransmissions += 1
                continue

            # Processar resposta de acordo com seu tipo e sequência
            if response.type == PacketType.ACK:
                if response.seq_num == self.seq_num:
                    # ACK correto recebido - sucesso!
                    self.logger.receive(f"{response} - Pacote confirmado")
                    self.acks_received += 1
                    self.seq_num = 1 - self.seq_num
                    break
                else:
                    # ACK duplicado (número de sequência incorreto)
                    self.logger.receive(f"{response} - ACK duplicado, retransmitindo")
                    self.duplicated_acks += 1
                    self.retransmissions += 1
                    continue

            elif response.type == PacketType.NAK:
                # NAK recebido - verificar se é com o número de sequência correto
                if response.seq_num == self.seq_num:
                    # NAK correto - o receptor pediu retransmissão
                    self.logger.receive(f"{response} - Retransmissão solicitada (NAK Seq{response.seq_num})")
                    self.naks_received += 1
                    self.retransmissions += 1
                    continue
                else:
                    # NAK duplicado (número de sequência incorreto) - ignorar
                    self.logger.receive(f"{response} - NAK duplicado, ignorando")
                    continue

    
    def _send_packet(self, packet):
        """Envia pacote através do canal"""
        packet_bytes = packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, self.peer_address)
        else:
            self.socket.sendto(packet_bytes, self.peer_address)
    
    def _wait_for_response(self):
        """Aguarda ACK do receptor"""
        try:
            packet_bytes, _ = self.socket.recvfrom(1024)
            return RDTPacket.deserialize(packet_bytes)
        except Exception:
            ...
            # RDT 2.1 também assume que pacotes podem ser corrompidos, mas não perdidos.
            # Logo, não há implementaçaõ de timeout aqui.
    
    def get_statistics(self):
        """Retorna estatísticas do remetente"""
        return {
            'packets_sent': self.packets_sent,
            'retransmissions': self.retransmissions,
            'acks_received': self.acks_received,
            'duplicated_acks': self.duplicated_acks,
            'naks_received': self.naks_received
        }
    
    def close(self):
        """Fecha o socket"""
        self.socket.close()


class RDT21Receiver:
    """Receptor do protocolo rdt2.1 com números de sequência"""
    
    def __init__(self, port, channel = None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'RDT2.1-Receiver-{port}')
        
        # Estado - número de sequência esperado
        self.expected_seq_num = 0
        self.last_ack_sent = 1  # ACK do pacote anterior
        
        # Buffer de mensagens recebidas
        self.received_messages = []
        
        # Estatísticas
        self.packets_received = 0
        self.corrupted_packets = 0
        self.duplicated_packets = 0
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

                # Verificar corrupção - enviar NAK com último número de sequência válido
                if packet.is_corrupt():
                    self.logger.corrupt(f"{packet} - Pacote corrompido, enviando NAK{self.last_ack_sent}")
                    self.corrupted_packets += 1
                    self._send_nak(sender_addr, self.last_ack_sent)
                    continue

                # Verificar número de sequência
                if packet.seq_num == self.expected_seq_num:
                    # Pacote esperado - entregar dados
                    self.logger.deliver(f"Seq{packet.seq_num} - Dados: {packet.data[:30]}")
                    self.received_messages.append(packet.data)

                    # Enviar ACK e alternar número esperado
                    self._send_ack(sender_addr, self.expected_seq_num)
                    self.last_ack_sent = self.expected_seq_num
                    self.expected_seq_num = 1 - self.expected_seq_num
                else:
                    # Pacote duplicado - enviar NAK com o último ACK válido
                    self.logger.warning(
                        f"{packet} - Duplicado! Esperava Seq. Num.: {self.expected_seq_num}, "
                        f"enviando NAK{self.last_ack_sent}"
                    )
                    self.duplicated_packets += 1
                    self._send_nak(sender_addr, self.last_ack_sent)

            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro no loop de recepção: {e}")
    
    def _send_ack(self, dest_addr, seq_num):
        """Envia ACK ao Remetente (Sender) com número de sequência"""
        ack_packet = RDTPacket(PacketType.ACK, seq_num = seq_num)
        self.logger.send(f"{ack_packet}")
        
        packet_bytes = ack_packet.serialize()
        
        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)
        
        self.acks_sent += 1

    def _send_nak(self, dest_addr, seq_num):
        """Envia NAK ao Remetente (Sender) com número de sequência"""
        nak_packet = RDTPacket(PacketType.NAK, seq_num = seq_num)
        self.logger.send(f"{nak_packet}")

        packet_bytes = nak_packet.serialize()

        if self.channel:
            self.channel.send(packet_bytes, self.socket, dest_addr)
        else:
            self.socket.sendto(packet_bytes, dest_addr)

        self.naks_sent += 1
    
    def get_messages(self):
        """Retorna lista de mensagens recebidas (sem duplicatas)"""
        return self.received_messages
    
    def get_statistics(self):
        """Retorna estatísticas do receptor"""
        return {
            'packets_received': self.packets_received,
            'corrupted_packets': self.corrupted_packets,
            'duplicated_packets': self.duplicated_packets,
            'acks_sent': self.acks_sent,
            'naks_sent': self.naks_sent,
            'messages_delivered': len(self.received_messages)
        }
    
    def stop(self):
        """Para o receptor"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        self.socket.close()


# Exemplo de uso e teste
if __name__ == "__main__":
    print("=" * 60)
    print("Teste do Protocolo rdt2.1 (com Números de Sequência)")
    print("=" * 60)
    
    # Criar canal com corrupção de pacotes DATA e ACKs
    channel = UnreliableChannel(loss_rate=0.0, corrupt_rate=0.2, 
                                delay_range=(0.01, 0.1))
    
    # Criar receptor e remetente
    receiver = RDT21Receiver(5011, channel)
    receiver.start()
    
    sender = RDT21Sender(5010, channel)
    
    # Enviar mensagens
    messages = [f"Mensagem {i}" for i in range(15)]
    
    print(f"\nEnviando {len(messages)} mensagens com 20% de corrupção...\n")
    
    for msg in messages:
        sender.send(msg, ('localhost', 5011))
        time.sleep(0.15)
    
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
    
    print("\nMensagens recebidas (sem duplicatas):")
    received = receiver.get_messages()
    for i, msg in enumerate(received):
        print(f"  {i+1}. {msg.decode()}")
    
    # Verificação
    print(f"\n✓ Verificação: {len(received)} de {len(messages)} mensagens recebidas")
    
    if len(received) == len(messages):
        print("✓ SUCESSO: Todas as mensagens foram entregues sem duplicação!")
    else:
        print("✗ FALHA: Mensagens perdidas ou duplicadas")
    
    # Estatísticas do canal
    channel.print_statistics()
    
    # Overhead
    header_size = 6  # 1 (tipo) + 1 (seq) + 4 (checksum)
    total_payload = sum(len(msg) for msg in messages)
    overhead_bytes = stats_sender['packets_sent'] * header_size
    overhead_percent = (overhead_bytes / total_payload) * 100
    
    print(f"\nOverhead: {overhead_bytes} bytes ({overhead_percent:.1f}% do payload)")
    
    # Limpar
    receiver.stop()
    sender.close()
