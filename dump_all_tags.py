import os
import re
from bs4 import BeautifulSoup

def dump_all_divs(file_path):
    print(f"Lendo DIVs/Ps de: {file_path}")
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        soup = BeautifulSoup(f, 'lxml')
    
    # Procura div, p, span
    tags = soup.find_all(['div', 'p', 'span'])
    print(f"Total tags: {len(tags)}")
    
    rows = {}
    for tag in tags:
        style = tag.get('style', '')
        top_match = re.search(r'top:(\d+)px', style)
        left_match = re.search(r'left:(\d+)px', style)
        text = tag.get_text().strip()
        
        if top_match and left_match and text:
            top = int(top_match.group(1))
            if top not in rows: rows[top] = []
            rows[top].append({'left': int(left_match.group(1)), 'text': text})
    
    with open("tags_dump.txt", "w", encoding="utf-8") as out:
        for top in sorted(rows.keys()):
            line = sorted(rows[top], key=lambda x: x['left'])
            text_line = " | ".join([f"L{el['left']}: {el['text']}" for el in line])
            out.write(f"TOP {top}: {text_line}\n")
    
    print(f"Dump salvo em tags_dump.txt. Linhas capturadas: {len(rows)}")

if __name__ == "__main__":
    dump_all_divs("relatorio.htm")
