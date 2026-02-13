import os
import re
from bs4 import BeautifulSoup

def sample_spans(file_path, lines_to_show=100):
    print(f"Lendo spans de: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    spans = soup.find_all('span')
    print(f"Total spans: {len(spans)}")
    
    # Agrupa por top para ver as linhas
    rows = {}
    for span in spans[:1000]: # Pega os primeiros 1000 pra analisar
        style = span.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        if top_match and left_match:
            top = int(top_match.group(1))
            if top not in rows: rows[top] = []
            rows[top].append({'left': int(left_match.group(1)), 'text': span.get_text().strip()})
    
    for top in sorted(rows.keys())[:50]:
        line = sorted(rows[top], key=lambda x: x['left'])
        print(f"TOP {top}: " + " | ".join([f"L{el['left']}: {el['text']}" for el in line if el['text']]))

if __name__ == "__main__":
    sample_spans("relatorio.htm")
