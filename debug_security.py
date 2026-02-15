import requests

INSTANCE_ID = "3EECA6A04BF7413E6BA8B269A10D1A36"
TOKEN = "A85C1AF99D030B9243723276"

def test_security_header():
    url = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/status"
    
    # Tentativa 1: Token no Header Client-Token tb
    headers = {
        "Client-Token": TOKEN
    }
    
    print(f"Tentando com Header Client-Token: {TOKEN}")
    try:
        resp = requests.get(url, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    test_security_header()
