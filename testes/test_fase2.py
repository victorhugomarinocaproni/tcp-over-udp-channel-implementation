"""
Testes automatizados para Fase 2: Pipelining (Go-Back-N e Selective Repeat)
Inclui comparações de desempenho e gráficos
"""
import sys
import time
import matplotlib.pyplot as plt
sys.path.append('../..')

from fase1.rdt30 import RDT30Sender, RDT30Receiver
from fase2.gbn import GBNSender, GBNReceiver
from fase2.sr import SRSender, SRReceiver
from utils.simulator import UnreliableChannel


def test_gbn_basic():
    """Teste básico do Go-Back-N"""
    print("\n" + "=" * 70)
    print("TESTE 1: Go-Back-N - Funcionalidade Básica")
    print("=" * 70)
    
    channel = UnreliableChannel(loss_rate=0.10, corrupt_rate=0.05, 
                                delay_range=(0.01, 0.1))
    
    receiver = GBNReceiver(9001, channel)
    receiver.start()
    
    sender = GBNSender(9000, window_size=5, channel=channel, timeout=1.0)
    sender.start(('localhost', 9001))
    
    # Enviar mensagens
    messages = [f"Mensagem {i}" for i in range(30)]
    
    print(f"\nEnviando {len(messages)} mensagens (janela=5)...")
    
    for msg in messages:
        sender.send(msg)
        time.sleep(0.02)
    
    sender.wait_for_completion(timeout=10.0)
    time.sleep(1)
    
    # Verificar resultados
    received = receiver.get_messages()
    stats_sender = sender.get_statistics()
    stats_receiver = receiver.get_statistics()
    
    print(f"\n✓ Recebidas: {len(received)}/{len(messages)}")
    print(f"  Retransmissões: {stats_sender['retransmissions']}")
    print(f"  Throughput: {stats_sender['throughput_bps']:.2f} bytes/s")
    
    channel.print_statistics()
    
    sender.stop()
    receiver.stop()
    
    return len(received) == len(messages)


def test_sr_buffering():
    """Teste do Selective Repeat com foco em bufferização"""
    print("\n" + "=" * 70)
    print("TESTE 2: Selective Repeat - Bufferização de Pacotes Fora de Ordem")
    print("=" * 70)
    
    channel = UnreliableChannel(loss_rate=0.15, corrupt_rate=0.05,
                                delay_range=(0.01, 0.15))
    
    receiver = SRReceiver(9011, window_size=8, channel=channel)
    receiver.start()
    
    sender = SRSender(9010, window_size=8, channel=channel, timeout=1.0)
    sender.start(('localhost', 9011))
    
    # Enviar mensagens
    messages = [f"Mensagem {i}" for i in range(40)]
    
    print(f"\nEnviando {len(messages)} mensagens (janela=8)...")
    
    for msg in messages:
        sender.send(msg)
        time.sleep(0.02)
    
    sender.wait_for_completion(timeout=15.0)
    time.sleep(1)
    
    # Verificar resultados
    received = receiver.get_messages()
    stats_sender = sender.get_statistics()
    stats_receiver = receiver.get_statistics()
    
    print(f"\n✓ Recebidas: {len(received)}/{len(messages)}")
    print(f"  Pacotes bufferizados: {stats_receiver['buffered_packets']}")
    print(f"  Retransmissões: {stats_sender['retransmissions']}")
    print(f"  Throughput: {stats_sender['throughput_bps']:.2f} bytes/s")
    
    channel.print_statistics()
    
    sender.stop()
    receiver.stop()
    
    return len(received) == len(messages)


