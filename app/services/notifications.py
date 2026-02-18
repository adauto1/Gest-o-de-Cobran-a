import asyncio
import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from decimal import Decimal

from app.core.database import SessionLocal
from app.core.helpers import format_money
from app.models import (
    Configuracoes, Director, Customer, Installment, DirectorAlertLog,
    FinancialUser, CollectionAction, FinancialAlertLog, today
)
from app.services.whatsapp import enviar_whatsapp

logger = logging.getLogger(__name__)


async def director_notification_loop():
    """
    Loop infinito que roda a cada 1 hora.
    Verifica clientes com >= 3 parcelas vencidas.
    Envia resumo para todos os diretores ativos.
    """
    while True:
        db = SessionLocal()
        try:
            config = db.query(Configuracoes).first()
            if config and config.whatsapp_ativo:
                directors = db.query(Director).filter(Director.active == True).all()
                if directors:
                    # Subquery para contar parcelas vencidas
                    critical_stmt = db.query(
                        Installment.customer_id,
                        func.count(Installment.id).label("qtd_vencida"),
                        func.sum(Installment.open_amount).label("total_vencido"),
                        func.min(Installment.due_date).label("mais_antiga")
                    ).filter(
                        Installment.status == "ABERTA",
                        Installment.due_date < today()
                    ).group_by(Installment.customer_id).having(func.count(Installment.id) >= 3).all()

                    for row in critical_stmt:
                        cid, qtd, total, old_date = row
                        last_alert = db.query(DirectorAlertLog).filter(
                             DirectorAlertLog.customer_id == cid,
                             DirectorAlertLog.alert_date >= today()
                        ).first()

                        if not last_alert:
                            cust = db.get(Customer, cid)
                            dias_atraso = (today() - old_date).days
                            valor_fmt = format_money(total)

                            msg = (
                                f"🚨 *ALERTA DE INADIMPLÊNCIA* 🚨\n\n"
                                f"Cliente: *{cust.name}*\n"
                                f"Parcelas Vencidas: {qtd}\n"
                                f"Valor Total: {valor_fmt}\n"
                                f"Maior Atraso: {dias_atraso} dias\n\n"
                                f"Acesse o sistema para verificar."
                            )

                            for direc in directors:
                                enviar_whatsapp(direc.phone, msg, modo_teste=config.whatsapp_modo_teste)
                                log = DirectorAlertLog(director_id=direc.id, customer_id=cid, alert_date=today())
                                db.add(log)
                            db.commit()
                            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"[DirectorBot] Erro: {e}", exc_info=True)
        finally:
            db.close()
        await asyncio.sleep(3600)


async def financial_notification_loop():
    """Processa notificações de promessas de pagamento."""
    while True:
        now = datetime.now()
        if 8 <= now.hour <= 19:
            db = SessionLocal()
            try:
                config = db.query(Configuracoes).first()
                if config and config.whatsapp_ativo:
                    fin_users = db.query(FinancialUser).filter(FinancialUser.active == True).all()
                    if fin_users:
                        target_date = today()
                        promises = db.query(CollectionAction).filter(
                            CollectionAction.promised_date == target_date,
                            CollectionAction.outcome == "PROMESSA"
                        ).all()

                        if promises:
                            # Calcula o total corretamente (bug corrigido: s_val era o último item)
                            total_val = sum(p.promised_amount or Decimal(0) for p in promises)
                            total_fmt = format_money(total_val)

                            msg_lines = [f"📅 *Agendamentos de Hoje ({target_date.strftime('%d/%m')})*"]
                            for p in promises:
                                c = db.get(Customer, p.customer_id)
                                val_fmt = format_money(p.promised_amount or 0)
                                msg_lines.append(f"• {c.name}: {val_fmt}")
                            msg_lines.append(f"\n💰 *Total Previsto: {total_fmt}*")
                            full_msg = "\n".join(msg_lines)

                            for fu in fin_users:
                                log = db.query(FinancialAlertLog).filter(
                                    FinancialAlertLog.financial_user_id == fu.id,
                                    FinancialAlertLog.alert_date == target_date
                                ).first()
                                if not log:
                                    enviar_whatsapp(fu.phone, full_msg, modo_teste=config.whatsapp_modo_teste)
                                    db.add(FinancialAlertLog(
                                        financial_user_id=fu.id,
                                        alert_date=target_date,
                                        item_count=len(promises)
                                    ))
                            db.commit()
            except Exception as e:
                logger.error(f"[FinancialBot] Erro: {e}", exc_info=True)
            finally:
                db.close()
        await asyncio.sleep(2700)
