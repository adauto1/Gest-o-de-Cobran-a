import os
import sys
from datetime import date, datetime

# Adiciona o diretório atual ao path para encontrar o app
sys.path.append(os.getcwd())

from app.main import SessionLocal, Configuracoes, Installment, CollectionRule, Customer, MessageDispatchLog

def diag():
    db = SessionLocal()
    try:
        print("--- DIAGNÓSTICO DO SISTEMA ---")
        
        # 1. Verificar Configurações
        config = db.query(Configuracoes).first()
        print(f"WhatsApp Ativo: {config.whatsapp_ativo if config else 'NÃO EXISTE'}")
        print(f"Modo Teste: {config.whatsapp_modo_teste if config else 'N/A'}")
        
        # 2. Verificar Regras
        rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
        print(f"Regras Ativas: {len(rules)}")
        for i, r in enumerate(rules[:3]):
             print(f"  - Regra {i+1}: {r.level} (Início: {r.start_days}, Fim: {r.end_days})")
        
        # 3. Verificar Parcelas e Clientes
        total_installments = db.query(Installment).filter(Installment.status == "ABERTA").count()
        print(f"Total Parcelas em Aberto: {total_installments}")
        
        # 4. Simular Busca do Scheduler
        open_insts = (
            db.query(Installment)
            .join(Customer)
            .filter(Installment.status == "ABERTA", Installment.open_amount > 0)
            .all()
        )
        print(f"Parcelas encontradas pelo Join: {len(open_insts)}")
        
        # Agrupar por cliente (como no scheduler)
        customer_map = {}
        for inst in open_insts:
            cid = inst.customer_id
            if cid not in customer_map:
                customer_map[cid] = {"customer": inst.customer, "installments": []}
            customer_map[cid]["installments"].append(inst)
        
        print(f"Total de Clientes mapeados: {len(customer_map)}")
        
        # 5. Verificar Logs de hoje
        today_start = datetime.combine(date.today(), datetime.min.time())
        logs = db.query(MessageDispatchLog).filter(MessageDispatchLog.created_at >= today_start).count()
        print(f"Logs criados hoje: {logs}")
        
    finally:
        db.close()

if __name__ == "__main__":
    diag()
