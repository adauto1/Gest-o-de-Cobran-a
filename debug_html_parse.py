import os
import re
from decimal import Decimal
from bs4 import BeautifulSoup

def parse_infocommerce_html(file_path):
    print(f"Lendo: {file_path}")
    
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    elements = []
    for span in soup.find_all('span'):
        style = span.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        
        if top_match and left_match:
            top = int(top_match.group(1))
            left = int(left_match.group(1))
            text = span.get_text().strip()
            if text:
                elements.append({'top': top, 'left': left, 'text': text})
    
    rows_data = {}
    for el in elements:
        top = el['top']
        if top not in rows_data:
            rows_data[top] = []
        rows_data[top].append(el)
    
    sorted_tops = sorted(rows_data.keys())
    parsed_titles = []
    
    for top in sorted_tops:
        line_elements = sorted(rows_data[top], key=lambda x: x['left'])
        line_text = " | ".join([f"[{el['left']}]{el['text']}" for el in line_elements])
        
        # Filtra linhas que parecem conter dados de títulos
        # Emissão [54] | Vencimento [147] | Cliente [261] | Valor [800+]
        date_matches = re.findall(r'(\d{2}/\d{2}/\d{4})', line_text)
        
        if len(date_matches) >= 2:
            # Tenta pegar o valor
            money_match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', line_text)
            if money_match:
                # O nome do cliente costuma estar entre left 200 e 600
                cliente = "Desconhecido"
                for el in line_elements:
                    if 200 <= el['left'] <= 600:
                        if el['text'] not in date_matches:
                            cliente = el['text']
                            break
                
                parsed_titles.append({
                    'emissao': date_matches[0],
                    'vencimento': date_matches[1],
                    'cliente': cliente,
                    'valor': money_match.group(1)
                })
                
    return parsed_titles

if __name__ == "__main__":
    html_file = "relatorio.htm"
    if os.path.exists(html_file):
        data = parse_infocommerce_html(html_file)
        print(f"Total: {len(data)}")
        for d in data[:20]:
            print(d)
    else:
        print("Arquivo nao encontrado.")
