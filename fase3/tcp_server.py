"""
Servidor TCP Simplificado
Exemplo de aplicação que usa SimpleTCPSocket
"""
import sys
import time
sys.path.append('../..')

from fase3.tcp_socket import SimpleTCPSocket
from utils.simulator import UnreliableChannel


def run_server(port=8000, use_channel=False):
    """
    Executa servidor TCP simplificado
    
    Args:
        port: Porta para escutar
        use_channel: Se True, usa canal não confiável para testes
    """
    print("=" * 70)
    print("SERVIDOR TCP SIMPLIFICADO")
    print("=" * 70)
    
    # Criar canal (opcional, para testes)
    channel = None
    if use_channel:
        channel = UnreliableChannel(
            loss_rate=0.05,
            corrupt_rate=0.02,
            delay_range=(0.01, 0.05)
        )
        print("\n⚠️  Usando canal não confiável (5% perda, 2% corrupção)")
    
    # Criar socket
    server = SimpleTCPSocket(port, channel=channel)
    
    print(f"\n[1] Servidor iniciado na porta {port}")
    
    try:
        # Colocar em modo de escuta
        server.listen()
        print("[2] Escutando por conexões...")
        
        # Aceitar conexão
        if not server.accept(timeout=60.0):
            print("\n✗ Timeout aguardando conexão")
            return
        
        print(f"[3] Conexão estabelecida com {server.peer_address}")
        print(f"    Estado: {server.state}")
        
        # Receber dados
        print("\n[4] Recebendo dados...")
        
        total_received = 0
        messages_received = []
        
        # Receber múltiplas mensagens
        while True:
            data = server.recv(buffer_size=4096)
            
            if not data:
                break
            
            total_received += len(data)
            messages_received.append(data)
            
            print(f"    Recebido: {len(data)} bytes")
            
            # Se recebeu mensagem de fim
            if b"FIM" in data:
                print("    (mensagem de fim detectada)")
                break
        
        print(f"\n[5] Total recebido: {total_received} bytes em {len(messages_received)} mensagens")
        
        # Exibir algumas mensagens
        print("\n    Primeiras mensagens:")
        for i, msg in enumerate(messages_received[:5]):
            try:
                decoded = msg.decode()
                print(f"      {i+1}. {decoded[:50]}...")
            except:
                print(f"      {i+1}. (dados binários, {len(msg)} bytes)")
        
        # Enviar resposta
        print("\n[6] Enviando resposta...")
        response = f"Servidor recebeu {total_received} bytes com sucesso!"
        server.send(response)
        
        print("[7] Resposta enviada")
        
        # Aguardar um pouco antes de fechar
        time.sleep(1)
        
        # Fechar conexão
        print("\n[8] Encerrando conexão...")
        server.close()
        
        # Estatísticas
        stats = server.get_statistics()
        
        print("\n" + "=" * 70)
        print("ESTATÍSTICAS DO SERVIDOR")
        print("=" * 70)
        print(f"Segmentos enviados:    {stats['segments_sent']}")
        print(f"Segmentos recebidos:   {stats['segments_received']}")
        print(f"Retransmissões:        {stats['retransmissions']}")
        print(f"Bytes enviados:        {stats['bytes_sent']}")
        print(f"Bytes recebidos:       {stats['bytes_received']}")
        print(f"RTT estimado:          {stats['estimated_rtt']*1000:.2f} ms")
        print(f"Tempo total:           {stats['elapsed_time']:.2f} s")
        print(f"Throughput:            {stats['throughput_bps']/1024:.2f} KB/s")
        print("=" * 70)
        
        if channel:
            channel.print_statistics()
        
        print("\n✓ Servidor encerrado com sucesso!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        server.close()
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        server.close()


def run_echo_server(port=8000):
    """
    Servidor echo: responde com os mesmos dados recebidos
    
    Args:
        port: Porta para escutar
    """
    print("=" * 70)
    print("SERVIDOR ECHO TCP")
    print("=" * 70)
    
    server = SimpleTCPSocket(port)
    
    print(f"\nServidor Echo iniciado na porta {port}")
    
    try:
        server.listen()
        print("Aguardando conexões...\n")
        
        if not server.accept(timeout=60.0):
            print("Timeout")
            return
        
        print(f"✓ Cliente conectado: {server.peer_address}\n")
        
        # Loop echo
        while True:
            data = server.recv(buffer_size=1024)
            
            if not data:
                print("Cliente desconectou")
                break
            
            print(f"← Recebido: {data.decode()}")
            
            # Enviar de volta
            server.send(data)
            print(f"→ Echo enviado\n")
            
            if b"sair" in data.lower():
                print("Comando de saída recebido")
                break
        
        server.close()
        print("\n✓ Conexão encerrada")
        
    except KeyboardInterrupt:
        print("\n\nInterrompido")
        server.close()
    except Exception as e:
        print(f"\nErro: {e}")
        server.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Servidor TCP Simplificado')
    parser.add_argument('--port', type=int, default=8000, 
                       help='Porta para escutar (padrão: 8000)')
    parser.add_argument('--echo', action='store_true',
                       help='Modo echo (repete dados recebidos)')
    parser.add_argument('--unreliable', action='store_true',
                       help='Usar canal não confiável (para testes)')
    
    args = parser.parse_args()
    
    if args.echo:
        run_echo_server(args.port)
    else:
        run_server(args.port, use_channel=args.unreliable)
