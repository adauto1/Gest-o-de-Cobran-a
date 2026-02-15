from bs4 import BeautifulSoup
import os

file_path = r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioDECLIENTE InfoCommerce.HTM'

print(f"Lendo arquivo: {file_path}")
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    # Lemos apenas os primeiros 200kb para análise
    content = f.read(200000)

soup = BeautifulSoup(content, 'html.parser')

# InfoCommerce reports often use div elements with absolute positioning
# Let's find all divs and their positions
divs = []
for div in soup.find_all('div'):
    style = div.get('style', '')
    top = None
    left = None
    if 'top:' in style:
        try:
            top = int(style.split('top:')[1].split('px')[0])
        except: pass
    if 'left:' in style:
        try:
            left = int(style.split('left:')[1].split('px')[0])
        except: pass
    
    text = div.get_text(strip=True)
    if text:
        divs.append({'top': top, 'left': left, 'text': text})

# Sort by top position then left
divs.sort(key=lambda x: (x['top'] if x['top'] is not None else 0, x['left'] if x['left'] is not None else 0))

# Print first 300 non-empty divs to identify headers and rows
print("\n--- Primeiros 300 elementos encontrados ---")
for i, d in enumerate(divs[:300]):
    print(f"Top: {d['top']}, Left: {d['left']}, Text: {d['text']}")
