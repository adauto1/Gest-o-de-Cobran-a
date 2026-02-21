# --------------------------------------------------------------------------
# Scheduler — Verificação diária da régua de cobrança (Fase 1: Simulação)
# --------------------------------------------------------------------------
from __future__ import annotations

import logging
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from app.models import (
    Customer, Installment, CollectionRule, SentMessage, MessageDispatchLog,
    Configuracoes, WhatsappHistorico, today as get_today
)
from app.core.helpers import format_money
from app.services.whatsapp import enviar_whatsapp

def _retry_rescheduled(db: Session, config, is_time_allowed: bool) -> int:
    """
    Reenvia mensagens RESCHEDULED do dia atual quando o horário de compliance permite.
    Retorna a quantidade de mensagens reenviadas com sucesso.
    """
    if not is_time_allowed:
        return 0

    _today = get_today()
    pending = (
        db.query(MessageDispatchLog)
        .filter(
            MessageDispatchLog.status == "RESCHEDULED",
            MessageDispatchLog.scheduled_for == _today,
        )
        .all()
    )

    retried = 0
    for entry in pending:
        phone = entry.destination_phone
        msg_body = entry.message_rendered
        if not phone or not msg_body:
            continue

        res = enviar_whatsapp(phone, msg_body, modo_teste=config.whatsapp_modo_teste)
        new_status = res.get("modo", "FAILED")
        entry.status = new_status
        entry.compliance_block_reason = "OK"
        entry.error_message = res.get("erro")
        entry.executed_at = datetime.utcnow()

        if new_status in ("SIMULADO", "ENVIADO"):
            retried += 1
            hist = WhatsappHistorico(
                cliente_id=entry.customer_id,
                telefone=phone,
                mensagem=msg_body,
                tipo="regua_retry",
                status=new_status.lower(),
                resposta=str(res),
            )
            db.add(hist)

    if retried:
        db.commit()
        log.info(f"[RETRY] {retried} mensagens RESCHEDULED reenviadas.")
    return retried


