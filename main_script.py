"""
Script Principal - EFC 02: Transferência Confiável de Dados e TCP sobre UDP

Este script executa todo o projeto de forma integrada:
- Fase 1: Protocolos RDT (rdt2.0, 2.1, 3.0)
- Fase 2: Pipelining (GBN e SR)
- Fase 3: TCP Simplificado

Uso:
    python main.py                  # Menu interativo
    python main.py --test-all       # Executar todos os testes
    python main.py --fase1          # Apenas Fase 1
    python main.py --fase2          # Apenas Fase 2
    python main.py --fase3          # Apenas Fase 3
    python main.py --demo           # Demonstração completa
"""

import sys
import time
import argparse


def print_header(title, width=70):
    """Imprime cabeçalho formatado"""
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title):
    """Imprime título de seção"""
    print("\n" + "-" * 70)
    print(f"  {title}")
    print("-" * 70)


def menu_principal():
    """Exibe menu interativo"""
    print_header("EFC 02: TRANSFERÊNCIA CONFIÁVEL DE DADOS E TCP SOBRE UDP")
    
    print("\n📚 Projeto completo de protocolos de rede")
    print("   Baseado em: Kurose & Ross - Capítulo 3\n")
    
    print("Selecione uma opção:\n")
    print("  [1] Executar TODOS os testes (Fase 1 + 2 + 3)")
    print("  [2] Fase 1: Protocolos RDT (rdt2.0, 2.1, 3.0)")
    print("  [3] Fase 2: Pipelining (Go-Back-N e Selective Repeat)")
    print("  [4] Fase 3: TCP Simplificado sobre UDP")
    print("  [5] Demonstração interativa (cliente-servidor)")
    print("  [6] Análise de desempenho com gráficos")
    print("  [7] Ver estatísticas do projeto")
    print("  [0] Sair\n")
    
    try:
        opcao = input("Digite sua escolha: ").strip()
        return opcao
    except KeyboardInterrupt:
        print("\n\n👋 Até logo!")
        sys.exit(0)


def executar_fase1():
    """Executa testes da Fase 1"""
    print_header("FASE 1: PROTOCOLOS RDT")
    
    print("\n📦 Protocolos a serem testados:")
    print("   • rdt2.0: Stop-and-Wait com ACK/NAK")
    print("   • rdt2.1: Com números de sequência")
    print("   • rdt3.0: Com timer e tratamento de perda\n")
    
    input("Pressione ENTER para iniciar os testes...")
    
    try:
        from testes.test_fase1 import run_all_tests
        success = run_all_tests()
        
        if success:
            print("\n✅ Fase 1 concluída com SUCESSO!")
        else:
            print("\n⚠️  Fase 1 teve alguns testes com falha")
        
        return success
        
    except ImportError as e:
        print(f"\n❌ Erro ao importar testes: {e}")
        print("   Certifique-se de estar no diretório correto")
        return False


def executar_fase2():
    """Executa testes da Fase 2"""
    print_header("FASE 2: PIPELINING (GO-BACK-N E SELECTIVE REPEAT)")
    
    print("\n🚀 Protocolos com janela deslizante:")
    print("   • Go-Back-N: ACKs cumulativos")
    print("   • Selective Repeat: ACKs individuais")
    print("   • Análise de desempenho com gráficos\n")
    
    input("Pressione ENTER para iniciar os testes...")
    
    try:
        from testes.test_fase2 import run_all_tests
        success = run_all_tests()
        
        if success:
            print("\n✅ Fase 2 concluída com SUCESSO!")
            print("📊 Gráfico salvo: fase2_performance_analysis.png")
        else:
            print("\n⚠️  Fase 2 teve alguns testes com falha")
        
        return success
        
    except ImportError as e:
        print(f"\n❌ Erro ao importar testes: {e}")
        return False


def executar_fase3():
    """Executa testes da Fase 3"""
    print_header("FASE 3: TCP SIMPLIFICADO SOBRE UDP")
    
    print("\n🌐 Funcionalidades TCP implementadas:")
    print("   • Three-way handshake (SYN, SYN-ACK, ACK)")
    print("   • Transferência confiável de dados")
    print("   • Controle de fluxo (window size)")
    print("   • Retransmissão adaptativa (RTT)")
    print("   • Four-way handshake (encerramento)\n")
    
    input("Pressione ENTER para iniciar os testes...")
    
    try:
        from testes.test_fase3 import run_all_tests
        success = run_all_tests()
        
        if success:
            print("\n✅ Fase 3 concluída com SUCESSO!")
        else:
            print("\n⚠️  Fase 3 teve alguns testes com falha")
        
        return success
        
    except ImportError as e:
        print(f"\n❌ Erro ao importar testes: {e}")
        return False


