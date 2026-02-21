import logging
from datetime import datetime, timedelta
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


def run_director_alerts():
    """
    Verifica clientes com >= N parcelas vencidas (N configuravel).
    Envia alerta individual por cliente para cada diretor ativo.
    Frequencia: 1x por semana por cliente.
    Chamado pelo APScheduler a cada 1h.
    """
    db = SessionLocal()
    try:
        config = db.query(Configuracoes).first()
        if not config or not config.whatsapp_ativo:
            return

        directors = db.query(Director).filter(Director.active == True).all()
        if not directors:
            return

        min_parcelas = getattr(config, 'director_alert_min_installments', 3)
        semana_atras = today() - timedelta(days=7)

        critical_stmt = db.query(
            Installment.customer_id,
            func.count(Installment.id).label("qtd_vencida"),
            func.sum(Installment.open_amount).label("total_vencido"),
            func.min(Installment.due_date).label("mais_antiga")
        ).filter(
            Installment.status == "ABERTA",
            Installment.due_date < today()
        ).group_by(Installment.customer_id).having(
            func.count(Installment.id) >= min_parcelas
        ).all()

        for row in critical_stmt:
            cid, qtd, total, old_date = row

            last_alert = db.query(DirectorAlertLog).filter(
                DirectorAlertLog.customer_id == cid,
                DirectorAlertLog.alert_date >= semana_atras
            ).first()

            if not last_alert:
                cust = db.get(Customer, cid)
                dias_atraso = (today() - old_date).days
                valor_fmt = format_money(total)

                for direc in directors:
                    msg = (
                        f"ALERTA DE INADIMPLENCIA\n\n"
                        f"Cliente: *{cust.name}*\n"
                        f"Parcelas Vencidas: {qtd}\n"
                        f"Valor Total: {valor_fmt}\n"
                        f"Maior Atraso: {dias_atraso} dias\n\n"
                        f"Acesse o sistema para verificar."
                    )
                    enviar_whatsapp(direc.phone, msg, modo_teste=config.whatsapp_modo_teste)
                    db.add(DirectorAlertLog(director_id=direc.id, customer_id=cid, alert_date=today()))

        db.commit()
    except Exception as e:
        logger.error(f"[DirectorBot] Erro: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def trigger_financial_report(db: Session) -> dict:
    """
    Envia resumo de promessas do dia para todos os usuarios financeiros ativos.
    Retorna {'sent': N, 'skipped': N}.
    Pode ser chamada diretamente pelo endpoint run-now ou pelo job agendado.
    """
    config = db.query(Configuracoes).first()
    if not config or not config.whatsapp_ativo:
        return {"sent": 0, "skipped": 0}

    fin_users = db.query(FinancialUser).filter(FinancialUser.active == True).all()
    if not fin_users:
        return {"sent": 0, "skipped": 0}

    target_date = today()
    promises = db.query(CollectionAction).filter(
        CollectionAction.promised_date == target_date,
        CollectionAction.outcome == "PROMESSA"
    ).all()

    if not promises:
        return {"sent": 0, "skipped": 0}

    total_val = sum(p.promised_amount or Decimal(0) for p in promises)
    total_fmt = format_money(total_val)

    msg_lines = [f"Agendamentos de Hoje ({target_date.strftime('%d/%m')})"]
    for p in promises:
        c = db.get(Customer, p.customer_id)
        val_fmt = format_money(p.promised_amount or 0)
        msg_lines.append(f"- {c.name}: {val_fmt}")
    msg_lines.append(f"\nTotal Previsto: {total_fmt}")
    full_msg = "\n".join(msg_lines)

    sent = 0
    skipped = 0
    for fu in fin_users:
        existing = db.query(FinancialAlertLog).filter(
            FinancialAlertLog.financial_user_id == fu.id,
            FinancialAlertLog.alert_date == target_date
        ).first()
        if not existing:
            enviar_whatsapp(fu.phone, full_msg, modo_teste=config.whatsapp_modo_teste)
            db.add(FinancialAlertLog(
                financial_user_id=fu.id,
                alert_date=target_date,
                item_count=len(promises)
            ))
            sent += 1
        else:
            skipped += 1

    db.commit()
    return {"sent": sent, "skipped": skipped}


def run_financial_alerts():
    """
    Verifica e envia alertas de promessas de pagamento.
    So executa em horario comercial (8h-19h).
    Chamado pelo APScheduler a cada 45min.
    """
    now = datetime.now()
    if not (8 <= now.hour <= 19):
        return

    db = SessionLocal()
    try:
        trigger_financial_report(db)
    except Exception as e:
        logger.error(f"[FinancialBot] Erro: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
