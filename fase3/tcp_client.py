"""
Cliente TCP Simplificado
Exemplo de aplicação cliente que usa SimpleTCPSocket
"""
import sys
import time
sys.path.append('../..')

from fase3.tcp_socket import SimpleTCPSocket
from utils.simulator import UnreliableChannel


def run_client(server_address, data_to_send=None, use_channel=False):
    """
    Executa cliente TCP simplificado
    
    Args:
        server_address: Tupla (host, port) do servidor
        data_to_send: Dados a enviar (string ou lista de strings)
        use_channel: Se True, usa canal não confiável
    """
    print("=" * 70)
    print("CLIENTE TCP SIMPLIFICADO")
    print("=" * 70)
    
    # Criar canal (opcional)
    channel = None
    if use_channel:
        channel = UnreliableChannel(
            loss_rate=0.05,
            corrupt_rate=0.02,
            delay_range=(0.01, 0.05)
        )
        print("\n⚠️  Usando canal não confiável (5% perda, 2% corrupção)")
    
    # Criar socket cliente
    client = SimpleTCPSocket(9000, channel=channel)
    
    print(f"\n[1] Cliente iniciado na porta {client.port}")
    
    try:
        # Conectar ao servidor
        print(f"[2] Conectando a {server_address}...")
        
        if not client.connect(server_address):
            print("\n✗ Falha ao conectar")
            return
        
        print(f"[3] Conectado ao servidor!")
        print(f"    Estado: {client.state}")
        
        # Preparar dados para enviar
        if data_to_send is None:
            # Dados padrão
            data_to_send = [
                f"Mensagem {i}: Esta é uma mensagem de teste do cliente TCP simplificado."
                for i in range(10)
            ]
        elif isinstance(data_to_send, str):
            data_to_send = [data_to_send]
        
        # Enviar dados
        print(f"\n[4] Enviando {len(data_to_send)} mensagens...")
        
        total_sent = 0
        
        for i, msg in enumerate(data_to_send):
            bytes_sent = client.send(msg)
            total_sent += bytes_sent
            print(f"    {i+1}. Enviado: {bytes_sent} bytes")
            time.sleep(0.05)  # Pequeno delay entre mensagens
        
        # Enviar marcador de fim
        client.send("FIM")
        print("    (marcador de fim enviado)")
        
        print(f"\n[5] Total enviado: {total_sent} bytes")
        
        # Receber resposta do servidor
        print("\n[6] Aguardando resposta do servidor...")
        
        response = client.recv(buffer_size=4096)
        
        if response:
            print(f"[7] Resposta recebida: {response.decode()}")
        else:
            print("[7] Nenhuma resposta recebida")
        
        # Aguardar um pouco
        time.sleep(1)
        
        # Fechar conexão
        print("\n[8] Encerrando conexão...")
        client.close()
        
        # Estatísticas
        stats = client.get_statistics()
        
        print("\n" + "=" * 70)
        print("ESTATÍSTICAS DO CLIENTE")
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
        
        print("\n✓ Cliente encerrado com sucesso!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        client.close()
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        import traceback
        traceback.print_exc()
        client.close()


def run_echo_client(server_address):
    """
    Cliente interativo para servidor echo
    
    Args:
        server_address: Tupla (host, port) do servidor
    """
    print("=" * 70)
    print("CLIENTE ECHO TCP (Interativo)")
    print("=" * 70)
    
    client = SimpleTCPSocket(9000)
    
    print(f"\nConectando a {server_address}...")
    
    if not client.connect(server_address):
        print("✗ Falha ao conectar")
        return
    
    print("✓ Conectado! Digite mensagens (ou 'sair' para encerrar)\n")
    
    try:
        while True:
            # Ler mensagem do usuário
            msg = input("→ Você: ")
            
            if not msg:
                continue
            
            # Enviar
            client.send(msg)
            
            if msg.lower() == 'sair':
                break
            
            # Receber echo
            response = client.recv(buffer_size=1024)
            
            if response:
                print(f"← Echo: {response.decode()}\n")
            else:
                print("(sem resposta)\n")
        
        client.close()
        print("\n✓ Desconectado")
        
    except KeyboardInterrupt:
        print("\n\nInterrompido")
        client.close()
    except Exception as e:
        print(f"\nErro: {e}")
        client.close()


def send_file(server_address, file_path):
    """
    Envia um arquivo para o servidor
    
    Args:
        server_address: Tupla (host, port) do servidor
        file_path: Caminho do arquivo a enviar
    """
    print("=" * 70)
    print("TRANSFERÊNCIA DE ARQUIVO TCP")
    print("=" * 70)
    
    try:
        # Ler arquivo
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        print(f"\nArquivo: {file_path}")
        print(f"Tamanho: {len(file_data)} bytes ({len(file_data)/1024:.2f} KB)")
        
        # Conectar
        client = SimpleTCPSocket(9000)
        
        print(f"\nConectando a {server_address}...")
        
        if not client.connect(server_address):
            print("✗ Falha ao conectar")
            return
        
        print("✓ Conectado!")
        
        # Enviar arquivo
        print("\nEnviando arquivo...")
        start_time = time.time()
        
        client.send(file_data)
        
        elapsed = time.time() - start_time
        
        print(f"✓ Arquivo enviado em {elapsed:.2f}s")
        print(f"  Throughput: {(len(file_data)/elapsed)/1024:.2f} KB/s")
        
        # Aguardar confirmação
        response = client.recv(buffer_size=1024)
        if response:
            print(f"\nServidor: {response.decode()}")
        
        client.close()
        
        # Estatísticas
        stats = client.get_statistics()
        print(f"\nRetransmissões: {stats['retransmissions']}")
        print(f"RTT médio: {stats['estimated_rtt']*1000:.2f} ms")
        
    except FileNotFoundError:
        print(f"✗ Arquivo não encontrado: {file_path}")
    except Exception as e:
        print(f"✗ Erro: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cliente TCP Simplificado')
    parser.add_argument('--host', type=str, default='localhost',
                       help='Endereço do servidor (padrão: localhost)')
    parser.add_argument('--port', type=int, default=8000,
                       help='Porta do servidor (padrão: 8000)')
    parser.add_argument('--echo', action='store_true',
                       help='Modo echo interativo')
    parser.add_argument('--file', type=str,
                       help='Caminho do arquivo a enviar')
    parser.add_argument('--unreliable', action='store_true',
                       help='Usar canal não confiável (para testes)')
    parser.add_argument('--messages', type=int, default=10,
                       help='Número de mensagens a enviar (padrão: 10)')
    
    args = parser.parse_args()
    
    server_addr = (args.host, args.port)
    
    if args.echo:
        run_echo_client(server_addr)
    elif args.file:
        send_file(server_addr, args.file)
    else:
        # Modo padrão: enviar mensagens de teste
        messages = [
            f"Mensagem {i}: Testando o protocolo TCP simplificado sobre UDP!"
            for i in range(args.messages)
        ]
        run_client(server_addr, data_to_send=messages, use_channel=args.unreliable)
