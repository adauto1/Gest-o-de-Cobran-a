from app.main import SessionLocal, Customer, Installment, today
from datetime import timedelta
import random

def create_or_update_test_data():
    db = SessionLocal()
    
    print("--- Gerenciando Dados de Teste ---")
    
    # 1. Buscar ou Criar Cliente
    cliente = db.query(Customer).filter(Customer.name == "Cliente Teste WhatsApp").first()
    
    if cliente:
        print(f"✅ Cliente encontrado: {cliente.name} (ID: {cliente.id})")
        print(f"   Atualizando telefone: {cliente.whatsapp} -> 67996524740")
        cliente.whatsapp = "67996524740"
    else:
        print("🆕 Criando novo Cliente de Teste...")
        cliente = Customer(
            name="Cliente Teste WhatsApp",
            external_key=f"TESTE_{random.randint(1000, 9999)}",
            cpf_cnpj="000.000.000-00",
            whatsapp="67996524740",
            store="LOJA TESTE",
            address="Rua dos Testes, 123 - Centro"
        )
        db.add(cliente)
    
    db.commit()
    db.refresh(cliente)
    
    # 2. Resetar Parcelas (Deletar e Recriar para garantir o cenário)
    num_deleted = db.query(Installment).filter(Installment.customer_id == cliente.id).delete()
    print(f"🧹 Parcelas antigas removidas: {num_deleted}")
    
    t = today()
    parcels = [
        # Vencida há 10 dias
        {"due": t - timedelta(days=10), "amt": 150.00, "n": 1},
        # Vence Hoje
        {"due": t, "amt": 200.50, "n": 2},
        # Vence em 5 dias
        {"due": t + timedelta(days=5), "amt": 300.00, "n": 3}
    ]
    
    print("📝 Criando novas parcelas...")
    for p in parcels:
        inst = Installment(
            customer_id=cliente.id,
            contract_id=f"CTR-{cliente.id}",
            installment_number=p["n"],
            issue_date=t - timedelta(days=30),
            due_date=p["due"],
            amount=p["amt"],
            open_amount=p["amt"],
            status="ABERTA"
        )
        db.add(inst)
    
    db.commit()
    print("✅ Dados de teste atualizados com sucesso!")
    print(f"   Cliente: {cliente.name}")
    print(f"   WhatsApp: {cliente.whatsapp}")
    print(f"   Parcelas criadas: {len(parcels)}")

if __name__ == "__main__":
    create_or_update_test_data()
