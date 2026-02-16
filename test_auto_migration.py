import logging
import time
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import (
    Base, Customer, Installment, CollectionRule, SentMessage, 
    Configuracoes, WhatsappHistorico, today, DATABASE_URL
)
from app.scheduler import run_collection_check

# Configurar Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TEST_MIGRATION")

def test_migration():
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    print("\n🔹 INICIANDO TESTE DE MIGRAÇÃO AUTOMÁTICA E VARIÁVEIS 🔹\n")
    
    # 1. Garantir Modo Teste Ativo (para não enviar Z-API real se configurado)
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes(whatsapp_ativo=True, whatsapp_modo_teste=True)
        db.add(config)
    else:
        config.whatsapp_modo_teste = True
    db.commit()

    # 2. Criar Cenários
    # Cenário A: < 2 parcelas vencidas (1) -> Deve cair na LEVE
    # Cenário B: >= 2 parcelas vencidas (2) -> Deve cair na MODERADA
    # Cenário C: >= 3 parcelas vencidas (3) -> Deve cair na INTENSA
    
    # Prefixar para limpar depois
    PREFIX = "TEST_AUTO_"
    
    scenarios = [
        {"suffix": "A", "overdue_count": 1, "days_late": 3, "expected_profile": "LEVE", "rule_days": 3},
        {"suffix": "B", "overdue_count": 2, "days_late": 3, "expected_profile": "MODERADA", "rule_days": 3},
        {"suffix": "C", "overdue_count": 3, "days_late": 3, "expected_profile": "INTENSA", "rule_days": 3} # Intensa tem D-3? Tem preventivo. Vamos usar D+30 que tem na Intensa? Não.
        # Intensa tem: D-5, D-3, D-0, D+30...
        # Se eu simular atraso de 30 dias entra.
        # Mas quero testar a migração.
        # Se o cliente tem 3 parcelas vencidas há 3 dias.
        # Ele cai na INTENSA.
        # A INTENSA tem regra para 3 dias de atraso? 
        # Checking `configure_rules_new.py`:
        # Intensa: D-5, D-3, D-0, D+30. Não tem D+3!
        # Então se ele cair na Intensa com 3 dias de atraso, NENHUMA regra vai disparar (o que é correto, pois Intensa é focado em D+30).
        # Vamos ajustar o Cenário C para ter 35 dias de atraso para pegar a regra D+30.
    ]
    
    # Ajuste cenário C
    scenarios[2]["days_late"] = 35 
    scenarios[2]["rule_days"] = 30 # Intensa tem D+30

    created_ids = []

    try:
        for scen in scenarios:
            print(f"Criando Cenário {scen['suffix']} ({scen['expected_profile']})...")
            
            c = Customer(
                name=f"Cliente Teste {scen['suffix']}",
                external_key=f"{PREFIX}{scen['suffix']}",
                profile_cobranca="AUTOMATICO", # O segredo
                whatsapp="67999999999",
                cpf_cnpj="12345678900"
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            created_ids.append(c.id)
            
            # Criar Parcelas
            dt_venc = today() - timedelta(days=scen["days_late"])
            
            for i in range(scen["overdue_count"]):
                inst = Installment(
                    customer_id=c.id,
                    contract_id=f"CONTR-{scen['suffix']}",
                    installment_number=i+1,
                    due_date=dt_venc, # Todas vencidas na data simulada
                    amount=100.00,
                    open_amount=100.00,
                    status="ABERTA"
                )
                db.add(inst)
            db.commit()

        # 3. Rodar Scheduler
        print("Executando Scheduler...")
        # Recarregar sessão para scheduler limpo
        stats = run_collection_check(SessionLocal)
        print(f"Stats Scheduler: {stats}")
        
        # 4. Verificar Resultados
        with open("test_results.txt", "w", encoding="utf-8") as f:
            f.write("--- Verificação ---\n")
            for scen in scenarios:
                cid = created_ids[scenarios.index(scen)]
                
                # Buscar mensagem enviada
                msg = db.query(SentMessage).filter(SentMessage.customer_id == cid).order_by(SentMessage.created_at.desc()).first()
                
                success = False
                details = "Mensagem não encontrada"
                
                if msg:
                    # Verificar se a regra aplicada corresponde ao perfil esperado
                    rule = db.query(CollectionRule).filter(CollectionRule.id == msg.rule_id).first()
                    if rule and rule.level == scen["expected_profile"]:
                        success = True
                        details = f"Regra Aplicada: {rule.level} (ID {rule.id}, Dias {rule.start_days})"
                    else:
                        details = f"ERRO: Esperado {scen['expected_profile']}, Aplicada {rule.level if rule else 'None'}"
                    
                    # Verificar variáveis no texto
                    if "{nome}" in msg.message_body or "{valor}" in msg.message_body: 
                        success = False
                        details += " | ERRO: Variáveis não substituídas."
                
                status_icon = "✅" if success else "❌"
                f.write(f"{status_icon} Cenário {scen['suffix']}: {details}\n")
                if msg:
                    f.write(f"   Conteúdo: {msg.message_body[:100]}...\n")

    except Exception as e:
        print(f"❌ Erro Fatal no Teste: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 5. Limpeza
        print("\nLimpeza de dados de teste...")
        if created_ids:
            db.query(Installment).filter(Installment.customer_id.in_(created_ids)).delete(synchronize_session=False)
            db.query(SentMessage).filter(SentMessage.customer_id.in_(created_ids)).delete(synchronize_session=False)
            db.query(WhatsappHistorico).filter(WhatsappHistorico.cliente_id.in_(created_ids)).delete(synchronize_session=False)
            db.query(Customer).filter(Customer.id.in_(created_ids)).delete(synchronize_session=False)
            db.commit()
            print("Dados limpos.")

if __name__ == "__main__":
    test_migration()
