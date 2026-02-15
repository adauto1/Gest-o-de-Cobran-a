
import re
from bs4 import BeautifulSoup
import sys

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
            elements.append({'top': int(tm.group(1)), 'left': int(lm.group(1)), 'text': text})

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

    for i in [101, 122]:
        if i < len(rows):
            row = rows[i]
            row.sort(key=lambda x: x['left'])
            status_parts = []
            name_parts = []
            amount = "N/A"
            date = "N/A"
            
            re_date = re.compile(r'\d{2}/\d{2}/\d{4}')
            re_money = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

            for el in row:
                if el['left'] > 700:
                    status_parts.append(el['text'])
                if re_date.match(el['text']) and 550 <= el['left'] <= 630:
                    date = el['text']
                if re_money.match(el['text']) and 630 <= el['left'] <= 700:
                    amount = el['text']
                if el['left'] < 500:
                    name_parts.append(el['text'])
            
            status = " ".join(status_parts)
            name = " ".join(name_parts)
            print(f"Row {i} | Name: {name} | Date: {date} | Amount: {amount} | Status: '{status}'")

except Exception as e:
    print(e)
