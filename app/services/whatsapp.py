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
            return None, None, None, False, True
        
        # Acesso seguro aos atributos para evitar crash se a migração falhar no VPS
        instance = getattr(config, 'whatsapp_instancia', None)
        token = getattr(config, 'whatsapp_token', None)
        client_token = getattr(config, 'whatsapp_client_token', None)
        active = getattr(config, 'whatsapp_ativo', False)
        test_mode = getattr(config, 'whatsapp_modo_teste', True)
        
        return instance, token, client_token, active, test_mode
    except Exception as e:
        logger.error(f"[WhatsApp] Erro ao ler banco: {e}")
        return None, None, None, False, True
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

def verificar_conexao(instance_id: str = None, token: str = None, client_token: str = None):
    """
    Verifica conexão com Z-API. 
    Se parâmetros forem passados, usa-os diretamente (teste ad-hoc).
    Caso contrário, busca as configurações salvas no banco.
    """
    try:
        # Se algum parâmetro for fornecido, usamos o modo ad-hoc
        if instance_id or token:
            curr_instance = instance_id
            curr_token = token
            curr_client = client_token
        else:
            curr_instance, curr_token, curr_client, _, _ = get_whatsapp_config()
        
        if not curr_instance or not curr_token:
            return {"conectado": False, "erro": "Credenciais não configuradas ou incompletas"}

        base_url = f"https://api.z-api.io/instances/{curr_instance}/token/{curr_token}"
        
        url = f"{base_url}/status"
        headers = {"Client-Token": curr_client or ""}
        
        try:
            response = requests.get(url, headers=headers, timeout=12)
            
            if response.status_code == 401:
                return {"conectado": False, "erro": "Não autorizado (Token ou ID inválidos)", "code": 401}
            
            if response.status_code == 404:
                return {"conectado": False, "erro": f"Instância '{curr_instance}' não encontrada", "code": 404}
            
            response.raise_for_status()
            data = response.json()
            
            # Z-API costuma retornar 'connected' no payload do /status
            is_connected = data.get("connected") is True or data.get("phoneConnected") is True
            
            return {
                "conectado": is_connected,
                "status": data
            }
        except requests.exceptions.Timeout:
            return {"conectado": False, "erro": "Tempo de conexão esgotado (Z-API demorou demais)"}
        except requests.exceptions.RequestException as re:
            return {"conectado": False, "erro": f"Erro de rede: {str(re)}"}
            
    except Exception as e:
        logger.error(f"[WhatsApp] Erro na verificação: {e}")
        return {"conectado": False, "erro": f"Erro interno: {str(e)}"}
