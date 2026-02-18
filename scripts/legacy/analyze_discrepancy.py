
import re
from bs4 import BeautifulSoup
import sys

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioFEVEREIROInfoCommerce.HTM"

def parse_money_str(s):
    try:
        clean = s.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(clean)
    except:
        return 0.0

try:
    with open(path, "r", encoding="iso-8859-1", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    elements = []
    re_top = re.compile(r'top:(\d+)')
    re_left = re.compile(r'left:(\d+)')

    for div in soup.find_all("div"):
        style = div.get("style", "")
        if not style: continue
        
        tm = re_top.search(style)
        lm = re_left.search(style)
        if tm and lm:
            text = div.get_text(" ", strip=True)
            if not text: continue
            elements.append({
                'top': int(tm.group(1)),
                'left': int(lm.group(1)),
                'text': text
            })

    elements.sort(key=lambda x: (x['top'], x['left']))

    rows = []
    current_row = [elements[0]]
    current_y = elements[0]['top']

    for el in elements[1:]:
        if abs(el['top'] - current_y) <= 4:
            current_row.append(el)
        else:
            rows.append(current_row)
            current_row = [el]
            current_y = el['top']
    rows.append(current_row)

    print("--- Captured Items ---")
    
    re_date = re.compile(r'\d{2}/\d{2}/\d{4}')
    re_money = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

    total_sum = 0.0
    
    for i, row in enumerate(rows):
        row.sort(key=lambda x: x['left'])
        
        candidates_date = []
        candidates_amount = []
        name_parts = []
        
        for el in row:
            txt = el['text']
            if re_date.match(txt):
                candidates_date.append(el)
            elif re_money.match(txt):
                candidates_amount.append(el)
        
        valid_date = None
        for cand in candidates_date:
            if 550 <= cand['left'] <= 630:
                valid_date = cand
                break
        
        valid_amount = None
        for cand in candidates_amount:
            if 630 <= cand['left'] <= 700:
                valid_amount = cand
                break
                
        if valid_date and valid_amount:
            amount = parse_money_str(valid_amount['text'])
            total_sum += amount
            
            # Extract Name (left < 500)
            for el in row:
                if el == valid_date or el == valid_amount: continue
                if el['left'] < 500:
                     name_parts.append(el['text'])
            
            name = " ".join(name_parts)
            print(f"Row {i} | Name: {name[:30]} | Date: {valid_date['text']} | Amount: {amount:.2f}")

    print(f"\nFinal Total: {total_sum:.2f}")

except Exception as e:
    print(f"Error: {e}")
