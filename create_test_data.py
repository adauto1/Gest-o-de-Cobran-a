from app.main import SessionLocal, Customer, Installment, today
from datetime import timedelta
import random

def create_test_data():
    db = SessionLocal()
    
    print("Criando dados de teste...")
    
    # 1. Criar Cliente de Teste
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
    print(f"Cliente criado: {cliente.name} (ID: {cliente.id})")
    
    # 2. Criar Parcelas
    t = today()
    parcels = [
        # Vencida há 10 dias (Prioridade Alta)
        {"due": t - timedelta(days=10), "amt": 150.00, "n": 1},
        
        # Vence Hoje (Para testar filtro 'Vence Hoje')
        {"due": t, "amt": 200.50, "n": 2},
        
        # Vence em 5 dias (Futura)
        {"due": t + timedelta(days=5), "amt": 300.00, "n": 3}
    ]
    
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
    print("Parcelas criadas com sucesso!")
    print("\nAGORA O QUE FAZER:")
    print("1. Vá na Fila de Cobrança.")
    print(f"2. Procure por '{cliente.name}'.")
    print("3. Edite o telefone para o SEU número real para testar o envio.")
    print("4. Clique no botão do WhatsApp.")

if __name__ == "__main__":
    create_test_data()
