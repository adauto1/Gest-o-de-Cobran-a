from datetime import datetime, time, timedelta, date
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Campo_Grande")
HORA_INICIO = time(9, 0)
HORA_FIM = time(18, 0)

# Feriados Nacionais (Fixos e Móveis aproximados para 2024-2026)
# Idealmente usar library 'holidays' ou tabela no banco.
# Lista simplificada para o MVP.
# Feriados Nacionais (DESATIVADO: Permite envio em feriados)
# A única restrição restante será o Domingo
FERIADOS_NACIONAIS_SET = set()

def is_domingo(d: datetime) -> bool:
    # Monday=0 ... Sunday=6
    return d.weekday() == 6

def is_feriado_nacional(date_obj: date) -> bool:
    # Retorna False sempre, pois a regra agora permite envio em feriados
    return False


def proximo_dia_permitido(d: datetime) -> datetime:
    x = d
    while True:
        # Se for Domingo ou Feriado -> Pula para próximo dia
        if is_domingo(x) or is_feriado_nacional(x.date()):
            # Avança 1 dia e reseta hora para 09:00
            x = datetime.combine(x.date() + timedelta(days=1), HORA_INICIO, x.tzinfo)
            continue
        return x

def normalizar_para_janela_comercial(dt_alvo: datetime) -> datetime:
    # Garantir TZ
    if dt_alvo.tzinfo is None:
        dt = dt_alvo.replace(tzinfo=TZ)
    else:
        dt = dt_alvo.astimezone(TZ)

    # 1) Se caiu em domingo/feriado nacional, joga para próximo dia permitido 09:00
    dt = proximo_dia_permitido(dt)

    # 2) Ajusta janela de horário comercial (Seg–Sáb - assumindo Sábado allowed, pois 'is_domingo' só checka domingo)
    # Usuario disse: "Seg–Sáb: enviar somente entre 09:00 e 18:00"
    
    current_time = dt.time()
    
    if current_time < HORA_INICIO:
        # Se antes das 09:00, ajusta para 09:00 do mesmo dia
        dt = datetime.combine(dt.date(), HORA_INICIO, TZ)
        # E verifica novamente se esse dia é permitido (redundante mas seguro)
        dt = proximo_dia_permitido(dt)
        return dt

    if current_time > HORA_FIM:
        # Se depois das 18:00, ajusta para 09:00 do dia seguinte
        dt = datetime.combine(dt.date() + timedelta(days=1), HORA_INICIO, TZ)
        dt = proximo_dia_permitido(dt)
        return dt

    return dt

def calcular_data_disparo(data_base: datetime, dias_gatilho: int) -> datetime:
    """
    data_base = data do vencimento (geralmente date ou datetime)
    dias_gatilho = offset do disparo
    """
    # Se data_base for date, converte para datetime meio-dia para evitar problemas de fuso
    if isinstance(data_base, date) and not isinstance(data_base, datetime):
        data_base = datetime.combine(data_base, time(12, 0), TZ)
    
    if data_base.tzinfo is None:
        data_base = data_base.replace(tzinfo=TZ)
        
    alvo = data_base + timedelta(days=dias_gatilho)
    # Padronizar para 09:00 antes da normalização pro caso de range check
    alvo = datetime.combine(alvo.date(), HORA_INICIO, TZ)
    
    return normalizar_para_janela_comercial(alvo)

def check_msg_allowed_now(return_reason: bool = False):
    """Helper simples para o scheduler saber se pode rodar AGORA (instant check)."""
    if TZ is None:
        # Fallback se TZ falhar import
        agora = datetime.now()
    else:
        agora = datetime.now(TZ)
    
    reason = None
    allowed = True
    
    # É domingo ou feriado?
    if is_domingo(agora): 
        allowed = False
        reason = "DOMINGO"
    elif is_feriado_nacional(agora.date()): 
        # Feriado liberado conforme nova regra
        pass 
    
    # Está no horário?
    elif not (HORA_INICIO <= agora.time() <= HORA_FIM):
        allowed = False
        reason = "FORA_HORARIO_COMERCIAL"
        
    if return_reason:
        return allowed, reason
    return allowed
