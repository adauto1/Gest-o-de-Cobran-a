import os

def peek_html_report(file_path, bytes_to_read=50000):
    print(f"Investigando a estrutura de: {file_path}")
    try:
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            content = f.read(bytes_to_read)
            print("-" * 50)
            print(content)
            print("-" * 50)
    except Exception as e:
        print(f"Erro ao ler arquivo: {e}")

if __name__ == "__main__":
    html_file = "relatorio.htm"
    if os.path.exists(html_file):
        peek_html_report(html_file)
    else:
        print(f"Erro: Arquivo '{html_file}' nao encontrado.")
