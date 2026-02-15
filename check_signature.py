
path = r"C:\Users\Adauto Pereira\Desktop\DADOS ERP\app2.xls"

try:
    with open(path, "rb") as f:
        header = f.read(500)
        print("Header bytes (hex):", header[:20].hex())
        try:
            print("Header text:", header.decode('utf-8', errors='replace'))
        except:
            print("Header text (latin1):", header.decode('latin1', errors='replace'))
except Exception as e:
    print(e)
