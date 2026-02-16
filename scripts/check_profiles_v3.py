import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

try:
    from app.main import SessionLocal, Customer
    db = SessionLocal()
    print("-" * 40)
    count = db.query(Customer).count()
    print(f"Total Customers: {count}")
    
    # Check the first 20 customers to get a good sample
    for c in db.query(Customer).limit(20).all():
        prof = c.profile_cobranca
        print(f"ID: {c.id} | Name: {c.name[:20]}... | Profile Raw: '{prof}' | Type: {type(prof)}")
    print("-" * 40)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