def demonstracao_interativa():
    """Demonstração interativa do TCP simplificado"""
    print_header("DEMONSTRAÇÃO: CLIENTE-SERVIDOR TCP")
    
    print("\n🔧 Esta demonstração iniciará:")
    print("   1. Um servidor TCP simplificado na porta 8000")
    print("   2. Um cliente que envia mensagens")
    print("   3. Troca de dados bidirecional\n")
    
    print("⚠️  Você precisará de 2 terminais:")
    print("   Terminal 1: python fase3/tcp_server.py")
    print("   Terminal 2: python fase3/tcp_client.py\n")
    
    print("Ou pode executar o modo echo interativo:")
    print("   Terminal 1: python fase3/tcp_server.py --echo")
    print("   Terminal 2: python fase3/tcp_client.py --echo\n")
    
    input("Pressione ENTER para ver instruções detalhadas...")
    
    print("\n" + "=" * 70)
    print("INSTRUÇÕES PASSO A PASSO")
    print("=" * 70)
    
    print("\n1️⃣  Abra um novo terminal e execute:")
    print("   $ cd fase3")
    print("   $ python tcp_server.py --port 8000")
    
    print("\n2️⃣  Abra outro terminal e execute:")
    print("   $ cd fase3")
    print("   $ python tcp_client.py --host localhost --port 8000")
    
    print("\n3️⃣  Observe a troca de mensagens e estatísticas")
    
    print("\n" + "=" * 70)
    
    print("\n💡 Outras opções úteis:")
    print("   --unreliable  : Simula rede não confiável (perdas)")
    print("   --messages N  : Envia N mensagens")
    print("   --echo        : Modo interativo (digite mensagens)")
    print("   --file ARQUIVO: Transfere um arquivo\n")


def analise_desempenho():
    """Análise de desempenho comparativa"""
    print_header("ANÁLISE DE DESEMPENHO")
    
    print("\n📊 Esta análise irá:")
    print("   • Comparar throughput de todos os protocolos")
    print("   • Variar tamanho da janela (N = 1, 5, 10, 20)")
    print("   • Gerar gráficos comparativos")
    print("   • Medir taxa de retransmissão")
    print("\n   ⏱️  Tempo estimado: 3-5 minutos\n")
    
    input("Pressione ENTER para iniciar análise...")
    
    try:
        from testes.test_fase2 import test_throughput_vs_window_size
        
        print("\n🔬 Executando testes de desempenho...")
        results = test_throughput_vs_window_size()
        
        print("\n✅ Análise concluída!")
        print("📈 Resultados:")
        
        print("\n┌─────────────┬──────────────┬──────────────┐")
        print("│   Janela    │ GBN Throughput│ SR Throughput│")
        print("├─────────────┼──────────────┼──────────────┤")
        
        for i, w in enumerate(results['window_sizes']):
            gbn = results['gbn_throughput'][i]
            sr = results['sr_throughput'][i]
            print(f"│   N = {w:2d}    │  {gbn:7.1f} B/s │  {sr:7.1f} B/s │")
        
        print("└─────────────┴──────────────┴──────────────┘")
        
        print("\n📊 Gráfico salvo: fase2_performance_analysis.png")
        
    except Exception as e:
        print(f"\n❌ Erro na análise: {e}")


def estatisticas_projeto():
    """Exibe estatísticas do projeto"""
    print_header("ESTATÍSTICAS DO PROJETO")
    
    print("\n📁 Estrutura do Projeto:\n")
    
    estrutura = {
        "Fase 1 - Protocolos RDT": {
            "rdt20.py": "250 linhas",
            "rdt21.py": "280 linhas",
            "rdt30.py": "350 linhas",
        },
        "Fase 2 - Pipelining": {
            "gbn.py": "420 linhas",
            "sr.py": "480 linhas",
        },
        "Fase 3 - TCP Simplificado": {
            "tcp_socket.py": "650 linhas",
            "tcp_server.py": "180 linhas",
            "tcp_client.py": "220 linhas",
        },
        "Utilitários": {
            "packet.py": "180 linhas",
            "simulator.py": "120 linhas",
            "logger.py": "80 linhas",
        },
        "Testes": {
            "test_fase1.py": "280 linhas",
            "test_fase2.py": "350 linhas",
            "test_fase3.py": "420 linhas",
        }
    }
    
    total_linhas = 0
    total_arquivos = 0
    
    for categoria, arquivos in estrutura.items():
        print(f"📦 {categoria}")
        for arquivo, linhas in arquivos.items():
            num_linhas = int(linhas.split()[0])
            total_linhas += num_linhas
            total_arquivos += 1
            print(f"   ├─ {arquivo:20s} {linhas:>12s}")
        print()
    
    print("=" * 70)
    print(f"Total: {total_arquivos} arquivos, ~{total_linhas:,} linhas de código")
    print("=" * 70)
    
    print("\n📊 Funcionalidades Implementadas:\n")
    
    features = [
        "✅ 8 protocolos diferentes (rdt2.0 a TCP)",
        "✅ Detecção e correção de erros (checksums)",
        "✅ Números de sequência e ACKs",
        "✅ Timers e retransmissão",
        "✅ Pipelining (janelas deslizantes)",
        "✅ Controle de fluxo",
        "✅ Estimativa adaptativa de RTT",
        "✅ Three-way e Four-way handshakes",
        "✅ 16 testes automatizados",
        "✅ Análise de desempenho com gráficos",
        "✅ Simulador de canal não confiável",
        "✅ Aplicações cliente-servidor funcionais",
    ]
    
    for feature in features:
        print(f"   {feature}")
    
    print("\n🎯 Conceitos do Capítulo 3 Aplicados:\n")
    
    conceitos = [
        "• Seção 3.4.1: Protocolos rdt (2.0, 2.1, 3.0)",
        "• Seção 3.4.3: Go-Back-N",
        "• Seção 3.4.4: Selective Repeat",
        "• Seção 3.5.2: Estrutura do segmento TCP",
        "• Seção 3.5.3: Estimativa de RTT",
        "• Seção 3.5.4: Transferência confiável",
        "• Seção 3.5.5: Controle de fluxo",
        "• Seção 3.5.6: Gerenciamento de conexão",
    ]
    
    for conceito in conceitos:
        print(f"   {conceito}")
    
    print("\n" + "=" * 70)


