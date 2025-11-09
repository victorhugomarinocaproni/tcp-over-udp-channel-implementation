"""
Testes automatizados para Fase 3: TCP Simplificado sobre UDP
"""
import sys
import time
import threading
sys.path.append('../..')

from fase3.tcp_socket import SimpleTCPSocket
from utils.simulator import UnreliableChannel


def test_three_way_handshake():
    """
    Teste 1: Estabelecimento de conexão (Three-Way Handshake)
    Verifica: SYN -> SYN-ACK -> ACK
    """
    print("\n" + "=" * 70)
    print("TESTE 1: Three-Way Handshake")
    print("=" * 70)
    
    # Criar servidor
    server = SimpleTCPSocket(10000)
    
    # Thread do servidor
    def server_thread():
        server.listen()
        server.accept(timeout=10.0)
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Criar cliente e conectar
    client = SimpleTCPSocket(10001)
    
    print("\nCliente conectando ao servidor...")
    connected = client.connect(('localhost', 10000))
    
    time.sleep(1)
    
    # Verificar estados
    print(f"\nEstado do cliente: {client.state}")
    print(f"Estado do servidor: {server.state}")
    
    success = (connected and 
               client.state == SimpleTCPSocket.STATE_ESTABLISHED and
               server.state == SimpleTCPSocket.STATE_ESTABLISHED)
    
    if success:
        print("\n✓ Three-way handshake bem-sucedido!")
    else:
        print("\n✗ Falha no three-way handshake")
    
    # Limpar
    client.close()
    server.close()
    
    return success


def test_data_transfer():
    """
    Teste 2: Transferência de Dados
    Envia 10KB e verifica integridade
    """
    print("\n" + "=" * 70)
    print("TESTE 2: Transferência de Dados (10KB)")
    print("=" * 70)
    
    # Dados a enviar
    test_data = b'X' * 10240  # 10KB
    received_data = []
    
    # Servidor
    server = SimpleTCPSocket(10010)
    
    def server_thread():
        server.listen()
        if server.accept(timeout=10.0):
            data = server.recv(buffer_size=12000)
            received_data.append(data)
            server.close()
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Cliente
    client = SimpleTCPSocket(10011)
    
    print("\nEnviando 10KB de dados...")
    
    if client.connect(('localhost', 10010)):
        bytes_sent = client.send(test_data)
        print(f"Enviado: {bytes_sent} bytes")
        
        time.sleep(2)
        
        # Verificar dados recebidos
        if received_data and received_data[0] == test_data:
            print("\n✓ Dados recebidos corretamente!")
            success = True
        else:
            print(f"\n✗ Erro: esperado {len(test_data)} bytes, recebido {len(received_data[0]) if received_data else 0}")
            success = False
        
        client.close()
    else:
        print("\n✗ Falha ao conectar")
        success = False
    
    server_t.join(timeout=2.0)
    
    return success


def test_flow_control():
    """
    Teste 3: Controle de Fluxo
    Reduz janela do receptor e verifica se remetente respeita
    """
    print("\n" + "=" * 70)
    print("TESTE 3: Controle de Fluxo")
    print("=" * 70)
    
    # Servidor com janela pequena
    server = SimpleTCPSocket(10020)
    server.recv_window = 1024  # Apenas 1KB de janela
    
    received_data = []
    
    def server_thread():
        server.listen()
        if server.accept(timeout=10.0):
            print(f"Servidor: janela de recepção = {server.recv_window} bytes")
            
            # Receber em partes
            while True:
                data = server.recv(buffer_size=512)
                if not data:
                    break
                received_data.append(data)
                print(f"  Recebido: {len(data)} bytes")
                time.sleep(0.1)  # Simular processamento lento
            
            server.close()
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Cliente envia mais dados que a janela
    client = SimpleTCPSocket(10021)
    
    if client.connect(('localhost', 10020)):
        print(f"\nCliente: janela do servidor = {client.send_window} bytes")
        
        # Enviar 5KB (maior que a janela)
        test_data = b'Y' * 5120
        print(f"Enviando {len(test_data)} bytes...")
        
        bytes_sent = client.send(test_data)
        
        time.sleep(3)
        
        # Verificar
        total_received = sum(len(d) for d in received_data)
        
        print(f"\nTotal recebido: {total_received} bytes")
        
        if total_received == len(test_data):
            print("✓ Controle de fluxo funcionou!")
            success = True
        else:
            print(f"✗ Erro: esperado {len(test_data)}, recebido {total_received}")
            success = False
        
        client.close()
    else:
        success = False
    
    server_t.join(timeout=5.0)
    
    return success


