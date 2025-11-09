"""
SimpleTCPSocket: Implementação de TCP simplificado sobre UDP
Funcionalidades:
- Three-way handshake (SYN, SYN-ACK, ACK)
- Transferência confiável com ACKs cumulativos
- Controle de fluxo (window size)
- Retransmissão adaptativa (estimativa de RTT)
- Encerramento com four-way handshake
"""
import socket
import threading
import time
import random
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.packet import TCPSegment
from utils.logger import ProtocolLogger


class SimpleTCPSocket:
    """Socket TCP simplificado implementado sobre UDP"""
    
    # Estados da conexão TCP
    STATE_CLOSED = 'CLOSED'
    STATE_LISTEN = 'LISTEN'
    STATE_SYN_SENT = 'SYN_SENT'
    STATE_SYN_RECEIVED = 'SYN_RECEIVED'
    STATE_ESTABLISHED = 'ESTABLISHED'
    STATE_FIN_WAIT_1 = 'FIN_WAIT_1'
    STATE_FIN_WAIT_2 = 'FIN_WAIT_2'
    STATE_CLOSE_WAIT = 'CLOSE_WAIT'
    STATE_LAST_ACK = 'LAST_ACK'
    STATE_TIME_WAIT = 'TIME_WAIT'
    
    def __init__(self, port, channel=None):
        """
        Inicializa o socket TCP simplificado
        
        Args:
            port: Porta local para bind
            channel: Canal não confiável (opcional, para testes)
        """
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('localhost', port))
        self.port = port
        self.channel = channel
        
        self.logger = ProtocolLogger(f'TCP-{port}')
        
        # Estado da conexão
        self.state = self.STATE_CLOSED
        self.state_lock = threading.Lock()
        
        # Números de sequência e ACK
        self.seq_num = random.randint(0, 10000)  # ISN
        self.ack_num = 0
        
        # Peer information
        self.peer_address = None
        self.peer_seq_num = 0
        
        # Buffers
        self.send_buffer = []  # [(seq, data, time, acked)]
        self.recv_buffer = {}  # {seq: data}
        self.buffer_lock = threading.Lock()
        
        # Controle de fluxo
        self.recv_window = 4096  # Janela de recepção (bytes)
        self.send_window = 4096  # Janela do peer
        self.cwnd = 1024  # Congestion window (simplificado)
        
        # Controle de tempo (RTT)
        self.estimated_rtt = 1.0
        self.dev_rtt = 0.5
        self.rtt_lock = threading.Lock()
        
        # Thread de recepção
        self.running = False
        self.receive_thread = None
        
        # Timer para retransmissão
        self.timer = None
        self.timer_lock = threading.Lock()
        
        # Dados recebidos prontos para aplicação
        self.app_data = []
        self.app_data_lock = threading.Lock()
        
        # Estatísticas
        self.segments_sent = 0
        self.segments_received = 0
        self.retransmissions = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.start_time = None
    
    def connect(self, dest_address):
        """
        Inicia conexão com three-way handshake (cliente)
        
        Args:
            dest_address: Tupla (host, port) do servidor
            
        Returns:
            True se conectado, False caso contrário
        """
        self.logger.info(f"Iniciando conexão com {dest_address}")
        self.peer_address = dest_address
        self.start_time = time.time()
        
        # Iniciar thread de recepção
        self._start_receive_thread()
        
        # Estado: SYN_SENT
        with self.state_lock:
            self.state = self.STATE_SYN_SENT
        
        # Enviar SYN
        syn_segment = TCPSegment(
            src_port=self.port,
            dst_port=dest_address[1],
            seq_num=self.seq_num,
            ack_num=0,
            flags=TCPSegment.FLAG_SYN,
            window_size=self.recv_window
        )
        
        self.logger.send(f"{syn_segment}")
        self._send_segment(syn_segment)
        self.segments_sent += 1
        
        # Aguardar SYN-ACK (timeout 5s)
        timeout = 5.0
        start = time.time()
        
        while time.time() - start < timeout:
            with self.state_lock:
                if self.state == self.STATE_ESTABLISHED:
                    self.logger.info("✓ Conexão estabelecida!")
                    return True
            time.sleep(0.1)
        
        self.logger.error("✗ Timeout ao conectar")
        self.state = self.STATE_CLOSED
        return False
    
    def listen(self):
        """Coloca socket em modo de escuta (servidor)"""
        self.logger.info(f"Escutando na porta {self.port}")
        
        with self.state_lock:
            self.state = self.STATE_LISTEN
        
        self._start_receive_thread()
    
    def accept(self, timeout=30.0):
        """
        Aceita conexão entrante (servidor)
        
        Args:
            timeout: Tempo máximo de espera
            
        Returns:
            True se conexão aceita, False se timeout
        """
        self.logger.info("Aguardando conexão...")
        
        start = time.time()
        while time.time() - start < timeout:
            with self.state_lock:
                if self.state == self.STATE_ESTABLISHED:
                    self.logger.info("✓ Conexão aceita!")
                    self.start_time = time.time()
                    return True
            time.sleep(0.1)
        
        self.logger.error("✗ Timeout aguardando conexão")
        return False
    
    def send(self, data):
        """
        Envia dados através da conexão
        
        Args:
            data: Bytes ou string a enviar
            
        Returns:
            Número de bytes enviados
        """
        if isinstance(data, str):
            data = data.encode()
        
        if self.state != self.STATE_ESTABLISHED:
            self.logger.error(f"Não é possível enviar: estado={self.state}")
            return 0
        
        self.bytes_sent += len(data)
        
        # Dividir dados em segmentos (MSS = 1024 bytes)
        mss = 1024
        offset = 0
        
        while offset < len(data):
            # Aguardar se a janela estiver cheia
            while self._get_unacked_bytes() >= min(self.send_window, self.cwnd):
                time.sleep(0.01)
            
            # Criar segmento
            chunk = data[offset:offset + mss]
            
            segment = TCPSegment(
                src_port=self.port,
                dst_port=self.peer_address[1],
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                flags=TCPSegment.FLAG_ACK,
                window_size=self.recv_window,
                data=chunk
            )
            
            with self.buffer_lock:
                self.send_buffer.append({
                    'seq': self.seq_num,
                    'data': chunk,
                    'time': time.time(),
                    'acked': False,
                    'segment': segment
                })
            
            self.logger.send(f"{segment}")
            self._send_segment(segment)
            self.segments_sent += 1
            
            self.seq_num += len(chunk)
            offset += len(chunk)
            
            # Iniciar timer se necessário
            self._start_retransmit_timer()
        
        return len(data)
    
    def recv(self, buffer_size=4096):
        """
        Recebe dados da conexão
        
        Args:
            buffer_size: Tamanho máximo a receber
            
        Returns:
            Bytes recebidos
        """
        if self.state not in [self.STATE_ESTABLISHED, self.STATE_CLOSE_WAIT]:
            return b''
        
        # Aguardar dados
        timeout = 10.0
        start = time.time()
        
        while time.time() - start < timeout:
            with self.app_data_lock:
                if self.app_data:
                    # Retornar dados disponíveis
                    data = b''.join(self.app_data[:buffer_size])
                    self.app_data = self.app_data[buffer_size:]
                    return data
            time.sleep(0.05)
        
        return b''
    
    def close(self):
        """Fecha a conexão com four-way handshake"""
        if self.state == self.STATE_CLOSED:
            return
        
        self.logger.info("Iniciando encerramento da conexão")
        
        if self.state == self.STATE_ESTABLISHED:
            # Enviar FIN
            with self.state_lock:
                self.state = self.STATE_FIN_WAIT_1
            
            fin_segment = TCPSegment(
                src_port=self.port,
                dst_port=self.peer_address[1],
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                flags=TCPSegment.FLAG_FIN | TCPSegment.FLAG_ACK,
                window_size=self.recv_window
            )
            
            self.logger.send(f"{fin_segment}")
            self._send_segment(fin_segment)
            self.seq_num += 1
            
            # Aguardar encerramento
            timeout = 5.0
            start = time.time()
            
            while time.time() - start < timeout:
                with self.state_lock:
                    if self.state == self.STATE_CLOSED:
                        break
                time.sleep(0.1)
        
        # Limpar recursos
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        
        with self.timer_lock:
            if self.timer:
                self.timer.cancel()
        
        self.udp_socket.close()
        self.logger.info("✓ Conexão encerrada")
    
    def _start_receive_thread(self):
        """Inicia thread de recepção de segmentos"""
        if not self.running:
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()
    
    def _receive_loop(self):
        """Loop principal de recepção"""
        self.udp_socket.settimeout(0.1)
        
        while self.running:
            try:
                segment_bytes, addr = self.udp_socket.recvfrom(4096)
                segment = TCPSegment.deserialize(segment_bytes)
                
                if segment is None or segment.is_corrupt():
                    continue
                
                self.segments_received += 1
                self.logger.receive(f"{segment}")
                
                # Processar segmento baseado no estado
                self._process_segment(segment, addr)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Erro no loop de recepção: {e}")
    
    def _process_segment(self, segment, addr):
        """Processa segmento recebido baseado no estado da conexão"""
        
        with self.state_lock:
            current_state = self.state
        
        # LISTEN: Aguardando SYN
        if current_state == self.STATE_LISTEN:
            if segment.has_flag(TCPSegment.FLAG_SYN):
                self.peer_address = addr
                self.peer_seq_num = segment.seq_num
                self.ack_num = segment.seq_num + 1
                self.send_window = segment.window_size
                
                # Enviar SYN-ACK
                syn_ack = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_SYN | TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                
                self.logger.send(f"{syn_ack}")
                self._send_segment(syn_ack)
                self.seq_num += 1
                
                with self.state_lock:
                    self.state = self.STATE_SYN_RECEIVED
        
        # SYN_SENT: Aguardando SYN-ACK
        elif current_state == self.STATE_SYN_SENT:
            if segment.has_flag(TCPSegment.FLAG_SYN) and segment.has_flag(TCPSegment.FLAG_ACK):
                self.peer_seq_num = segment.seq_num
                self.ack_num = segment.seq_num + 1
                self.send_window = segment.window_size
                
                # Enviar ACK final
                ack_segment = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num + 1,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                
                self.logger.send(f"{ack_segment}")
                self._send_segment(ack_segment)
                self.seq_num += 1
                
                with self.state_lock:
                    self.state = self.STATE_ESTABLISHED
        
        # SYN_RECEIVED: Aguardando ACK final
        elif current_state == self.STATE_SYN_RECEIVED:
            if segment.has_flag(TCPSegment.FLAG_ACK):
                with self.state_lock:
                    self.state = self.STATE_ESTABLISHED
        
        # ESTABLISHED: Transferência de dados
        elif current_state == self.STATE_ESTABLISHED:
            # Processar dados
            if len(segment.data) > 0:
                self._receive_data(segment)
            
            # Processar ACKs
            if segment.has_flag(TCPSegment.FLAG_ACK):
                self._process_ack(segment)
            
            # Processar FIN
            if segment.has_flag(TCPSegment.FLAG_FIN):
                self.ack_num = segment.seq_num + 1
                
                # Enviar ACK
                ack_segment = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                self._send_segment(ack_segment)
                
                with self.state_lock:
                    self.state = self.STATE_CLOSE_WAIT
                
                # Enviar FIN de volta
                time.sleep(0.1)
                fin_segment = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_FIN | TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                self._send_segment(fin_segment)
                
                with self.state_lock:
                    self.state = self.STATE_LAST_ACK
        
        # FIN_WAIT_1: Aguardando ACK do FIN
        elif current_state == self.STATE_FIN_WAIT_1:
            if segment.has_flag(TCPSegment.FLAG_ACK):
                with self.state_lock:
                    self.state = self.STATE_FIN_WAIT_2
            
            if segment.has_flag(TCPSegment.FLAG_FIN):
                self.ack_num = segment.seq_num + 1
                ack_segment = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                self._send_segment(ack_segment)
                
                with self.state_lock:
                    self.state = self.STATE_CLOSED
        
        # FIN_WAIT_2: Aguardando FIN
        elif current_state == self.STATE_FIN_WAIT_2:
            if segment.has_flag(TCPSegment.FLAG_FIN):
                self.ack_num = segment.seq_num + 1
                ack_segment = TCPSegment(
                    src_port=self.port,
                    dst_port=segment.src_port,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    flags=TCPSegment.FLAG_ACK,
                    window_size=self.recv_window
                )
                self._send_segment(ack_segment)
                
                with self.state_lock:
                    self.state = self.STATE_CLOSED
        
        # LAST_ACK: Aguardando ACK final
        elif current_state == self.STATE_LAST_ACK:
            if segment.has_flag(TCPSegment.FLAG_ACK):
                with self.state_lock:
                    self.state = self.STATE_CLOSED
    
    def _receive_data(self, segment):
        """Processa dados recebidos"""
        seq_num = segment.seq_num
        data = segment.data
        
        self.bytes_received += len(data)
        
        # Adicionar ao buffer
        with self.buffer_lock:
            self.recv_buffer[seq_num] = data
        
        # Entregar dados em ordem à aplicação
        self._deliver_in_order_data()
        
        # Enviar ACK
        self.ack_num = segment.seq_num + len(data)
        ack_segment = TCPSegment(
            src_port=self.port,
            dst_port=segment.src_port,
            seq_num=self.seq_num,
            ack_num=self.ack_num,
            flags=TCPSegment.FLAG_ACK,
            window_size=self.recv_window
        )
        
        self.logger.send(f"{ack_segment}")
        self._send_segment(ack_segment)
    
    def _deliver_in_order_data(self):
        """Entrega dados em ordem à aplicação"""
        with self.buffer_lock:
            expected_seq = self.peer_seq_num + 1
            
            while expected_seq in self.recv_buffer:
                data = self.recv_buffer.pop(expected_seq)
                
                with self.app_data_lock:
                    self.app_data.append(data)
                
                expected_seq += len(data)
                self.peer_seq_num = expected_seq - 1
    
    def _process_ack(self, segment):
        """Processa ACK recebido"""
        ack_num = segment.ack_num
        self.send_window = segment.window_size
        
        with self.buffer_lock:
            # Marcar segmentos como confirmados
            for entry in self.send_buffer:
                if not entry['acked'] and entry['seq'] < ack_num:
                    entry['acked'] = True
                    
                    # Atualizar estimativa de RTT
                    rtt_sample = time.time() - entry['time']
                    self._update_rtt(rtt_sample)
            
            # Remover segmentos confirmados
            self.send_buffer = [e for e in self.send_buffer if not e['acked']]
        
        # Parar timer se tudo foi confirmado
        if not self.send_buffer:
            with self.timer_lock:
                if self.timer:
                    self.timer.cancel()
                    self.timer = None
    
    def _send_segment(self, segment):
        """Envia segmento TCP através do UDP"""
        segment_bytes = segment.serialize()
        
        if self.channel:
            self.channel.send(segment_bytes, self.udp_socket, self.peer_address)
        else:
            self.udp_socket.sendto(segment_bytes, self.peer_address)
    
    def _calculate_timeout(self):
        """Calcula timeout baseado em RTT"""
        with self.rtt_lock:
            return self.estimated_rtt + 4 * self.dev_rtt
    
    def _update_rtt(self, sample_rtt):
        """Atualiza estimativa de RTT"""
        with self.rtt_lock:
            self.estimated_rtt = 0.875 * self.estimated_rtt + 0.125 * sample_rtt
            self.dev_rtt = 0.75 * self.dev_rtt + 0.25 * abs(sample_rtt - self.estimated_rtt)
    
    def _start_retransmit_timer(self):
        """Inicia timer de retransmissão"""
        with self.timer_lock:
            if self.timer is None and self.send_buffer:
                timeout = self._calculate_timeout()
                self.timer = threading.Timer(timeout, self._on_retransmit_timeout)
                self.timer.daemon = True
                self.timer.start()
    
    def _on_retransmit_timeout(self):
        """Callback de timeout - retransmite segmentos não confirmados"""
        self.logger.timeout("Retransmitindo segmentos não confirmados")
        
        with self.buffer_lock:
            for entry in self.send_buffer:
                if not entry['acked']:
                    self.logger.retransmit(f"{entry['segment']}")
                    self._send_segment(entry['segment'])
                    self.retransmissions += 1
                    entry['time'] = time.time()
        
        # Reiniciar timer
        with self.timer_lock:
            self.timer = None
        self._start_retransmit_timer()
    
    def _get_unacked_bytes(self):
        """Retorna número de bytes não confirmados"""
        with self.buffer_lock:
            return sum(len(e['data']) for e in self.send_buffer if not e['acked'])
    
    def get_statistics(self):
        """Retorna estatísticas da conexão"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            'state': self.state,
            'segments_sent': self.segments_sent,
            'segments_received': self.segments_received,
            'retransmissions': self.retransmissions,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'estimated_rtt': self.estimated_rtt,
            'elapsed_time': elapsed,
            'throughput_bps': (self.bytes_sent / elapsed) if elapsed > 0 else 0
        }
