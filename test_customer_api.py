import requests

# Teste 1: Login
session = requests.Session()
login_data = {
    "email": "admin@portalmoveis.com",
    "password": "admin123"
}
login_resp = session.post("http://localhost:8000/login", data=login_data, allow_redirects=False)
print(f"Login status: {login_resp.status_code}")
print(f"Cookies: {session.cookies}")

# Teste 2: Buscar cliente ID 1
customer_resp = session.get("http://localhost:8000/api/customers/1")
print(f"\nGET /api/customers/1 status: {customer_resp.status_code}")
if customer_resp.status_code == 200:
    print(f"Response: {customer_resp.json()}")
else:
    print(f"Error: {customer_resp.text}")
