"""
Sistema de logging para protocolos RDT e TCP
"""
import logging
import sys
from datetime import datetime


class ProtocolLogger:
    """Logger customizado para protocolos de rede"""
    
    def __init__(self, name, level=logging.INFO, log_file=None):
        """
        Inicializa o logger
        
        Args:
            name: Nome do logger (ex: 'RDT2.0-Sender')
            level: Nível de log (DEBUG, INFO, WARNING, ERROR)
            log_file: Arquivo para salvar logs (opcional)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove handlers existentes
        self.logger.handlers = []
        
        # Formato do log
        formatter = logging.Formatter(
            '[%(asctime)s] %(name)s %(levelname)s: %(message)s',
            datefmt = '%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Handler para arquivo (opcional)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def send(self, packet_info):
        """Log de envio de pacote"""
        self.logger.info(f"SEND: {packet_info}")
    
    def receive(self, packet_info):
        """Log de recebimento de pacote"""
        self.logger.info(f"RECV: {packet_info}")
    
    def timeout(self, packet_info):
        """Log de timeout"""
        self.logger.warning(f"TIMEOUT: {packet_info}")
    
    def retransmit(self, packet_info):
        """Log de retransmissão"""
        self.logger.warning(f"RETRANSMIT: {packet_info}")
    
    def corrupt(self, packet_info):
        """Log de pacote corrompido"""
        self.logger.error(f"CORRUPT: {packet_info}")
    
    def state_change(self, old_state, new_state):
        """Log de mudança de estado"""
        self.logger.info(f"STATE: {old_state} -> {new_state}")
    
    def deliver(self, data_info):
        """Log de entrega de dados à aplicação"""
        self.logger.info(f"DELIVER: {data_info}")
    
    def debug(self, message):
        """Log de debug"""
        self.logger.debug(message)
    
    def info(self, message):
        """Log de informação"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log de aviso"""
        self.logger.warning(message)
    
    def error(self, message):
        """Log de erro"""
        self.logger.error(message)


def setup_logging(level=logging.INFO):
    """
    Configura logging global para o projeto
    
    Args:
        level: Nível de log padrão
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
