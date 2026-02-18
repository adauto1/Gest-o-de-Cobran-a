import requests

def test_priority_api():
    base_url = "http://127.0.0.1:8000"
    route = "/api/fila/prioridade?page=1&limit=2"
    url = base_url + route
    try:
        # We might need to login first or use a session
        session = requests.Session()
        # Usually we need a cookie. Since I don't have one here, I'll see if it return 401 or works (if no auth, which is unlikely)
        resp = session.get(url, timeout=5)
        print(f"Route: {route} | Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response JSON keys:", resp.json().keys())
        else:
            print("Response Text:", resp.text[:200])
    except Exception as e:
        print(f"Route: {route} | Error: {e}")

if __name__ == "__main__":
    test_priority_api()