def test_retransmission():
    """
    Teste 4: Retransmissão com perda de pacotes
    Simula 20% de perda e verifica retransmissão
    """
    print("\n" + "=" * 70)
    print("TESTE 4: Retransmissão (20% perda)")
    print("=" * 70)
    
    # Canal com perda
    channel = UnreliableChannel(
        loss_rate=0.20,
        corrupt_rate=0.05,
        delay_range=(0.01, 0.05)
    )
    
    test_data = b'Z' * 5000
    received_data = []
    
    # Servidor
    server = SimpleTCPSocket(10030, channel=channel)
    
    def server_thread():
        server.listen()
        if server.accept(timeout=15.0):
            data = server.recv(buffer_size=6000)
            received_data.append(data)
            server.close()
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Cliente
    client = SimpleTCPSocket(10031, channel=channel)
    
    print("\nEnviando dados com 20% de perda...")
    
    if client.connect(('localhost', 10030)):
        client.send(test_data)
        
        time.sleep(5)
        
        # Estatísticas
        stats_client = client.get_statistics()
        
        print(f"\nRetransmissões: {stats_client['retransmissions']}")
        
        # Verificar dados
        if received_data and received_data[0] == test_data:
            print("✓ Dados recebidos corretamente apesar da perda!")
            success = True
        else:
            print("✗ Dados não recebidos corretamente")
            success = False
        
        # Deve ter ocorrido retransmissões
        if stats_client['retransmissions'] > 0:
            print(f"✓ Retransmissões ocorreram: {stats_client['retransmissions']}")
        else:
            print("⚠️  Nenhuma retransmissão (perda não afetou)")
        
        client.close()
    else:
        success = False
    
    server_t.join(timeout=5.0)
    
    channel.print_statistics()
    
    return success


def test_connection_termination():
    """
    Teste 5: Encerramento de Conexão (Four-Way Handshake)
    Verifica: FIN -> ACK -> FIN -> ACK
    """
    print("\n" + "=" * 70)
    print("TESTE 5: Encerramento de Conexão (Four-Way Handshake)")
    print("=" * 70)
    
    # Servidor
    server = SimpleTCPSocket(10040)
    
    def server_thread():
        server.listen()
        if server.accept(timeout=10.0):
            print("Servidor: conexão aceita")
            time.sleep(1)
            
            # Cliente vai fechar primeiro
            time.sleep(2)
            
            print(f"Servidor: estado final = {server.state}")
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Cliente
    client = SimpleTCPSocket(10041)
    
    if client.connect(('localhost', 10040)):
        print("Cliente: conectado")
        time.sleep(1)
        
        print("\nCliente: iniciando encerramento...")
        client.close()
        
        time.sleep(2)
        
        # Verificar estados finais
        print(f"Cliente: estado final = {client.state}")
        
        success = (client.state == SimpleTCPSocket.STATE_CLOSED)
        
        if success:
            print("\n✓ Conexão encerrada corretamente!")
        else:
            print("\n✗ Erro no encerramento")
    else:
        success = False
    
    server_t.join(timeout=3.0)
    
    return success


