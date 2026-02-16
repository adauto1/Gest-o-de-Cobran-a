import requests
import time

print("Fazendo requisição para http://127.0.0.1:8000/api/whatsapp/status...")
try:
    resp = requests.get("http://127.0.0.1:8000/api/whatsapp/status")
    print(f"Status Code Frontend: {resp.status_code}")
    print(f"JSON Frontend: {resp.json()}")
except Exception as e:
    print(f"Erro ao conectar no localhost: {e}")
