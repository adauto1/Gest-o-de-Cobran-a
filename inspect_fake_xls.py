
import pandas as pd
import sys

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\app2.xls"

print("Attempting to read as Excel (openpyxl)...")
try:
    df = pd.read_excel(path, engine='openpyxl')
    print("Success with openpyxl!")
    print(df.head())
except Exception as e:
    print(f"Openpyxl failed: {e}")

print("\nAttempting to read as HTML...")
try:
    dfs = pd.read_html(path)
    print(f"Success with read_html! Found {len(dfs)} tables.")
    if dfs:
        print(dfs[0].head())
except Exception as e:
    print(f"read_html failed: {e}")

print("\nAttempting to read as XML...")
try:
    df = pd.read_xml(path)
    print("Success with read_xml!")
    print(df.head())
except Exception as e:
    print(f"read_xml failed: {e}")
