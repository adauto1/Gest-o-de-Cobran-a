import requests

def test_routes():
    base_url = "http://127.0.0.1:8000"
    routes = ["/", "/login", "/dashboard", "/customers", "/queue"]
    
    for route in routes:
        url = base_url + route
        try:
            # allow_redirects=False to see 302
            resp = requests.get(url, allow_redirects=False, timeout=5)
            print(f"Route: {route} | Status: {resp.status_code}")
        except Exception as e:
            print(f"Route: {route} | Error: {e}")

if __name__ == "__main__":
    test_routes()
