import sys
import os
sys.path.append(os.getcwd())

try:
    from app.main import SessionLocal, CollectionRule
    db = SessionLocal()
    print("-" * 40)
    for r in db.query(CollectionRule).all():
        print(f"ID: {r.id} | Level: {r.level} | Days: {r.start_days} - {r.end_days}")
    print("-" * 40)
except Exception as e:
    print(f"ERROR: {e}")
