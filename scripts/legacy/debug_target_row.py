
import pandas as pd
from datetime import datetime
import re
from bs4 import BeautifulSoup
import sys

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\RelatorioFEVEREIROInfoCommerce.HTM"

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

    # Find row with 1171.73
    target_row = None
    for i, row in enumerate(rows):
        for el in row:
            if "1171,73" in el['text'] or "1.171,73" in el['text']:
                target_row = row
                print(f"Found target in Row {i}")
                break
        if target_row: break

    if target_row:
        target_row.sort(key=lambda x: x['left'])
        print("\n--- Row Elements ---")
        for el in target_row:
            print(f"x={el['left']} | Text: '{el['text']}'")

except Exception as e:
    print(f"Error: {e}")
