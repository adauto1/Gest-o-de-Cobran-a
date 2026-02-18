import requests
import logging
from datetime import datetime
from app.core.database import SessionLocal
from app.models import Configuracoes

logger = logging.getLogger(__name__)

def get_whatsapp_config():
    """Busca configuração ativa do WhatsApp no banco."""
    db = SessionLocal()
    try:
        config = db.query(Configuracoes).first()
        if not config:
            return None, None, None, False, True # instance, token, client_token, active, test_mode
        return (
            config.whatsapp_instancia,
            config.whatsapp_token,
            "F2d93bb4f23434f82bb1b4d718cd3b74fS", # Client Token fixo ou poderia vir do banco
            config.whatsapp_ativo,
            config.whatsapp_modo_teste
        )
    finally:
        db.close()

def enviar_whatsapp(telefone: str, mensagem: str, modo_teste: bool = True):
    """
    Envia mensagem via WhatsApp Z-API usando configurações do banco.
    """
    if not telefone:
        return {"success": False, "erro": "Telefone vazio"}
    
    # Formata telefone
    telefone_formatado = telefone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    if not telefone_formatado.startswith("55"):
        telefone_formatado = f"55{telefone_formatado}"
    
    # Busca config
    instance, token, client_token, active, db_test_mode = get_whatsapp_config()
    
    # Se for modo teste forçado pelo parametro OU pela config global
    is_simulation = modo_teste or db_test_mode
    
    if is_simulation:
        return {
            "success": True,
            "modo": "SIMULADO",
            "telefone": telefone_formatado,
            "mensagem": mensagem,
            "data": datetime.now().isoformat()
        }

    if not active:
        return {"success": False, "erro": "WhatsApp inativo nas configurações"}

    if not instance or not token:
        return {"success": False, "erro": "Credenciais Z-API não configuradas"}

    base_url = f"https://api.z-api.io/instances/{instance}/token/{token}"

    try:
        url = f"{base_url}/send-text"
        payload = {"phone": telefone_formatado, "message": mensagem}
        headers = {"Client-Token": client_token}
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        return {
            "success": True,
            "modo": "ENVIADO",
            "telefone": telefone_formatado,
            "response": response.json(),
            "data": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"[WhatsApp] Erro ao enviar: {e}")
        return {
            "success": False,
            "modo": "ERRO",
            "erro": str(e)
        }

def verificar_conexao():
    """Verifica conexão com Z-API usando configs do banco."""
    instance, token, client_token, _, _ = get_whatsapp_config()
    
    if not instance or not token:
        return {"conectado": False, "erro": "Credenciais não configuradas"}

    base_url = f"https://api.z-api.io/instances/{instance}/token/{token}"
    
    try:
        url = f"{base_url}/status"
        headers = {"Client-Token": client_token}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        return {
            "conectado": (response.status_code == 200 and data.get("connected") is True),
            "status": data
        }
    except Exception as e:
        return {"conectado": False, "erro": str(e)}
