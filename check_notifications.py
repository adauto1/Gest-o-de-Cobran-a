from app.core.database import SessionLocal
from app.models import FinancialUser, FinancialAlertLog, Configuracoes, CollectionAction, today

db = SessionLocal()

# Configuracoes WhatsApp
config = db.query(Configuracoes).first()
print("=== CONFIGURACOES WHATSAPP ===")
if config:
    print(f"  WhatsApp Ativo: {config.whatsapp_ativo}")
    print(f"  Modo Teste: {config.whatsapp_modo_teste}")
else:
    print("  NENHUMA CONFIGURACAO ENCONTRADA!")

# Usuarios financeiros
print()
print("=== USUARIOS FINANCEIROS ===")
fins = db.query(FinancialUser).all()
if fins:
    for f in fins:
        status = "ATIVO" if f.active else "INATIVO"
        print(f"  [{status}] {f.name} - {f.phone}")
else:
    print("  NENHUM USUARIO FINANCEIRO CADASTRADO!")

# Logs de envio hoje
print()
print("=== LOGS DE ENVIO HOJE ===")
hoje = today()
logs = db.query(FinancialAlertLog).filter(FinancialAlertLog.alert_date == hoje).all()
if logs:
    for l in logs:
        print(f"  FinancialUser ID {l.financial_user_id} - {l.item_count} agendamentos - {l.alert_date}")
else:
    print(f"  Nenhum envio registrado hoje ({hoje})")

# Promessas de hoje
print()
print("=== PROMESSAS AGENDADAS PARA HOJE ===")
promises = db.query(CollectionAction).filter(
    CollectionAction.promised_date == hoje,
    CollectionAction.outcome == "PROMESSA"
).all()
print(f"  Total: {len(promises)}")
for p in promises:
    print(f"  - Cliente ID {p.customer_id}: R$ {p.promised_amount} | Data: {p.promised_date}")

db.close()

from datetime import datetime
now = datetime.now()
print()
print("=== DIAGNOSTICO DO LOOP ===")
print(f"  Hora atual: {now.hour}:{now.minute:02d}")
print(f"  Loop ativo entre 8h e 19h: {'SIM' if 8 <= now.hour <= 19 else 'NAO - fora do horario'}")
print(f"  Intervalo de verificacao: a cada 45 minutos (2700s)")
