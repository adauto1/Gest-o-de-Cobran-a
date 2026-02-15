import requests
from datetime import datetime

ZAPI_INSTANCE_ID = "3EECA6A04BF7413E6BA8B269A10D1A36"
ZAPI_TOKEN = "A85C1AF99D030B9243723276"
ZAPI_CLIENT_TOKEN = "F2d93bb4f23434f82bb1b4d718cd3b74fS"
ZAPI_BASE_URL = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}"

def enviar_whatsapp(telefone: str, mensagem: str, modo_teste: bool = True):
    """
    Envia mensagem via WhatsApp Z-API
    - telefone: formato "67999999999" (DDD + número)
    - mensagem: texto a enviar
    - modo_teste: se True, apenas simula (não envia de verdade)
    """
    if not telefone:
        return {
            "success": False,
            "modo": "ERRO",
            "telefone": None,
            "erro": "Telefone vazio",
            "data": datetime.now().isoformat()
        }
    
    # Formata telefone (adiciona 55 se não tiver e remove caracteres)
    telefone_formatado = telefone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    
    if not telefone_formatado.startswith("55"):
        telefone_formatado = f"55{telefone_formatado}"
    
    # Se modo teste, apenas simula
    if modo_teste:
        return {
            "success": True,
            "modo": "SIMULADO",
            "telefone": telefone_formatado,
            "mensagem": mensagem,
            "data": datetime.now().isoformat()
        }
    
    # Envio real
    try:
        url = f"{ZAPI_BASE_URL}/send-text"
        payload = {
            "phone": telefone_formatado,
            "message": mensagem
        }
        headers = {
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
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
        return {
            "success": False,
            "modo": "ERRO",
            "telefone": telefone_formatado,
            "erro": str(e),
            "data": datetime.now().isoformat()
        }
