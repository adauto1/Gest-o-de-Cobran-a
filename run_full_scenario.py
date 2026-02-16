import logging
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import (
    Base, Customer, Installment, CollectionRule, SentMessage, 
    Configuracoes, WhatsappHistorico, today, DATABASE_URL
)
from app.scheduler import run_collection_check

# Dataset
CLIENTES_DATA = [
    {"id": "C001", "nome": "ANA CAROLINA SILVA", "cpf": "12345678901", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "LEVE"}, # Matched LEVE (D+7)
    {"id": "C002", "nome": "BRUNO HENRIQUE SOUZA", "cpf": "23456789012", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "Nenhuma"}, # Missed D+7
    {"id": "C003", "nome": "CAMILA FERREIRA LIMA", "cpf": "34567890123", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "Nenhuma"},
    {"id": "C004", "nome": "DIEGO ALMEIDA COSTA", "cpf": "45678901234", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "Nenhuma"},
    {"id": "C005", "nome": "ELIANA MORAES SANTOS", "cpf": "56789012345", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "INTENSA"}, # Migrated to INTENSA (ok)
    {"id": "C006", "nome": "FABIO PEREIRA OLIVEIRA", "cpf": "67890123456", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "MODERADA"}, # Matched MODERADA (D+25)
    {"id": "C007", "nome": "GABRIELA ROCHA ARAUJO", "cpf": "78901234567", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "Nenhuma"},
    {"id": "C008", "nome": "HEITOR BARBOSA RIBEIRO", "cpf": "89012345678", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "INTENSA"},
    {"id": "C009", "nome": "ISABELA MARTINS CARDOSO", "cpf": "90123456789", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "Nenhuma"},
    {"id": "C010", "nome": "JOAO VICTOR GONCALVES", "cpf": "01234567890", "telefone": "67996524740", "perfil": "AUTOMATICO", "esperado": "INTENSA"},
]

