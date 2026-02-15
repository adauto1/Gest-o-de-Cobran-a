
path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\rel.14.02.26 InfoCommerce.HTM"
import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    with open(path, "r", encoding="iso-8859-1", errors="replace") as f:
        print(f.read(2000))
except Exception as e:
    print(f"Error: {e}")
