"""
Script de teste para validar detecção de parcelas quitadas.
Simula importação sequencial dos relatórios 3 e 4 de fevereiro.
"""
import requests
import os

BASE_URL = "http://localhost:8000"
LOGIN_URL = f"{BASE_URL}/login"
IMPORT_URL = f"{BASE_URL}/import/upload"
CUSTOMERS_URL = f"{BASE_URL}/customers"

# Credenciais
EMAIL = "admin@portalmoveis.local"
PASSWORD = "admin123"

# Arquivos de teste
RELATORIO_3 = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\Relatorio3fevereiroInfoCommerce.HTM"
RELATORIO_4 = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\Relatorio4fevereiro InfoCommerce.HTM"

def test_import_with_paid_detection():
    print("=" * 70)
    print("TESTE: Detecção de Parcelas Quitadas")
    print("=" * 70)
    
    # Cria sessão para manter cookies
    session = requests.Session()
    
    # 1. Login
    print("\n[1] Fazendo login...")
    login_data = {"email": EMAIL, "password": PASSWORD}
    response = session.post(LOGIN_URL, data=login_data, allow_redirects=False)
    
    if response.status_code != 302:
        print(f"❌ Erro no login: {response.status_code}")
        return
    print("✅ Login realizado com sucesso")
    
    # 2. Importa Relatório 3 (com parcela de teste de 12k)
    print("\n[2] Importando Relatório 3 (03/fev - COM parcela de teste)...")
    if not os.path.exists(RELATORIO_3):
        print(f"❌ Arquivo não encontrado: {RELATORIO_3}")
        return
    
    with open(RELATORIO_3, 'rb') as f:
        files = {'file': ('relatorio3.htm', f, 'text/html')}
        response = session.post(IMPORT_URL, files=files, allow_redirects=False)
    
    if response.status_code == 302:
        location = response.headers.get('Location', '')
        if 'msg=' in location:
            msg = location.split('msg=')[1]
            print(f"✅ Importação 1: {msg}")
        else:
            print(f"✅ Importação 1 concluída (redirecionado para {location})")
    else:
        print(f"❌ Erro na importação 1: {response.status_code}")
        return
    
    # 3. Importa Relatório 4 (sem a parcela de teste - foi quitada)
    print("\n[3] Importando Relatório 4 (04/fev - SEM parcela de teste - quitada)...")
    if not os.path.exists(RELATORIO_4):
        print(f"❌ Arquivo não encontrado: {RELATORIO_4}")
        return
    
    with open(RELATORIO_4, 'rb') as f:
        files = {'file': ('relatorio4.htm', f, 'text/html')}
        response = session.post(IMPORT_URL, files=files, allow_redirects=False)
    
    if response.status_code == 302:
        location = response.headers.get('Location', '')
        if 'msg=' in location:
            msg = location.split('msg=')[1]
            print(f"✅ Importação 2: {msg}")
            
            # Verifica se detectou baixas
            if 'Baixadas:' in msg and 'Baixadas: 0' not in msg:
                print("\n🎉 SUCESSO! Parcelas quitadas foram detectadas!")
            else:
                print("\n⚠️  ATENÇÃO: Nenhuma baixa foi detectada. Verifique a lógica.")
        else:
            print(f"✅ Importação 2 concluída (redirecionado para {location})")
    else:
        print(f"❌ Erro na importação 2: {response.status_code}")
        return
    
    print("\n" + "=" * 70)
    print("TESTE CONCLUÍDO")
    print("=" * 70)
    print("\nPróximos passos:")
    print("1. Acesse http://localhost:8000/customers")
    print("2. Busque por 'TESTE'")
    print("3. Verifique se a parcela de R$ 12.000,00 está marcada como PAGA")

if __name__ == "__main__":
    test_import_with_paid_detection()
