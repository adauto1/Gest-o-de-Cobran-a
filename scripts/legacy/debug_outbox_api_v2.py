import requests
import json

url = "http://localhost:8000/api/mensagens/outbox"
params = {
    "date_from": "2026-02-15",
    "date_to": "2026-02-15"
}

try:
    # Assuming the current session might be authenticated if I were a browser,
    # but here I might get 401. However, if I get 500, that's the bug.
    resp = requests.get(url, params=params)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("Success")
        print(json.dumps(resp.json(), indent=2))
    else:
        print("Error Response:")
        print(resp.text)
except Exception as e:
    print(f"Request failed: {e}")
