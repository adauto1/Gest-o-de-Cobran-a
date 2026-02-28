from __future__ import annotations
import logging
import re
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CollectionAction, Customer, User, today

router = APIRouter()
logger = logging.getLogger(__name__)

# Mapeamento de keywords → outcomes sugeridos
_KEYWORDS: list[tuple[str, str]] = [
    (r"pagu|paguei|pagamento|pix|transferi|comprovante|quitei|quitado", "PAGOU"),
    (r"segunda|amanhã|semana|dia\s*\d|prazo|posso|vou pagar|pago\s*na", "PROMESSA"),
    (r"não tenho|sem dinheiro|desempregad|falid|difícil|aperto|aguardar", "RECUSA"),
    (r"não sou|número errado|engano|quem|outro número", "NUMERO_ERRADO"),
    (r"ok|certo|sim|pode|confirmad|entendido", "NEGOCIACAO"),
]


def _detectar_outcome(texto: str) -> str:
    t = texto.lower()
    for pattern, outcome in _KEYWORDS:
        if re.search(pattern, t):
            return outcome
    return "NAO_ATENDEU"


def _normalizar_fone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


@router.post("/api/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber mensagens de resposta dos clientes via Z-API.
    Endpoint a ser configurado no painel da Z-API quando disponível.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}  # Retorna 200 mesmo com payload inválido

    # Z-API envia: {"phone": "5565999...", "text": {"message": "..."}, "isGroup": false}
    if payload.get("isGroup"):
        return {"ok": True}  # Ignora grupos

    phone_raw = payload.get("phone", "") or payload.get("from", "")
    phone = _normalizar_fone(str(phone_raw))
    if not phone:
        return {"ok": True}

    # Extrai texto da mensagem
    text_obj = payload.get("text") or {}
    if isinstance(text_obj, dict):
        texto = text_obj.get("message", "") or ""
    else:
        texto = str(text_obj)
    texto = texto.strip()

    if not texto:
        return {"ok": True}

    # Busca cliente pelo telefone (sem código de país ou com)
    fone_sem_pais = phone[-11:] if len(phone) > 11 else phone
    cliente = db.query(Customer).filter(
        Customer.whatsapp.like(f"%{fone_sem_pais[-8:]}")
    ).first()

    outcome = _detectar_outcome(texto)
    notas = f"[Resposta WhatsApp] {texto[:500]}"

    # Usa user_id=1 (admin) como registrador automático
    admin = db.query(User).filter(User.role == "ADMIN").first()
    user_id = admin.id if admin else 1

    if cliente:
        action = CollectionAction(
            customer_id=cliente.id,
            user_id=user_id,
            action_type="WHATSAPP_ENTRADA",
            outcome=outcome,
            notes=notas,
        )
        db.add(action)
        db.commit()
        logger.info(f"[Webhook WA] Cliente {cliente.name} respondeu: '{texto[:80]}' → {outcome}")
    else:
        logger.info(f"[Webhook WA] Telefone {phone} não encontrado. Texto: '{texto[:80]}'")

    return {"ok": True}
