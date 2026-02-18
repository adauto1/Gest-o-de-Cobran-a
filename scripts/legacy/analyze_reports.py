import re
from bs4 import BeautifulSoup

def analyze_html(filepath):
    with open(filepath, 'r', encoding='latin-1') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    
    tags = soup.find_all(['div', 'p', 'span'])
    rows_data = {}
    
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        txt = tag.get_text().strip()
        
        if top_match and left_match and txt:
            top = int(top_match.group(1))
            left = int(left_match.group(1))
            if top not in rows_data:
                rows_data[top] = {}
            rows_data[top][left] = txt
    
    # Procura por cliente TESTE
    print(f"\n=== Análise de {filepath} ===\n")
    for top in sorted(rows_data.keys()):
        row = rows_data[top]
        cliente = row.get(264, '')
        if 'TESTE' in cliente.upper():
            vencimento = row.get(588, '')
            valor = row.get(648, '')
            print(f"Cliente: {cliente}")
            print(f"Vencimento: {vencimento}")
            print(f"Valor: {valor}")
            print("-" * 50)

# Analisa os dois relatórios
analyze_html(r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\Relatorio3fevereiroInfoCommerce.HTM')
analyze_html(r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\Relatorio4fevereiro InfoCommerce.HTM')
