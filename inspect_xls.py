
import pandas as pd
import sys

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\app2.xls"

try:
    # Try reading first few rows
    # header=None to see raw layout
    df = pd.read_excel(path, header=None, nrows=20)
    print("Shape:", df.shape)
    print("\n--- First 20 Rows ---")
    print(df.to_string())
    
    # Try auto-detect header
    print("\n--- Attempting Header Auto-Detect ---")
    df_header = pd.read_excel(path, nrows=5)
    print("Columns:", df_header.columns.tolist())
    
except Exception as e:
    print(f"Error: {e}")