def run_collection_check(session_factory) -> dict:
    """
    Verifica todos os clientes com parcelas vencidas/a vencer,
    aplica a régua de cobrança e registra mensagens.
    Retorna estatísticas da execução.
    """
    db: Session = session_factory()
    stats = {"checked": 0, "created": 0, "rescheduled": 0, "retried": 0, "skipped_freq": 0, "skipped_no_phone": 0}

    try:
        _today = get_today()

        # 1) Buscar regras ativas
        rules = db.query(CollectionRule).filter(CollectionRule.active == True).all()
        if not rules:
            log.info("Nenhuma regra ativa encontrada.")
            print("DEBUG: Nenhuma regra ativa encontrada.")
            return stats
        
        print(f"DEBUG: Total Active Rules in DB: {len(rules)}")

        # 1.5) Buscar configurações de WhatsApp
        config = db.query(Configuracoes).first()
        if not config:
            config = Configuracoes(whatsapp_ativo=False, whatsapp_modo_teste=True)
            db.add(config)
            db.commit()
        
        if not config.whatsapp_ativo:
            log.info("Régua de cobrança ignorada (WhatsApp desativado nas configurações).")
            return stats

        # 1.6) Verificar compliance de horário UMA VEZ (válido para todo o ciclo)
        from app.services.compliance import calcular_data_disparo, check_msg_allowed_now, TZ
        is_time_allowed, block_reason = check_msg_allowed_now(return_reason=True)

        # 1.7) Reenviar mensagens RESCHEDULED do dia que ainda estão pendentes
        stats["retried"] = _retry_rescheduled(db, config, is_time_allowed)

        # 2) Buscar todas as parcelas abertas
        open_insts = (
            db.query(Installment)
            .join(Customer)
            .filter(Installment.status == "ABERTA", Installment.open_amount > 0)
            .all()
        )

        # Agrupar por cliente
        customer_map: dict = {}
        for inst in open_insts:
            cid = inst.customer_id
            if cid not in customer_map:
                customer_map[cid] = {
                    "customer": inst.customer,
                    "installments": [],
                }
            customer_map[cid]["installments"].append(inst)

        # 3) Para cada cliente, aplicar regras
        for cid, data in customer_map.items():
            customer = data["customer"]
            insts = data["installments"]
            stats["checked"] += 1

            # Pular clientes com mensagens desativadas
            if not getattr(customer, 'msgs_ativo', True):
                continue

            # Calcular atraso máximo e totais
            max_overdue = 0
            total_open = Decimal("0")
            nearest_due = None

            for inst in insts:
                delay = (_today - inst.due_date).days
                if delay > max_overdue:
                    max_overdue = delay
                total_open += Decimal(str(inst.open_amount))
                if nearest_due is None or inst.due_date < nearest_due:
                    nearest_due = inst.due_date

            # Encontrar regra aplicável
            # Lógica de Migração Automática de Nível
            c_profile = getattr(customer, "profile_cobranca", "AUTOMATICO")
            effective_profile = c_profile

            # Calcular totais do cliente para variáveis e decisão
            # total_open já calculado acima.
            # contar parcelas vencidas
            overdue_count = sum(1 for i in insts if (_today - i.due_date).days > 0)
            
            if c_profile == "AUTOMATICO":
                # Regra de Migração Automática:
                # < 30 dias -> LEVE
                # >= 30 dias -> MODERADA
                # >= 90 dias -> INTENSA
                if max_overdue >= 90:
                    effective_profile = "INTENSA"
                elif max_overdue >= 30:
                    effective_profile = "MODERADA"
                else:
                    effective_profile = "LEVE"
            
            # Filtrar regras baseadas no perfil efetivo
            applicable_rules = [r for r in rules if r.level == effective_profile]
            
            matched_rule = None
            
            # Logica de match
            for r in applicable_rules:
                # Se não pode enviar, ainda verificamos match para logar RESCHEDULED
                is_match = False
                
                if r.start_days == r.end_days:
                    trigger_adjusted = calcular_data_disparo(nearest_due, r.start_days)
                    if trigger_adjusted.date() == _today:
                        is_match = True
                else:
                    if r.start_days <= max_overdue <= r.end_days:
                        is_match = True
                
                if is_match:
                    if matched_rule is None or (r.priority, r.start_days) > (matched_rule.priority, matched_rule.start_days):
                        matched_rule = r

            if not matched_rule:
                continue

            # Verificar frequência
            last_msg = (
                db.query(SentMessage)
                .filter(
                    SentMessage.customer_id == cid,
                    SentMessage.rule_id == matched_rule.id,
                )
                .order_by(SentMessage.created_at.desc())
                .first()
            )

            if last_msg:
                days_since = (_today - last_msg.created_at.date()).days
                if days_since < matched_rule.frequency:
                    stats["skipped_freq"] += 1
                    continue

            # Montar mensagem
            msg_body = matched_rule.template_message
            cpf_raw = customer.cpf_cnpj or ""
            cpf_masked = f"***.{cpf_raw[3:6]}.{cpf_raw[6:9]}-**" if len(cpf_raw) >= 11 else cpf_raw
            chave_pix = "00.000.000/0001-00"
            link_pagto = f"https://portalmoveis.com.br/pagar/{customer.external_key}"
            
            juros = Decimal("1.10") if max_overdue > 30 else Decimal("1.02")
            valor_com_juros = insts[0].open_amount * juros if insts else Decimal("0")
            
            nome_fmt = customer.name.title()
            venc_fmt = nearest_due.strftime("%d/%m/%Y") if nearest_due else ""

            # --- Gerar lista de parcelas vencidas para {PARCELAS} ---
            insts_sorted = sorted(insts, key=lambda i: i.due_date)
            vencidas = [i for i in insts_sorted if (_today - i.due_date).days > 0]
            futuras = [i for i in insts_sorted if (_today - i.due_date).days <= 0]

            def _fmt_lista(items, limite=10):
                if not items:
                    return "(nenhuma)"
                linhas = []
                for i in items[:limite]:
                    linhas.append(f"  - {format_money(i.open_amount)} — venc. {i.due_date.strftime('%d/%m/%Y')}")
                if len(items) > limite:
                    linhas.append(f"  ... e mais {len(items) - limite} parcela(s)")
                return "\n".join(linhas)

            parcelas_fmt = _fmt_lista(vencidas)
            parcelas_futuras_fmt = _fmt_lista(futuras)
            replacements = {
                "{nome}": nome_fmt, "{NOME}": nome_fmt,
                "{valor}": format_money(insts[0].open_amount) if insts else "0,00",
                "{VALOR}": format_money(insts[0].open_amount) if insts else "0,00",
                "{valor_com_juros}": format_money(valor_com_juros),
                "{total}": format_money(total_open), "{TOTAL}": format_money(total_open),
                "{total_divida}": format_money(total_open),
                "{dias_atraso}": str(max_overdue), "{DIAS}": str(max_overdue),
                "{dias}": str(max_overdue),
                "{vencimento}": venc_fmt, "{VENCIMENTO}": venc_fmt,
                "{data_vencimento}": venc_fmt,
                "{data}": venc_fmt, "{DATA}": venc_fmt,
                "{qtd}": str(len(insts)), "{QTD}": str(len(insts)),
                "{quantidade_parcelas}": str(overdue_count),
                "{parcelas}": parcelas_fmt, "{PARCELAS}": parcelas_fmt,
                "{parcelas_futuras}": parcelas_futuras_fmt, "{PARCELAS_FUTURAS}": parcelas_futuras_fmt,
                "{cpf}": cpf_masked,
                "{cpf_mascarado}": cpf_masked,
                "{telefone}": "(67) 99916-1881",
                "{chave_pix}": chave_pix,
                "{link_pagamento}": link_pagto,
            }
            for k, v in replacements.items():
                msg_body = msg_body.replace(k, v)

            phone = customer.whatsapp or ""
            
            # --- ENVIO / LOG ---
            status_dispatch = "UNKNOWN"
            error_msg = None
            block_reason_compliance = "OK"
            
            if not phone:
                 status_dispatch = "FAILED"
                 error_msg = "Sem telefone cadastrado"
                 stats["skipped_no_phone"] += 1
            elif not is_time_allowed:
                 status_dispatch = "RESCHEDULED"
                 block_reason_compliance = block_reason or "FORA_HORARIO"
                 error_msg = f"Compliance Block: {block_reason_compliance}"
                 stats["rescheduled"] += 1
            else:
                 # Enviar
                 res_envio = enviar_whatsapp(phone, msg_body, modo_teste=config.whatsapp_modo_teste)
                 status_dispatch = res_envio.get("modo", "ERRO")
                 error_msg = res_envio.get("erro")
                 
                 # Registrar SentMessage (Legado)
                 sent = SentMessage(
                    customer_id=cid,
                    user_id=None,
                    channel="WHATSAPP_ZAPI",
                    template_used=matched_rule.template_message,
                    message_body=msg_body,
                    phone=phone,
                    status=status_dispatch,
                    rule_id=matched_rule.id,
                 )
                 db.add(sent)
                
                 hist = WhatsappHistorico(
                    cliente_id=cid,
                    telefone=phone,
                    mensagem=msg_body,
                    tipo="regua_automatica",
                    status=status_dispatch.lower(),
                    resposta=str(res_envio)
                 )
                 db.add(hist)
                 stats["created"] += 1

            # Log Auditoria (MessageDispatchLog)
            log_entry = MessageDispatchLog(
                scheduled_for=_today,
                mode="TEST" if config.whatsapp_modo_teste else "PROD",
                status=status_dispatch,
                regua=matched_rule.level,
                gatilho_dias=matched_rule.start_days,
                customer_id=cid,
                customer_name=customer.name,
                destination_phone=phone,
                cpf_mask=cpf_masked,
                compliance_block_reason=block_reason_compliance,
                message_rendered=msg_body,
                error_message=error_msg,
                metadata_json=json.dumps(replacements, default=str),
                data_vencimento=nearest_due,
                valor_original=insts[0].open_amount if insts else 0,
                total_divida=total_open,
                qtd_parcelas_atrasadas=overdue_count
            )
            db.add(log_entry)

        db.commit()
        log.info(f"Verificação concluída: {stats}")

    except Exception as e:
        db.rollback()
        log.error(f"Erro no scheduler: {e}")
        raise
    finally:
        db.close()

    return stats
