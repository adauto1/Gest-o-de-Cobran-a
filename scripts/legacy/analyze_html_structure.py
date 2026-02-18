
from bs4 import BeautifulSoup
import sys
# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\rel.14.02.26 InfoCommerce.HTM"

try:
    with open(path, "r", encoding="iso-8859-1", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")
        
    tables = soup.find_all("table")
    print(f"Tables found: {len(tables)}")
    
    for i, table in enumerate(tables):
        print(f"\n--- Table {i} ---")
        headers = []
        
        # Strategy 1: Th elements
        for th in table.find_all("th"):
            headers.append(th.get_text(strip=True))
            
        # Strategy 2: First Tr with Td (often used in simple reports)
        if not headers:
            rows = table.find_all("tr")
            if rows:
                first_row = rows[0]
                # Check formatting too? Just text for now
                for td in first_row.find_all("td"):
                    headers.append(td.get_text(strip=True))
                    
        print(f"Headers: {headers}")
        
        # Peek at data
        rows = table.find_all("tr")
        if len(rows) > 1:
            data = []
            for td in rows[1].find_all("td"):
                data.append(td.get_text(strip=True))
            print(f"Row 1 Data: {data}")

except Exception as e:
    print(f"Error: {e}")
