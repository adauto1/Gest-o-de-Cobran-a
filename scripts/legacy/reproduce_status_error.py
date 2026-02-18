import requests
from app.services.whatsapp import ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN

def test_status_no_header():
    print(f"Testing URL: {ZAPI_BASE_URL}/status")
    print("Attempt 1: No Headers (Like app/main.py)")
    try:
        response = requests.get(f"{ZAPI_BASE_URL}/status", timeout=10)
        print(f"Response: {response.status_code}")
        print(f"Data: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    print("\nAttempt 2: With Client-Token Header")
    try:
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        response = requests.get(f"{ZAPI_BASE_URL}/status", headers=headers, timeout=10)
        print(f"Response: {response.status_code}")
        print(f"Data: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_status_no_header()
