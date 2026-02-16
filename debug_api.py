import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from app.main import api_get_outbox, SessionLocal, MessageDispatchLog

# Mock Request
class MockRequest:
    def __init__(self):
        self.headers = {}
        self.state = type('obj', (object,), {'user': MagicMock(role="ADMIN")}) 

# We need to bypass require_login decorator or check.
# In main.py:
# user = require_login(request, db)
# require_login checks session.
# We can mock require_login in app.main if we can import it.
import app.main
app.main.require_login = lambda r, d: MagicMock(role="ADMIN", id=1)

db = SessionLocal()

print("Testing api_get_outbox...")
try:
    # Test valid call
    result = api_get_outbox(
        request=MockRequest(),
        date_from="2026-02-16",
        date_to="2026-02-16",
        status="",
        regua="",
        cliente="",
        only_test=False,
        only_rescheduled=False,
        page=1,
        limit=50,
        db=db
    )
    print("Success!")
    print("KPIs:", result['kpis'])
    print("Data Length:", len(result['data']))
    if len(result['data']) > 0:
        print("First Item:", result['data'][0])

except Exception as e:
    print("CRASHED:")
    import traceback
    traceback.print_exc()

finally:
    db.close()
