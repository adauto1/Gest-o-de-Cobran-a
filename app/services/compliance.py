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
FERIADOS_NACIONAIS_SET = {
    # 2024
    date(2024, 1, 1),   # Ano Novo
    date(2024, 2, 12),  # Carnaval
    date(2024, 2, 13),  # Carnaval
    date(2024, 3, 29),  # Paixão de Cristo
    date(2024, 4, 21),  # Tiradentes
    date(2024, 5, 1),   # Trabalho
    date(2024, 5, 30),  # Corpus Christi
    date(2024, 9, 7),   # Independência
    date(2024, 10, 12), # Padroeira
    date(2024, 11, 2),  # Finados
    date(2024, 11, 15), # Proclamação República
    date(2024, 11, 20), # Consciência Negra
    date(2024, 12, 25), # Natal

    # 2025
    date(2025, 1, 1),
    date(2025, 3, 3),   # Carnaval
    date(2025, 3, 4),
    date(2025, 4, 18),  # Paixão
    date(2025, 4, 21),
    date(2025, 5, 1),
    date(2025, 6, 19),  # Corpus
    date(2025, 9, 7),
    date(2025, 10, 12),
    date(2025, 11, 2),
    date(2025, 11, 15),
    date(2025, 11, 20),
    date(2025, 12, 25),

    # 2026
    date(2026, 1, 1),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 4, 3),
    date(2026, 4, 21),
    date(2026, 5, 1),
    date(2026, 6, 4),
    date(2026, 9, 7),
    date(2026, 10, 12),
    date(2026, 11, 2),
    date(2026, 11, 15),
    date(2026, 11, 20),
    date(2026, 12, 25),
}

def is_domingo(d: datetime) -> bool:
    # Monday=0 ... Sunday=6
    return d.weekday() == 6

def is_feriado_nacional(date_obj: date) -> bool:
    return date_obj in FERIADOS_NACIONAIS_SET

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

def check_msg_allowed_now() -> bool:
    """Helper simples para o scheduler saber se pode rodar AGORA (instant check)."""
    agora = datetime.now(TZ)
    
    # É domingo ou feriado?
    if is_domingo(agora): return False
    if is_feriado_nacional(agora.date()): return False
    
    # Está no horário?
    if not (HORA_INICIO <= agora.time() <= HORA_FIM):
        return False
        
    return True
