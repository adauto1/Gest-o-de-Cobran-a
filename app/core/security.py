import time
import threading
from collections import defaultdict
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --- Rate limiter em memória (proteção contra brute force) ---
_failed_attempts: dict = defaultdict(list)
_lock = threading.Lock()

MAX_ATTEMPTS = 5       # tentativas antes de bloquear
WINDOW_SECONDS = 900   # janela de 15 minutos

def check_rate_limit(ip: str) -> tuple:
    """Verifica se o IP pode tentar login. Retorna (permitido, segundos_bloqueado)."""
    now = time.time()
    with _lock:
        attempts = _failed_attempts[ip]
        attempts[:] = [t for t in attempts if now - t < WINDOW_SECONDS]
        if len(attempts) >= MAX_ATTEMPTS:
            wait = int(WINDOW_SECONDS - (now - attempts[0]))
            return False, max(wait, 1)
        return True, 0

def record_failed_attempt(ip: str) -> None:
    with _lock:
        _failed_attempts[ip].append(time.time())

def clear_attempts(ip: str) -> None:
    with _lock:
        _failed_attempts.pop(ip, None)
