from app.main import SessionLocal, Customer

def update_test_customer():
    db = SessionLocal()
    try:
        # Buscar o cliente de teste criado
        cliente = db.query(Customer).filter(Customer.name == "Cliente Teste WhatsApp").first()
        
        if cliente:
            print(f"Cliente encontrado: {cliente.name}")
            print(f"Telefone antigo: {cliente.whatsapp}")
            
            # Atualizar telefone
            cliente.whatsapp = "67996524740"
            db.commit()
            
            print(f"Telefone atualizado para: {cliente.whatsapp}")
            print("✅ Atualização concluída com sucesso!")
        else:
            print("❌ Cliente 'Cliente Teste WhatsApp' não encontrado.")
            
    except Exception as e:
        print(f"Erro ao atualizar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_test_customer()
