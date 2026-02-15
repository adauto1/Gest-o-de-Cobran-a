from bs4 import BeautifulSoup
import re

file_path = r'C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioDECLIENTE InfoCommerce.HTM'

target_name = "ACELDO MONTIEL"
print(f"Buscando dados de: {target_name}")

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

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

# Find the target name
found_divs = [d for d in divs if d['top'] is not None and target_name in d['text']]

if found_divs:
    for fd in found_divs:
        target_top = fd['top']
        print(f"\n--- Encontrado em Top: {target_top} ---")
        # Show all divs within -10 and +300px of this top
        nearby = sorted([d for d in divs if d['top'] is not None and target_top - 10 <= d['top'] <= target_top + 300], key=lambda x: (x['top'], x['left'] if x['left'] is not None else 0))
        
        last_top = None
        current_line = []
        for d in nearby:
            if d['top'] != last_top:
                if current_line:
                    print(" | ".join(current_line))
                current_line = []
                last_top = d['top']
                print(f"Top {d['top']}: ", end="")
            current_line.append(f"L{d['left']}: {d['text']}")
        if current_line:
            print(" | ".join(current_line))
else:
    print("Cliente não encontrado.")