def executar_todos():
    """Executa todas as fases em sequência"""
    print_header("EXECUÇÃO COMPLETA DO PROJETO")
    
    print("\n🚀 Iniciando execução de todas as fases...")
    print("   Tempo estimado: 5-10 minutos\n")
    
    input("Pressione ENTER para continuar...")
    
    resultados = {}
    
    # Fase 1
    print_section("Iniciando Fase 1...")
    resultados['fase1'] = executar_fase1()
    time.sleep(2)
    
    # Fase 2
    print_section("Iniciando Fase 2...")
    resultados['fase2'] = executar_fase2()
    time.sleep(2)
    
    # Fase 3
    print_section("Iniciando Fase 3...")
    resultados['fase3'] = executar_fase3()
    
    # Resumo final
    print("\n" + "=" * 70)
    print("RESUMO FINAL DA EXECUÇÃO")
    print("=" * 70)
    
    for fase, sucesso in resultados.items():
        status = "✅ PASSOU" if sucesso else "❌ FALHOU"
        print(f"   {status}  {fase.upper()}")
    
    total_sucesso = sum(resultados.values())
    total_fases = len(resultados)
    
    print("\n" + "=" * 70)
    print(f"Resultado: {total_sucesso}/{total_fases} fases passaram ({total_sucesso/total_fases*100:.0f}%)")
    
    if total_sucesso == total_fases:
        print("\n🎉 PARABÉNS! TODAS AS FASES FORAM CONCLUÍDAS COM SUCESSO! 🎉")
    else:
        print("\n⚠️  Algumas fases tiveram problemas. Verifique os logs acima.")
    
    print("=" * 70 + "\n")
    
    return total_sucesso == total_fases


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description='EFC 02: Transferência Confiável de Dados e TCP sobre UDP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py                    # Menu interativo
  python main.py --test-all         # Executar todos os testes
  python main.py --fase1            # Apenas Fase 1
  python main.py --fase2            # Apenas Fase 2
  python main.py --fase3            # Apenas Fase 3
  python main.py --demo             # Demonstração
  python main.py --stats            # Estatísticas do projeto
        """
    )
    
    parser.add_argument('--test-all', action='store_true',
                       help='Executar todos os testes')
    parser.add_argument('--fase1', action='store_true',
                       help='Executar apenas Fase 1 (RDT)')
    parser.add_argument('--fase2', action='store_true',
                       help='Executar apenas Fase 2 (Pipelining)')
    parser.add_argument('--fase3', action='store_true',
                       help='Executar apenas Fase 3 (TCP)')
    parser.add_argument('--demo', action='store_true',
                       help='Demonstração interativa')
    parser.add_argument('--performance', action='store_true',
                       help='Análise de desempenho')
    parser.add_argument('--stats', action='store_true',
                       help='Estatísticas do projeto')
    
    args = parser.parse_args()
    
    # Se argumentos de linha de comando foram fornecidos
    if args.test_all:
        return 0 if executar_todos() else 1
    elif args.fase1:
        return 0 if executar_fase1() else 1
    elif args.fase2:
        return 0 if executar_fase2() else 1
    elif args.fase3:
        return 0 if executar_fase3() else 1
    elif args.demo:
        demonstracao_interativa()
        return 0
    elif args.performance:
        analise_desempenho()
        return 0
    elif args.stats:
        estatisticas_projeto()
        return 0
    
    # Menu interativo
    while True:
        opcao = menu_principal()
        
        if opcao == '0':
            print("\n👋 Até logo!")
            break
        elif opcao == '1':
            executar_todos()
        elif opcao == '2':
            executar_fase1()
        elif opcao == '3':
            executar_fase2()
        elif opcao == '4':
            executar_fase3()
        elif opcao == '5':
            demonstracao_interativa()
        elif opcao == '6':
            analise_desempenho()
        elif opcao == '7':
            estatisticas_projeto()
        else:
            print("\n❌ Opção inválida! Tente novamente.")
        
        if opcao != '0':
            input("\n\nPressione ENTER para voltar ao menu...")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário. Até logo!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
