"""
Módulo para criação e manipulação de pacotes RDT/TCP
"""
import struct
import hashlib


class PacketType:
    """Tipos de pacotes suportados"""
    DATA = 0
    ACK = 1
    NAK = 2
    SYN = 3
    FIN = 4


class RDTPacket:
    """
    Estrutura de pacote para protocolos RDT
    Formato: [Tipo(1) | SeqNum(1) | Checksum(4) | Dados(variável)]
    """
    
    def __init__(self, packet_type, seq_num=0, data=b''):
        """
        Inicializa um pacote RDT
        
        Args:
            packet_type: Tipo do pacote (DATA, ACK, NAK)
            seq_num: Número de sequência (0 ou 1 alternante)
            data: Dados a serem transmitidos no pacote entre as aplicações
        """
        self.type = packet_type
        self.seq_num = seq_num
        self.data = data
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self):
        """Calcula checksum MD5 do pacote"""
        content = struct.pack('BB', self.type, self.seq_num) + self.data
        return hashlib.md5(content).digest()[:4]
    
    def serialize(self):
        """Serializa o pacote para bytes"""
        header = struct.pack('BB4s', self.type, self.seq_num, self.checksum)
        return header + self.data
    
    @staticmethod
    def deserialize(packet_bytes):
        """
        Deserializa bytes para um objeto RDTPacket
        
        Args:
            packet_bytes: Bytes recebidos
            
        Returns:
            RDTPacket ou None se inválido
        """
        try:
            if len(packet_bytes) < 6:
                return None
            
            packet_type, seq_num, checksum = struct.unpack('BB4s', packet_bytes[:6])
            data = packet_bytes[6:]
            
            packet = RDTPacket(packet_type, seq_num, data)
            packet.checksum = checksum
            
            return packet
        except Exception as e:
            print(f"Erro ao deserializar pacote: {e}")
            return None
    
    def is_corrupt(self):
        """Verifica se o pacote está corrompido"""
        expected_checksum = self._calculate_checksum()
        return self.checksum != expected_checksum
    
    def __str__(self):
        type_names = {0: 'DATA', 1: 'ACK', 2: 'NAK', 3: 'SYN', 4: 'FIN'}
        return f"[{type_names.get(self.type, 'UNKNOWN')} | Seq:{self.seq_num} | Len:{len(self.data)}]"


class TCPSegment:
    """
    Estrutura simplificada de segmento TCP
    Campos: Source Port, Dest Port, Seq Number, Ack Number, Flags, Window Size, Checksum
    """
    
    # Flags TCP
    FLAG_FIN = 0x01
    FLAG_SYN = 0x02
    FLAG_ACK = 0x10
    
    def __init__(self, src_port, dst_port, seq_num, ack_num, 
                 flags=0, window_size=4096, data=b''):
        """
        Inicializa um segmento TCP
        
        Args:
            src_port: Porta de origem
            dst_port: Porta de destino
            seq_num: Número de sequência
            ack_num: Número de acknowledgment
            flags: Flags TCP (SYN, ACK, FIN)
            window_size: Tamanho da janela
            data: Dados do segmento
        """
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.window_size = window_size
        self.data = data
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self):
        """Calcula checksum do segmento"""
        header = struct.pack('!HHIIBBH', 
                           self.src_port, self.dst_port,
                           self.seq_num, self.ack_num,
                           5, self.flags, self.window_size)
        content = header + self.data
        return hashlib.md5(content).digest()[:2]
    
    def serialize(self):
        """Serializa o segmento para bytes"""
        header = struct.pack('!HHIIBBH2s',
                           self.src_port, self.dst_port,
                           self.seq_num, self.ack_num,
                           5, self.flags, self.window_size,
                           self.checksum)
        return header + self.data
    
    @staticmethod
    def deserialize(segment_bytes):
        """Deserializa bytes para TCPSegment"""
        try:
            if len(segment_bytes) < 20:
                return None
            
            src_port, dst_port, seq_num, ack_num, header_len, flags, \
                window_size, checksum = struct.unpack('!HHIIBBH2s', segment_bytes[:20])
            
            data = segment_bytes[20:]
            
            segment = TCPSegment(src_port, dst_port, seq_num, ack_num,
                               flags, window_size, data)
            segment.checksum = checksum
            
            return segment
        except Exception as e:
            print(f"Erro ao deserializar segmento TCP: {e}")
            return None
    
    def is_corrupt(self):
        """Verifica se o segmento está corrompido"""
        expected_checksum = self._calculate_checksum()
        return self.checksum != expected_checksum
    
    def has_flag(self, flag):
        """Verifica se uma flag está ativada"""
        return (self.flags & flag) != 0
    
    def __str__(self):
        flags_str = []
        if self.has_flag(self.FLAG_SYN):
            flags_str.append('SYN')
        if self.has_flag(self.FLAG_ACK):
            flags_str.append('ACK')
        if self.has_flag(self.FLAG_FIN):
            flags_str.append('FIN')
        
        return (f"[TCP | {self.src_port}->{self.dst_port} | "
                f"Seq:{self.seq_num} Ack:{self.ack_num} | "
                f"Flags:{','.join(flags_str) if flags_str else 'NONE'} | "
                f"Win:{self.window_size} | Len:{len(self.data)}]")
