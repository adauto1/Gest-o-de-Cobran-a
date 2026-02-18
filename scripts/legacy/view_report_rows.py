from bs4 import BeautifulSoup

file_path = r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioDECLIENTE InfoCommerce.HTM'

print("Procurando cabeçalhos no relatório...")
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    # Lemos os primeiros 500kb para ter certeza de pegar o cabeçalho
    content = f.read(500000)

soup = BeautifulSoup(content, 'html.parser')
divs = []
for div in soup.find_all('div'):
    style = div.get('style', '')
    top = None
    left = None
    if 'top:' in style:
        try: top = int(style.split('top:')[1].split('px')[0])
        except: pass
    if 'left:' in style:
        try: left = int(style.split('left:')[1].split('px')[0])
        except: pass
    
    text = div.get_text(strip=True)
    if text:
        divs.append({'top': top, 'left': left, 'text': text})

# Agrupar por 'top' para ver as linhas
rows = {}
for d in divs:
    t = d['top']
    if t is None: continue
    if t not in rows: rows[t] = []
    rows[t].append(d)

import re

# Padrão para buscar telefones
phone_pattern = re.compile(r'(\(?\d{2}\)?\s?\d{4,5}-?\d{4})')

tops = sorted(rows.keys())
for top in tops:
    line = " | ".join([f"L{d['left']}: {d['text']}" for d in sorted(rows[top], key=lambda x: x['left'] if x['left'] is not None else 0)])
    if phone_pattern.search(line) or "Fone" in line or "Cel" in line:
        print(f"Top {top}: {line}")
    elif 400 <= top <= 600: # Mostrar alguns exemplos perto do início
        print(f"Top {top}: {line}")
