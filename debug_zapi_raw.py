import http.client
import json

INSTANCE_ID = "3EECA6A04BF7413E6BA8B269A10D1A36"
TOKEN = "A85C1AF99D030B9243723276"

def test_raw():
    conn = http.client.HTTPSConnection("api.z-api.io")
    
    path = f"/instances/{INSTANCE_ID}/token/{TOKEN}/status"
    
    print(f"GET {path}")
    
    headers = {
        "User-Agent": "curl/7.68.0",
        "Client-Token": "F2d93bb4f23434f82bb1b4d718cd3b74fS"
    }
    conn.request("GET", path, headers=headers)
    
    res = conn.getresponse()
    data = res.read()
    
    print(f"Status: {res.status}")
    print(f"Data: {data.decode('utf-8')}")

if __name__ == "__main__":
    test_raw()
