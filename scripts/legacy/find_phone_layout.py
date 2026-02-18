from bs4 import BeautifulSoup
import re

file_path = r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioDECLIENTE InfoCommerce.HTM'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

soup = BeautifulSoup(content, 'html.parser')
print("Buscando padrões de dados...")
found = 0
for div in soup.find_all('div'):
    text = div.get_text(strip=True)
    # Busca algo que pareça telefone ou CPF
    if re.search(r'\(\d{2}\)', text) or re.search(r'\d{3}\.\d{3}', text):
        style = div.get('style', '')
        print(f"VALOR: '{text}' | STYLE: {style}")
        found += 1
        if found > 50: break

if found == 0:
    print("Nenhum dado encontrado.")
