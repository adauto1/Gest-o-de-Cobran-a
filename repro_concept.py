import requests
import sys

try:
    # URL to test (assuming default port 8000)
    url = "http://127.0.0.1:8000/api/mensagens/outbox"
    
    # Params matching the default view
    params = {
        "page": 1,
        "limit": 50,
        "date_from": "2026-02-16",
        "date_to": "2026-02-16",
        "status": "",
        "regua": "",
        "cliente": "",
        "only_test": ""
    }
    
    # We need authentication cookies?
    # The API requires login: user = require_login(request, db)
    # Since we can't easily fake the session cookie without logging in, 
    # we might need to bypass login or use a valid session id.
    # OR, we can use a script that imports the app and calls the function directly?
    # Calling function directly is better to see the traceback in python.
    
    print("Testing via internal function call...")
    
    from app.main import api_get_outbox, SessionLocal
    from fastapi import Request
    
    # Mock Request
    class MockRequest:
        def __init__(self):
            self.cookies = {} # Check valid session
            self.headers = {}
            self.state = type('obj', (object,), {'user': None})
            
    # However, require_login checks session token in cookie. 
    # To bypass, we can mock require_login or set a valid token.
    # Easier to mock require_login if possible? 
    # Or just use the mock user directly if we can modify the code? 
    # We can't easily modify the running code without reloading.
    
    # Let's try to simulate a valid session using `run_command` to curl with the cookie 
    # IF we knew the cookie. We don't.
    
    # Revert to python script:
    # We can bypass authentication by temporarily modifying main.py or by 
    # creating a testing context. 
    
    # Actually, the user is running the app with `--reload`, so I can just run a python script 
    # that imports the function and MOCKS `require_login`.
    
    pass

except Exception as e:
    print(e)