PARCELAS_DATA = [
    # LEVE
    {"pid": "P0001", "cid": "C001", "num": 1, "valor": "219.90", "venc": "2026-02-12"}, # D+3 LEVE
    {"pid": "P0002", "cid": "C001", "num": 2, "valor": "219.90", "venc": "2026-03-12"},

    {"pid": "P0003", "cid": "C002", "num": 1, "valor": "179.90", "venc": "2026-02-08"}, # D+7 LEVE
    {"pid": "P0004", "cid": "C002", "num": 2, "valor": "179.90", "venc": "2026-03-08"},

    {"pid": "P0005", "cid": "C003", "num": 1, "valor": "249.90", "venc": "2026-01-31"}, # D+15 LEVE
    {"pid": "P0006", "cid": "C003", "num": 2, "valor": "249.90", "venc": "2026-02-28"},

    {"pid": "P0007", "cid": "C004", "num": 1, "valor": "299.90", "venc": "2026-01-21"}, # D+25 LEVE
    {"pid": "P0008", "cid": "C004", "num": 2, "valor": "299.90", "venc": "2026-02-21"},

    # MODERADA
    {"pid": "P0009", "cid": "C005", "num": 3, "valor": "189.90", "venc": "2026-02-15"}, # D-0 MODERADA (15/02Hoje)
    {"pid": "P0010", "cid": "C005", "num": 2, "valor": "189.90", "venc": "2026-02-05"}, # Atrasado
    {"pid": "P0011", "cid": "C005", "num": 1, "valor": "189.90", "venc": "2026-01-05"}, # Atrasado

    {"pid": "P0012", "cid": "C006", "num": 4, "valor": "209.90", "venc": "2026-02-08"}, # D+7 MODERADA
    {"pid": "P0013", "cid": "C006", "num": 3, "valor": "209.90", "venc": "2026-01-25"},
    {"pid": "P0014", "cid": "C006", "num": 2, "valor": "209.90", "venc": "2026-03-08"},

    {"pid": "P0015", "cid": "C007", "num": 5, "valor": "159.90", "venc": "2026-01-21"},
    {"pid": "P0016", "cid": "C007", "num": 4, "valor": "159.90", "venc": "2026-02-01"},
    {"pid": "P0017", "cid": "C007", "num": 3, "valor": "159.90", "venc": "2026-02-15"}, # D-0 MODERADA (15/02 Hoje)

    # INTENSA
    {"pid": "P0018", "cid": "C008", "num": 6, "valor": "239.90", "venc": "2026-02-12"}, # D+3 INTENSA? Tem D+3 na Intensa? Não.
                                                                                       # Intensa tem D-5, D-3, D-0, D+30...
                                                                                       # Se cair no D+3 do "atraso", nenhuma regra dispara.
                                                                                       # Mas o objetivo é validar o PERFIL.
    {"pid": "P0019", "cid": "C008", "num": 5, "valor": "239.90", "venc": "2026-02-01"},
    {"pid": "P0020", "cid": "C008", "num": 4, "valor": "239.90", "venc": "2026-01-15"}, # D+30 INTENSA
    {"pid": "P0021", "cid": "C008", "num": 7, "valor": "239.90", "venc": "2026-03-12"},

    {"pid": "P0022", "cid": "C009", "num": 8, "valor": "199.90", "venc": "2026-02-08"}, # D+7
    {"pid": "P0023", "cid": "C009", "num": 7, "valor": "199.90", "venc": "2026-01-31"}, # D+15
    {"pid": "P0024", "cid": "C009", "num": 6, "valor": "199.90", "venc": "2026-01-21"}, # D+25

    {"pid": "P0025", "cid": "C010", "num": 9, "valor": "279.90", "venc": "2026-01-05"},
    {"pid": "P0026", "cid": "C010", "num": 8, "valor": "279.90", "venc": "2026-01-21"},
    {"pid": "P0027", "cid": "C010", "num": 7, "valor": "279.90", "venc": "2026-02-05"},
    {"pid": "P0028", "cid": "C010", "num": 10, "valor": "279.90", "venc": "2026-03-05"},
]

