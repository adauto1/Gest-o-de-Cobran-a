from app.main import SessionLocal, Customer
db = SessionLocal()
print("-" * 40)
for c in db.query(Customer).limit(5).all():
    print(f"{c.id}: {c.name} -> {c.profile_cobranca}")
print("-" * 40)