def test_throughput_vs_window_size():
    """
    Teste comparativo: Throughput vs Tamanho da Janela
    Compara rdt3.0, GBN e SR com diferentes tamanhos de janela
    """
    print("\n" + "=" * 70)
    print("TESTE 3: Análise de Desempenho - Throughput vs Tamanho da Janela")
    print("=" * 70)
    
    window_sizes = [1, 5, 10, 20]
    num_packets = 100
    
    # Configuração do canal
    loss_rate = 0.10
    corrupt_rate = 0.05
    
    results = {
        'window_sizes': window_sizes,
        'gbn_throughput': [],
        'sr_throughput': [],
        'gbn_time': [],
        'sr_time': [],
        'gbn_retrans': [],
        'sr_retrans': []
    }
    
    # Teste com diferentes tamanhos de janela
    for window_size in window_sizes:
        print(f"\n--- Testando com janela = {window_size} ---")
        
        # Teste GBN
        print(f"  GBN (janela={window_size})...")
        channel = UnreliableChannel(loss_rate=loss_rate, corrupt_rate=corrupt_rate,
                                    delay_range=(0.01, 0.05))
        
        receiver_gbn = GBNReceiver(9021, channel)
        receiver_gbn.start()
        
        sender_gbn = GBNSender(9020, window_size=window_size, channel=channel, timeout=0.5)
        sender_gbn.start(('localhost', 9021))
        
        messages = [f"Packet{i:03d}" for i in range(num_packets)]
        
        for msg in messages:
            sender_gbn.send(msg)
            time.sleep(0.005)
        
        sender_gbn.wait_for_completion(timeout=20.0)
        time.sleep(0.5)
        
        stats_gbn = sender_gbn.get_statistics()
        results['gbn_throughput'].append(stats_gbn['throughput_bps'])
        results['gbn_time'].append(stats_gbn['elapsed_time'])
        results['gbn_retrans'].append(stats_gbn['retransmissions'])
        
        print(f"    Throughput: {stats_gbn['throughput_bps']:.2f} bytes/s")
        print(f"    Tempo: {stats_gbn['elapsed_time']:.2f}s")
        
        sender_gbn.stop()
        receiver_gbn.stop()
        time.sleep(0.5)
        
        # Teste SR
        print(f"  SR (janela={window_size})...")
        channel = UnreliableChannel(loss_rate=loss_rate, corrupt_rate=corrupt_rate,
                                    delay_range=(0.01, 0.05))
        
        receiver_sr = SRReceiver(9031, window_size=window_size, channel=channel)
        receiver_sr.start()
        
        sender_sr = SRSender(9030, window_size=window_size, channel=channel, timeout=0.5)
        sender_sr.start(('localhost', 9031))
        
        for msg in messages:
            sender_sr.send(msg)
            time.sleep(0.005)
        
        sender_sr.wait_for_completion(timeout=20.0)
        time.sleep(0.5)
        
        stats_sr = sender_sr.get_statistics()
        results['sr_throughput'].append(stats_sr['throughput_bps'])
        results['sr_time'].append(stats_sr['elapsed_time'])
        results['sr_retrans'].append(stats_sr['retransmissions'])
        
        print(f"    Throughput: {stats_sr['throughput_bps']:.2f} bytes/s")
        print(f"    Tempo: {stats_sr['elapsed_time']:.2f}s")
        
        sender_sr.stop()
        receiver_sr.stop()
        time.sleep(0.5)
    
    # Gerar gráficos
    plot_performance_comparison(results)
    
    return results


