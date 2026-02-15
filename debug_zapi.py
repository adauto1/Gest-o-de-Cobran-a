import requests
import json

# Credenciais
ZAPI_INSTANCE_ID = "3EECA6A04BF7413E6BA8B269A10D1A36"
ZAPI_TOKEN = "05378181EC7C9F4A958AE8B4"
TELEFONE = "5567996524740"

def debug_zapi_verbose():
    base_url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}"
    
    # 1. Testar Status
    print("\n----- 1. TESTANDO STATUS -----")
    try:
        resp = requests.get(f"{base_url}/status")
        print(f"Status Code: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Erro ao checar status: {e}")

    # 2. Testar Envio
    print("\n----- 2. TESTANDO ENVIO -----")
    payload = {
        "phone": TELEFONE,
        "message": "Teste Z-API - Se ler isso, funcionou."
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(f"{base_url}/send-text", json=payload, headers=headers)
        print(f"Status Code: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Erro ao enviar: {e}")

if __name__ == "__main__":
    debug_zapi_verbose()
