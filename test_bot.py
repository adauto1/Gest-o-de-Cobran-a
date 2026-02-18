from app.core.database import SessionLocal
from app.models import Configuracoes, FinancialUser, CollectionAction, today, Customer
from app.services.whatsapp import enviar_whatsapp
from app.core.helpers import format_money
from decimal import Decimal
import asyncio

async def trigger_manual():
    db = SessionLocal()
    try:
        config = db.query(Configuracoes).first()
        if not config or not config.whatsapp_ativo:
            print("WhatsApp inativo nas configs.")
            return

        fin_users = db.query(FinancialUser).filter(FinancialUser.active == True).all()
        if not fin_users:
            print("Sem usuarios financeiros ativos.")
            return

        target_date = today()
        promises = db.query(CollectionAction).filter(
            CollectionAction.promised_date == target_date,
            CollectionAction.outcome == "PROMESSA"
        ).all()

        if not promises:
            print("Sem promessas para hoje.")
            # Vamos testar o envio com uma mensagem genérica se não houver promessas
            full_msg = f"📡 *Teste de Robô Financeiro*\n\nNenhuma promessa agendada para hoje ({target_date.strftime('%d/%m')})."
        else:
            total_val = sum(p.promised_amount or Decimal(0) for p in promises)
            total_fmt = format_money(total_val)

            msg_lines = [f"📅 *Agendamentos de Hoje ({target_date.strftime('%d/%m')})*"]
            for p in promises:
                c = db.get(Customer, p.customer_id)
                val_fmt = format_money(p.promised_amount or 0)
                msg_lines.append(f"• {c.name}: {val_fmt}")
            msg_lines.append(f"\n💰 *Total Previsto: {total_fmt}*")
            full_msg = "\n".join(msg_lines)

        print("Enviando notificacao manual para teste...")
        for fu in fin_users:
            res = enviar_whatsapp(fu.phone, full_msg, modo_teste=False)
            print(f"Resultado para {fu.name} ({fu.phone}): {res}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(trigger_manual())
