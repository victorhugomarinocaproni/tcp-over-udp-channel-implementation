"""
Simulador de canal não confiável para testes
Simula perda de pacotes, corrupção e atrasos
"""
import random
import threading
import time


class UnreliableChannel:
    """
    Simula um canal de comunicação não confiável
    Pode perder pacotes, corromper dados e introduzir atrasos
    """
    
    def __init__(self, loss_rate=0.0, corrupt_rate=0.0, delay_range=(0.01, 0.1)):
        """
        Inicializa o canal não confiável
        
        Args:
            loss_rate: Probabilidade de perda de pacote (0.0 a 1.0)
            corrupt_rate: Probabilidade de corrupção (0.0 a 1.0)
            delay_range: Tupla (min_delay, max_delay) em segundos
        """
        self.loss_rate = loss_rate
        self.corrupt_rate = corrupt_rate
        self.delay_range = delay_range
        
        # Estatísticas
        self.packets_sent = 0
        self.packets_lost = 0
        self.packets_corrupted = 0
        self.total_delay = 0.0
    
    def send(self, packet, dest_socket, dest_addr):
        """
        Envia pacote através do canal não confiável
        
        Args:
            packet: Bytes do pacote a enviar
            dest_socket: Socket UDP de destino
            dest_addr: Endereço (host, port) de destino
        """
        self.packets_sent += 1
        
        # Simular perda
        if random.random() < self.loss_rate:
            self.packets_lost += 1
            print(f"[CANAL] Pacote #{self.packets_sent} PERDIDO")
            return
        
        # Simular corrupção
        if random.random() < self.corrupt_rate:
            packet = self._corrupt_packet(packet)
            self.packets_corrupted += 1
            print(f"[CANAL] Pacote #{self.packets_sent} CORROMPIDO")
        
        # Simular atraso
        delay = random.uniform(*self.delay_range)
        self.total_delay += delay
        
        # Enviar com atraso
        timer = threading.Timer(delay, self._delayed_send, 
                              args=(packet, dest_socket, dest_addr))
        timer.daemon = True
        timer.start()
    
    def _delayed_send(self, packet, dest_socket, dest_addr):
        """Envia o pacote após o atraso"""
        try:
            dest_socket.sendto(packet, dest_addr)
        except Exception as e:
            print(f"[CANAL] Erro ao enviar pacote: {e}")
    
    def _corrupt_packet(self, packet):
        """
        Corrompe bits aleatórios do pacote
        
        Args:
            packet: Bytes do pacote original
            
        Returns:
            Bytes do pacote corrompido
        """
        packet_list = list(packet)
        
        if len(packet_list) == 0:
            return packet
        
        # Corrompe de 1 a 5 bytes aleatórios
        num_corruptions = random.randint(1, min(5, len(packet_list)))
        
        for _ in range(num_corruptions):
            idx = random.randint(0, len(packet_list) - 1)
            # Inverter todos os bits do byte
            packet_list[idx] = packet_list[idx] ^ 0xFF
        
        return bytes(packet_list)
    
    def get_statistics(self):
        """
        Retorna estatísticas do canal
        
        Returns:
            Dict com estatísticas
        """
        return {
            'packets_sent': self.packets_sent,
            'packets_lost': self.packets_lost,
            'packets_corrupted': self.packets_corrupted,
            'loss_rate_actual': self.packets_lost / self.packets_sent if self.packets_sent > 0 else 0,
            'corrupt_rate_actual': self.packets_corrupted / self.packets_sent if self.packets_sent > 0 else 0,
            'avg_delay': self.total_delay / self.packets_sent if self.packets_sent > 0 else 0
        }
    
    def reset_statistics(self):
        """Reseta as estatísticas do canal"""
        self.packets_sent = 0
        self.packets_lost = 0
        self.packets_corrupted = 0
        self.total_delay = 0.0
    
    def print_statistics(self):
        """Imprime estatísticas formatadas"""
        stats = self.get_statistics()
        print("\n" + "="*50)
        print("ESTATÍSTICAS DO CANAL")
        print("="*50)
        print(f"Pacotes enviados:      {stats['packets_sent']}")
        print(f"Pacotes perdidos:      {stats['packets_lost']} ({stats['loss_rate_actual']*100:.1f}%)")
        print(f"Pacotes corrompidos:   {stats['packets_corrupted']} ({stats['corrupt_rate_actual']*100:.1f}%)")
        print(f"Atraso médio:          {stats['avg_delay']*1000:.2f} ms")
        print("="*50 + "\n")


class ReliableChannel(UnreliableChannel):
    """Canal perfeitamente confiável (para teste do rdt1.0)"""
    
    def __init__(self):
        super().__init__(loss_rate=0.0, corrupt_rate=0.0, delay_range=(0.001, 0.005))
