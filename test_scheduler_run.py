import os
import sys

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal
from app.scheduler import run_collection_check

def test_run():
    print("Iniciando run_collection_check...")
    stats = run_collection_check(SessionLocal)
    print(f"Stats retornados: {stats}")

if __name__ == "__main__":
    test_run()