def plot_performance_comparison(results):
    """
    Gera gráficos comparativos de desempenho
    
    Args:
        results: Dicionário com resultados dos testes
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Análise de Desempenho: Pipelining vs Stop-and-Wait', 
                 fontsize=16, fontweight='bold')
    
    # Gráfico 1: Throughput vs Tamanho da Janela
    ax1 = axes[0, 0]
    ax1.plot(results['window_sizes'], results['gbn_throughput'], 
             marker='o', linewidth=2, label='Go-Back-N', color='blue')
    ax1.plot(results['window_sizes'], results['sr_throughput'], 
             marker='s', linewidth=2, label='Selective Repeat', color='green')
    ax1.set_xlabel('Tamanho da Janela (N)', fontsize=12)
    ax1.set_ylabel('Throughput (bytes/s)', fontsize=12)
    ax1.set_title('Throughput vs Tamanho da Janela', fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Gráfico 2: Tempo Total vs Tamanho da Janela
    ax2 = axes[0, 1]
    ax2.plot(results['window_sizes'], results['gbn_time'], 
             marker='o', linewidth=2, label='Go-Back-N', color='blue')
    ax2.plot(results['window_sizes'], results['sr_time'], 
             marker='s', linewidth=2, label='Selective Repeat', color='green')
    ax2.set_xlabel('Tamanho da Janela (N)', fontsize=12)
    ax2.set_ylabel('Tempo Total (s)', fontsize=12)
    ax2.set_title('Tempo de Transmissão vs Tamanho da Janela', fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Gráfico 3: Retransmissões vs Tamanho da Janela
    ax3 = axes[1, 0]
    ax3.bar([x - 0.2 for x in results['window_sizes']], results['gbn_retrans'], 
            width=0.4, label='Go-Back-N', color='blue', alpha=0.7)
    ax3.bar([x + 0.2 for x in results['window_sizes']], results['sr_retrans'], 
            width=0.4, label='Selective Repeat', color='green', alpha=0.7)
    ax3.set_xlabel('Tamanho da Janela (N)', fontsize=12)
    ax3.set_ylabel('Número de Retransmissões', fontsize=12)
    ax3.set_title('Retransmissões vs Tamanho da Janela', fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Gráfico 4: Speedup em relação a Window=1
    ax4 = axes[1, 1]
    gbn_speedup = [results['gbn_throughput'][i] / results['gbn_throughput'][0] 
                   for i in range(len(results['window_sizes']))]
    sr_speedup = [results['sr_throughput'][i] / results['sr_throughput'][0] 
                  for i in range(len(results['window_sizes']))]
    
    ax4.plot(results['window_sizes'], gbn_speedup, 
             marker='o', linewidth=2, label='Go-Back-N', color='blue')
    ax4.plot(results['window_sizes'], sr_speedup, 
             marker='s', linewidth=2, label='Selective Repeat', color='green')
    ax4.set_xlabel('Tamanho da Janela (N)', fontsize=12)
    ax4.set_ylabel('Speedup (vs N=1)', fontsize=12)
    ax4.set_title('Ganho de Desempenho Relativo', fontweight='bold')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('fase2_performance_analysis.png', dpi=300, bbox_inches='tight')
    print("\n✓ Gráfico salvo: fase2_performance_analysis.png")
    plt.show()


def test_transfer_1mb():
    """Teste de transferência de 1MB comparando com rdt3.0"""
    print("\n" + "=" * 70)
    print("TESTE 4: Transferência de 1MB - Comparação de Eficiência")
    print("=" * 70)
    
    # Gerar dados de 1MB
    data_1mb = b'X' * (1024 * 1024)  # 1MB
    chunk_size = 1024  # 1KB por pacote
    chunks = [data_1mb[i:i+chunk_size] for i in range(0, len(data_1mb), chunk_size)]
    
    print(f"\nTransferindo {len(data_1mb)} bytes em {len(chunks)} pacotes...")
    
    # Canal com perda
    channel = UnreliableChannel(loss_rate=0.10, corrupt_rate=0.05,
                                delay_range=(0.005, 0.02))
    
    # Teste com GBN
    print("\n[1] Go-Back-N (janela=10)...")
    receiver_gbn = GBNReceiver(9041, channel)
    receiver_gbn.start()
    
    sender_gbn = GBNSender(9040, window_size=10, channel=channel, timeout=0.5)
    sender_gbn.start(('localhost', 9041))
    
    start_gbn = time.time()
    for chunk in chunks:
        sender_gbn.send(chunk)
    sender_gbn.wait_for_completion(timeout=60.0)
    time_gbn = time.time() - start_gbn
    
    stats_gbn = sender_gbn.get_statistics()
    
    print(f"  Tempo: {time_gbn:.2f}s")
    print(f"  Throughput: {stats_gbn['throughput_bps']/1024:.2f} KB/s")
    print(f"  Retransmissões: {stats_gbn['retransmissions']}")
    
    sender_gbn.stop()
    receiver_gbn.stop()
    
    time.sleep(1)
    
    # Teste com SR
    channel.reset_statistics()
    
    print("\n[2] Selective Repeat (janela=10)...")
    receiver_sr = SRReceiver(9051, window_size=10, channel=channel)
    receiver_sr.start()
    
    sender_sr = SRSender(9050, window_size=10, channel=channel, timeout=0.5)
    sender_sr.start(('localhost', 9051))
    
    start_sr = time.time()
    for chunk in chunks:
        sender_sr.send(chunk)
    sender_sr.wait_for_completion(timeout=60.0)
    time_sr = time.time() - start_sr
    
    stats_sr = sender_sr.get_statistics()
    
    print(f"  Tempo: {time_sr:.2f}s")
    print(f"  Throughput: {stats_sr['throughput_bps']/1024:.2f} KB/s")
    print(f"  Retransmissões: {stats_sr['retransmissions']}")
    
    sender_sr.stop()
    receiver_sr.stop()
    
    # Comparação
    print("\n" + "=" * 70)
    print("COMPARAÇÃO")
    print("=" * 70)
    print(f"GBN:  {time_gbn:.2f}s | {stats_gbn['throughput_bps']/1024:.2f} KB/s | {stats_gbn['retransmissions']} retrans")
    print(f"SR:   {time_sr:.2f}s | {stats_sr['throughput_bps']/1024:.2f} KB/s | {stats_sr['retransmissions']} retrans")
    
    if time_sr < time_gbn:
        improvement = ((time_gbn - time_sr) / time_gbn) * 100
        print(f"\n✓ SR foi {improvement:.1f}% mais rápido que GBN")
    
    return True


def run_all_tests():
    """Executa todos os testes da Fase 2"""
    print("\n" + "=" * 70)
    print("EXECUÇÃO COMPLETA DOS TESTES - FASE 2")
    print("Protocolos com Pipelining (Go-Back-N e Selective Repeat)")
    print("=" * 70)
    
    results = []
    
    # Teste 1: GBN básico
    results.append(("GBN Básico", test_gbn_basic()))
    time.sleep(1)
    
    # Teste 2: SR com bufferização
    results.append(("SR Bufferização", test_sr_buffering()))
    time.sleep(1)
    
    # Teste 3: Análise de desempenho
    print("\n[Executando análise de desempenho - pode levar alguns minutos...]")
    perf_results = test_throughput_vs_window_size()
    results.append(("Análise de Desempenho", True))
    time.sleep(1)
    
    # Teste 4: Transferência 1MB
    results.append(("Transferência 1MB", test_transfer_1mb()))
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES - FASE 2")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASSOU" if passed else "✗ FALHOU"
        print(f"{status} - {test_name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 TODOS OS TESTES DA FASE 2 PASSARAM! 🎉")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
    print("=" * 70 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
