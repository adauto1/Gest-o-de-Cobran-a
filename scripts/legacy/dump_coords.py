import os
import re
from bs4 import BeautifulSoup

def dump_all_spans(file_path):
    print(f"Lendo spans de: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    spans = soup.find_all('span')
    print(f"Total spans: {len(spans)}")
    
    rows = {}
    for span in spans:
        style = span.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        if top_match and left_match:
            top = int(top_match.group(1))
            if top not in rows: rows[top] = []
            rows[top].append({'left': int(left_match.group(1)), 'text': span.get_text().strip()})
    
    with open("spans_dump.txt", "w", encoding="utf-8") as out:
        for top in sorted(rows.keys()):
            line = sorted(rows[top], key=lambda x: x['left'])
            text_line = " | ".join([f"L{el['left']}: {el['text']}" for el in line if el['text']])
            if text_line:
                out.write(f"TOP {top}: {text_line}\n")
    
    print("Dump salvo em spans_dump.txt")

if __name__ == "__main__":
    dump_all_spans("relatorio.htm")