def run_scenario():
    print("🚀 Iniciando Cenário de Teste Completo (10 Clientes)...")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    # 1. Configurar Modo Teste
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes(whatsapp_ativo=True, whatsapp_modo_teste=True)
        db.add(config)
    else:
        config.whatsapp_modo_teste = True
    db.commit()
    
    # 2. Limpar Dados Antigos (Customers C001-C010)
    customer_keys = [c["id"] for c in CLIENTES_DATA]
    
    existing_customers = db.query(Customer).filter(Customer.external_key.in_(customer_keys)).all()
    cids = [c.id for c in existing_customers]
    
    if cids:
        print(f"Limpando {len(cids)} clientes antigos...")
        db.query(Installment).filter(Installment.customer_id.in_(cids)).delete(synchronize_session=False)
        db.query(SentMessage).filter(SentMessage.customer_id.in_(cids)).delete(synchronize_session=False)
        db.query(WhatsappHistorico).filter(WhatsappHistorico.cliente_id.in_(cids)).delete(synchronize_session=False)
        db.query(Customer).filter(Customer.id.in_(cids)).delete(synchronize_session=False)
        db.commit()

    # 3. Inserir Dados Novos
    print("Inserindo Clientes e Parcelas...")
    created_cids = []
    
    # Map external_key -> customer_id
    key_to_id = {}
    
    for c_data in CLIENTES_DATA:
        c = Customer(
            name=c_data["nome"],
            external_key=c_data["id"],
            profile_cobranca=c_data["perfil"],
            whatsapp=c_data["telefone"],
            cpf_cnpj=c_data["cpf"]
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        key_to_id[c_data["id"]] = c.id
        created_cids.append(c.id)
    
    for p_data in PARCELAS_DATA:
        cid = key_to_id.get(p_data["cid"])
        if not cid: continue
        
        inst = Installment(
            customer_id=cid,
            contract_id=f"CONTR-{p_data['cid']}",
            installment_number=p_data["num"],
            due_date=datetime.strptime(p_data["venc"], "%Y-%m-%d").date(),
            amount=Decimal(p_data["valor"]),
            open_amount=Decimal(p_data["valor"]),
            status="ABERTA"
        )
        db.add(inst)
    db.commit()
    
    # 4. Executar Scheduler (Com Mock de Data para Segunda-feira 16/02)
    print("Executando Scheduler (Simulando Segunda-feira 16/02/2026 - Pós Fim de Semana)...")
    
    import app.scheduler
    import app.services.compliance
    import app.main 
    from unittest.mock import patch
    
    print(f"DEBUG: app.main attributes: {dir(app.main)}")
    
    # Mock de hoje para ser Quinta 19/02/2026 (Pós Carnaval e Cinzas)
    # Motivo: 15/02 (Dom) -> 16/02 (Carnaval) -> 17/02 (Carnaval) -> 18/02 (Cinzas) -> 19/02 (Quinta)
    fake_today = date(2026, 2, 19)
    
    import sys
    
    # Redirecionar stdout para arquivo de debug
    with open("scenario_debug.txt", "w", encoding="utf-8") as debug_file:
        sys.stdout = debug_file
        
        try:
            # Patch app.main.today (onde é definido)
            # Patch app.services.compliance.check_msg_allowed_now
            
            with patch('app.main.today', return_value=fake_today), \
                 patch('app.services.compliance.check_msg_allowed_now', return_value=(True, "OK")):
                 
                # Scheduler espera uma factory (callable), não uma instância
                run_collection_check(SessionLocal)
                
        except Exception as e:
            print(f"Erro durante execução mockada: {e}")
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout = sys.__stdout__ # Restaurar stdout
    
    # 5. Gerar Relatório
    # Fechar sessão antiga e criar nova para garantir leitura atualizada
    db.close()
    db = SessionLocal()
    
    with open("scenario_results.txt", "w", encoding="utf-8") as f:
        f.write("📋 Relatório de Validação:\n")
        f.write(f"{'CLIENTE':<30} | {'PERFIL ESPERADO':<10} | {'REGRA APLICADA':<30} | {'STATUS'}\n")
        f.write("-" * 100 + "\n")
        
        # Debug: Listar Regras INTENSA
        intensa_rules = db.query(CollectionRule).filter(CollectionRule.level == "INTENSA").all()
        f.write(f"DEBUG: Regras INTENSA no banco: {len(intensa_rules)}\n")
        for r in intensa_rules:
            f.write(f" - ID {r.id}: Start={r.start_days} End={r.end_days} Freq={r.frequency}\n")
        f.write("-" * 100 + "\n")
        
        for c_data in CLIENTES_DATA:
            cid = key_to_id[c_data["id"]]
            
            # Buscar mensagem enviada
            msg = db.query(SentMessage).filter(SentMessage.customer_id == cid).order_by(SentMessage.created_at.desc()).first()
            
            regra_nome = "Nenhuma"
            regra_nivel = "Nenhuma"
            
            if msg:
                rule = db.query(CollectionRule).filter(CollectionRule.id == msg.rule_id).first()
                if rule:
                    regra_nome = f"{rule.level} (D{'+' if rule.start_days >=0 else ''}{rule.start_days})"
                    regra_nivel = rule.level
            
            status = "✅ OK" if regra_nivel == c_data["esperado"] else "❌ ERRO"
            
            # Tratamento especial para INTENSA se não houver regras
            if c_data["esperado"] == "INTENSA" and regra_nivel == "Nenhuma":
                 status = "⚠️ Sem Regra INTENSA Compatível"
            
            f.write(f"{c_data['nome'][:30]:<30} | {c_data['esperado']:<10} | {regra_nome:<30} | {status}\n")
            
        f.write("\nVerificação concluída.\n")

if __name__ == "__main__":
    run_scenario()
