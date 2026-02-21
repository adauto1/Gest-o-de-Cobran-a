"""
Configurações centralizadas da aplicação.
Valores lidos de variáveis de ambiente com defaults seguros.
Para sobrescrever, defina as variáveis no ambiente ou em um arquivo .env.
"""
import os
from decimal import Decimal
from datetime import time

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# --- Fuso horário ---
TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Campo_Grande"))

# --- Janela comercial de envio de mensagens ---
BUSINESS_HOUR_START = time(int(os.getenv("BUSINESS_HOUR_START", "9")), 0)
BUSINESS_HOUR_END = time(int(os.getenv("BUSINESS_HOUR_END", "18")), 0)

# --- Metas de recuperação ---
# Percentual mínimo de recuperação para atingir a meta (padrão: 70%)
RECOVERY_TARGET_PCT = Decimal(os.getenv("RECOVERY_TARGET_PCT", "0.70"))

# --- Buckets de prioridade de cobrança (dias de atraso) ---
PRIORITY_CRITICAL_DAYS = int(os.getenv("PRIORITY_CRITICAL_DAYS", "60"))
PRIORITY_ALERT_DAYS = int(os.getenv("PRIORITY_ALERT_DAYS", "30"))
PRIORITY_MODERATE_DAYS = int(os.getenv("PRIORITY_MODERATE_DAYS", "1"))
