"""
Testes automatizados para Fase 1: Protocolos RDT
"""
import sys
import time
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fase1.rdt20 import RDT20Sender, RDT20Receiver
from fase1.rdt21 import RDT21Sender, RDT21Receiver
from fase1.rdt30 import RDT30Sender, RDT30Receiver
from utils.simulator import UnreliableChannel, ReliableChannel


class TestResults:
    """Classe para armazenar resultados de testes"""
    def __init__(self):
        self.tests = []
    
    def add_test(self, name, passed, details=""):
        self.tests.append({
            'name': name,
            'passed': passed,
            'details': details
        })
    
    def print_summary(self):
        print("\n" + "=" * 70)
        print("RESUMO DOS TESTES")
        print("=" * 70)
        
        passed = sum(1 for t in self.tests if t['passed'])
        total = len(self.tests)
        
        for test in self.tests:
            status = "✓ PASSOU" if test['passed'] else "✗ FALHOU"
            print(f"{status} - {test['name']}")
            if test['details']:
                print(f"         {test['details']}")
        
        print("\n" + "=" * 70)
        print(f"Total: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
        print("=" * 70 + "\n")


def test_rdt20():
    """
    Teste do rdt2.0:
    - Canal perfeito (10 mensagens)
    - Canal com 30% de corrupção
    """
    print("\n" + "=" * 70)
    print("TESTE 1: RDT 2.0 - Canal com Erros de Bits")
    print("=" * 70)
    
    results = TestResults()
    
    # Teste 1.1: Canal perfeito
    print("\n[Teste 1.1] Canal perfeito - 10 mensagens")
    
    channel = ReliableChannel()
    receiver = RDT20Receiver(6001, channel)
    receiver.start()
    sender = RDT20Sender(6000, channel)
    
    messages = [f"Mensagem {i}" for i in range(10)]
    
    for msg in messages:
        sender.send(msg, ('localhost', 6001))
        time.sleep(0.05)
    
    time.sleep(1)
    
    received = receiver.get_messages()
    passed = len(received) == len(messages)
    
    results.add_test(
        "RDT2.0 - Canal perfeito",
        passed,
        f"Recebidas: {len(received)}/{len(messages)}"
    )
    
    receiver.stop()
    sender.close()
    
    # Teste 1.2: Canal com 30% de corrupção
    print("\n[Teste 1.2] Canal com 30% de corrupção")
    
    channel = UnreliableChannel(loss_rate=0.0, corrupt_rate=0.3, delay_range=(0.01, 0.1))
    receiver = RDT20Receiver(6003, channel)
    receiver.start()
    sender = RDT20Sender(6002, channel)
    
    messages = [f"Teste {i}" for i in range(10)]
    
    for msg in messages:
        sender.send(msg, ('localhost', 6003))
        time.sleep(0.1)
    
    time.sleep(2)
    
    received = receiver.get_messages()
    stats_sender = sender.get_statistics()
    
    passed = len(received) == len(messages) and stats_sender['retransmissions'] > 0
    
    results.add_test(
        "RDT2.0 - Com corrupção",
        passed,
        f"Recebidas: {len(received)}/{len(messages)}, Retransmissões: {stats_sender['retransmissions']}"
    )
    
    channel.print_statistics()
    
    receiver.stop()
    sender.close()
    
    return results


def test_rdt21():
    """
    Teste do rdt2.1:
    - Corrupção de 20% em DATA
    - Corrupção de 20% em ACKs
    - Verificar ausência de duplicação
    """
    print("\n" + "=" * 70)
    print("TESTE 2: RDT 2.1 - Com Números de Sequência")
    print("=" * 70)
    
    results = TestResults()
    
    print("\n[Teste 2.1] Corrupção de DATA e ACKs - sem duplicação")
    
    channel = UnreliableChannel(loss_rate=0.0, corrupt_rate=0.2, delay_range=(0.01, 0.1))
    receiver = RDT21Receiver(6011, channel)
    receiver.start()
    sender = RDT21Sender(6010, channel)
    
    messages = [f"Mensagem {i}" for i in range(15)]
    
    for msg in messages:
        sender.send(msg, ('localhost', 6011))
        time.sleep(0.1)
    
    time.sleep(2)
    
    received = receiver.get_messages()
    stats_sender = sender.get_statistics()
    stats_receiver = receiver.get_statistics()
    
    # Verificar se todas as mensagens foram recebidas SEM duplicação
    no_duplicates = len(received) == len(messages)
    all_correct = all(
        received[i].decode() == messages[i]
        for i in range(min(len(received), len(messages)))
    )
    
    passed = no_duplicates and all_correct and stats_receiver['duplicated_packets'] == 0
    
    results.add_test(
        "RDT2.1 - Sem duplicação",
        passed,
        f"Recebidas: {len(received)}/{len(messages)}, Duplicados: {stats_receiver['duplicated_packets']}"
    )
    
    # Calcular overhead
    header_size = 6
    total_payload = sum(len(msg) for msg in messages)
    overhead_bytes = stats_sender['packets_sent'] * header_size
    overhead_percent = (overhead_bytes / total_payload) * 100
    
    print(f"\nOverhead: {overhead_bytes} bytes ({overhead_percent:.1f}% do payload)")
    
    channel.print_statistics()
    
    receiver.stop()
    sender.close()
    
    return results


def test_rdt30():
    """
    Teste do rdt3.0:
    - Perda de 15% dos DATA
    - Perda de 15% dos ACKs
    - Atraso variável 50-500ms
    - Medir taxa de retransmissão e throughput
    """
    print("\n" + "=" * 70)
    print("TESTE 3: RDT 3.0 - Com Timer e Perda de Pacotes")
    print("=" * 70)
    
    results = TestResults()
    
    print("\n[Teste 3.1] Perda e corrupção - entrega completa")
    
    channel = UnreliableChannel(
        loss_rate=0.15,
        corrupt_rate=0.10,
        delay_range=(0.05, 0.5)
    )
    
    receiver = RDT30Receiver(6021, channel)
    receiver.start()
    sender = RDT30Sender(6020, channel, timeout=2.0)
    
    messages = [f"Mensagem número {i}" for i in range(20)]
    
    start_time = time.time()
    
    for msg in messages:
        sender.send(msg, ('localhost', 6021))
    
    elapsed = time.time() - start_time
    
    time.sleep(1)
    
    received = receiver.get_messages()
    stats_sender = sender.get_statistics()
    stats_receiver = receiver.get_statistics()
    
    # Verificar entrega completa e correta
    all_delivered = len(received) == len(messages)
    all_correct = all(
        received[i].decode() == messages[i]
        for i in range(min(len(received), len(messages)))
    )
    
    passed = all_delivered and all_correct
    
    results.add_test(
        "RDT3.0 - Entrega completa",
        passed,
        f"Recebidas: {len(received)}/{len(messages)}"
    )
    
    # Teste de métricas
    retrans_rate = stats_sender['retransmission_rate']
    throughput = stats_sender['throughput_bps']
    
    print(f"\nMétricas:")
    print(f"  Taxa de retransmissão: {retrans_rate:.2%}")
    print(f"  Timeouts: {stats_sender['timeouts']}")
    print(f"  Throughput: {throughput:.2f} bytes/s")
    print(f"  Tempo total: {elapsed:.2f}s")
    
    results.add_test(
        "RDT3.0 - Retransmissões ocorreram",
        retrans_rate > 0,
        f"Taxa: {retrans_rate:.2%}"
    )
    
    channel.print_statistics()
    
    receiver.stop()
    sender.close()
    
    return results


def run_all_tests():
    """Executa todos os testes da Fase 1"""
    print("\n" + "=" * 70)
    print("EXECUÇÃO COMPLETA DOS TESTES - FASE 1")
    print("Protocolos RDT (Reliable Data Transfer)")
    print("=" * 70)
    
    all_results = TestResults()
    
    # Teste RDT 2.0
    results_20 = test_rdt20()
    all_results.tests.extend(results_20.tests)
    
    time.sleep(1)
    
    # Teste RDT 2.1
    results_21 = test_rdt21()
    all_results.tests.extend(results_21.tests)
    
    time.sleep(1)
    
    # Teste RDT 3.0
    results_30 = test_rdt30()
    all_results.tests.extend(results_30.tests)
    
    # Resumo final
    all_results.print_summary()
    
    return all_results


if __name__ == "__main__":
    results = run_all_tests()
    
    # Verificar se todos passaram
    all_passed = all(t['passed'] for t in results.tests)
    
    if all_passed:
        print("🎉 TODOS OS TESTES DA FASE 1 PASSARAM! 🎉\n")
        exit(0)
    else:
        print("❌ ALGUNS TESTES FALHARAM\n")
        exit(1)