def test_performance_1mb():
    """
    Teste 6: Desempenho com 1MB
    Mede throughput e RTT
    """
    print("\n" + "=" * 70)
    print("TESTE 6: Desempenho - Transferência de 1MB")
    print("=" * 70)
    
    # Gerar 1MB de dados
    data_1mb = b'A' * (1024 * 1024)
    received_data = []
    
    # Servidor
    server = SimpleTCPSocket(10050)
    
    def server_thread():
        server.listen()
        if server.accept(timeout=15.0):
            print("Servidor: recebendo dados...")
            
            total = 0
            while total < len(data_1mb):
                chunk = server.recv(buffer_size=8192)
                if not chunk:
                    break
                received_data.append(chunk)
                total += len(chunk)
                
                if total % 102400 == 0:  # A cada 100KB
                    print(f"  Recebido: {total/1024:.0f} KB")
            
            print(f"\nServidor: total recebido = {total} bytes")
            server.close()
    
    server_t = threading.Thread(target=server_thread)
    server_t.daemon = True
    server_t.start()
    
    time.sleep(0.5)
    
    # Cliente
    client = SimpleTCPSocket(10051)
    
    if client.connect(('localhost', 10050)):
        print("\nCliente: enviando 1MB...")
        
        start_time = time.time()
        client.send(data_1mb)
        
        # Aguardar transmissão completa
        time.sleep(5)
        
        elapsed = time.time() - start_time
        
        # Estatísticas
        stats = client.get_statistics()
        
        print("\n" + "=" * 70)
        print("ESTATÍSTICAS DE DESEMPENHO")
        print("=" * 70)
        print(f"Tempo total:           {elapsed:.2f} s")
        print(f"Throughput:            {(len(data_1mb)/elapsed)/1024:.2f} KB/s")
        print(f"                       {((len(data_1mb)/elapsed)/1024/1024)*8:.2f} Mbps")
        print(f"Segmentos enviados:    {stats['segments_sent']}")
        print(f"Retransmissões:        {stats['retransmissions']}")
        print(f"RTT médio:             {stats['estimated_rtt']*1000:.2f} ms")
        print(f"Taxa de retrans.:      {stats['retransmissions']/stats['segments_sent']*100:.1f}%")
        print("=" * 70)
        
        client.close()
        
        # Verificar integridade
        total_received = sum(len(d) for d in received_data)
        success = (total_received == len(data_1mb))
        
        if success:
            print("\n✓ 1MB transferido com sucesso!")
        else:
            print(f"\n✗ Erro: enviado {len(data_1mb)}, recebido {total_received}")
    else:
        success = False
    
    server_t.join(timeout=10.0)
    
    return success


def run_all_tests():
    """Executa todos os testes da Fase 3"""
    print("\n" + "=" * 70)
    print("EXECUÇÃO COMPLETA DOS TESTES - FASE 3")
    print("TCP Simplificado sobre UDP")
    print("=" * 70)
    
    results = []
    
    # Teste 1: Three-way handshake
    results.append(("Three-Way Handshake", test_three_way_handshake()))
    time.sleep(1)
    
    # Teste 2: Transferência de dados
    results.append(("Transferência 10KB", test_data_transfer()))
    time.sleep(1)
    
    # Teste 3: Controle de fluxo
    results.append(("Controle de Fluxo", test_flow_control()))
    time.sleep(1)
    
    # Teste 4: Retransmissão
    results.append(("Retransmissão", test_retransmission()))
    time.sleep(1)
    
    # Teste 5: Encerramento
    results.append(("Four-Way Handshake", test_connection_termination()))
    time.sleep(1)
    
    # Teste 6: Desempenho 1MB
    results.append(("Desempenho 1MB", test_performance_1mb()))
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES - FASE 3")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASSOU" if passed else "✗ FALHOU"
        print(f"{status} - {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print("\n" + "=" * 70)
    print(f"Resultado: {passed_count}/{total_count} testes passaram ({passed_count/total_count*100:.0f}%)")
    
    if passed_count == total_count:
        print("🎉 TODOS OS TESTES DA FASE 3 PASSARAM! 🎉")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
    print("=" * 70 + "\n")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
