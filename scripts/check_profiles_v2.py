import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.main import SessionLocal, Customer

db = SessionLocal()
print("-" * 40)
# Check the first 20 customers to get a good sample
for c in db.query(Customer).limit(20).all():
    print(f"ID: {c.id} | Name: {c.name[:20]}... | Profile: '{c.profile_cobranca}'")
print("-" * 40)
