import logging
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Literal
from starlette.status import HTTP_302_FOUND
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import Configuracoes, Director, FinancialUser
from app.core.web import render, require_login


class SettingsUpdate(BaseModel):
    whatsapp_ativo: Optional[bool] = None
    whatsapp_modo_teste: Optional[bool] = None
    whatsapp_instancia: Optional[str] = Field(None, max_length=100)
    whatsapp_token: Optional[str] = Field(None, max_length=100)
    whatsapp_client_token: Optional[str] = Field(None, max_length=100)
    scheduler_hora_disparo: Optional[int] = Field(None, ge=0, le=23)
    director_alert_min_installments: Optional[int] = Field(None, ge=1, le=100)
    pix_chave: Optional[str] = Field(None, max_length=100)
    pix_tipo: Optional[Literal["CNPJ", "CPF", "EMAIL", "TELEFONE", "ALEATORIA"]] = None
    meta_contatos_diarios: Optional[int] = Field(None, ge=0, le=1000)
    meta_promessas_diarios: Optional[int] = Field(None, ge=0, le=1000)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    try:
        config = db.query(Configuracoes).first()
    except Exception as e:
        logger.error(f"Falha ao ler configuracoes do banco: {e}")
        config = None

    if not config:
        class MockConfig:
            def __init__(self):
                self.whatsapp_ativo = False
                self.whatsapp_modo_teste = True
                self.whatsapp_instancia = ""
                self.whatsapp_token = ""
                self.whatsapp_client_token = ""
                self.scheduler_hora_disparo = 9
                self.director_alert_min_installments = 3
        config = MockConfig()
    else:
        for attr, default in [
            ('whatsapp_instancia', ""),
            ('whatsapp_token', ""),
            ('whatsapp_client_token', ""),
            ('whatsapp_modo_teste', True),
            ('scheduler_hora_disparo', 9),
            ('director_alert_min_installments', 3),
        ]:
            if not hasattr(config, attr):
                setattr(config, attr, default)
    
    return render("settings.html", request=request, user=user, title="Configurações", config=config)

# --- WhatsApp API Status ---
@router.api_route("/api/whatsapp/status", methods=["GET", "POST"])
async def get_whatsapp_status(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    from app.services.whatsapp import verificar_conexao
    
    if request.method == "POST":
        try:
            dados = await request.json()
            instance = dados.get("instance")
            token = dados.get("token")
            client = dados.get("client_token")
            # Chama verificação com dados fornecidos (ad-hoc)
            return verificar_conexao(instance, token, client)
        except Exception as e:
            return {"conectado": False, "erro": f"Erro ao processar dados de teste: {e}"}
            
    # GET: Usa o comportamento padrão (busca do banco)
    return verificar_conexao()

# --- Config Settings (Form and AJAX) ---
@router.post("/settings")
async def update_settings_form(
    request: Request, 
    whatsapp_ativo: bool = Form(False),
    whatsapp_modo_teste: bool = Form(False),
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes()
        db.add(config)
    
    config.whatsapp_ativo = whatsapp_ativo
    config.whatsapp_modo_teste = whatsapp_modo_teste
    db.commit()
    return RedirectResponse("/settings?msg=Configurações salvas!", status_code=HTTP_302_FOUND)

@router.post("/api/settings")
async def update_settings_api(request: Request, dados: SettingsUpdate, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Sem permissão")

    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes()
        db.add(config)

    if dados.whatsapp_ativo is not None: config.whatsapp_ativo = dados.whatsapp_ativo
    if dados.whatsapp_modo_teste is not None: config.whatsapp_modo_teste = dados.whatsapp_modo_teste
    if dados.whatsapp_instancia is not None: config.whatsapp_instancia = dados.whatsapp_instancia.strip()
    if dados.whatsapp_token is not None: config.whatsapp_token = dados.whatsapp_token.strip()
    if dados.whatsapp_client_token is not None: config.whatsapp_client_token = dados.whatsapp_client_token.strip()
    if dados.director_alert_min_installments is not None: config.director_alert_min_installments = dados.director_alert_min_installments
    if dados.pix_chave is not None: config.pix_chave = dados.pix_chave.strip() or None
    if dados.pix_tipo is not None: config.pix_tipo = dados.pix_tipo
    if dados.meta_contatos_diarios is not None: config.meta_contatos_diarios = dados.meta_contatos_diarios
    if dados.meta_promessas_diarios is not None: config.meta_promessas_diarios = dados.meta_promessas_diarios

    if dados.scheduler_hora_disparo is not None:
        config.scheduler_hora_disparo = dados.scheduler_hora_disparo
        try:
            from app.main import scheduler
            from apscheduler.triggers.cron import CronTrigger
            scheduler.reschedule_job(
                "collection_check",
                trigger=CronTrigger(hour=dados.scheduler_hora_disparo, minute=0)
            )
        except Exception as e:
            logger.warning(f"[Settings] Reagendamento falhou: {e}")

    db.commit()
    return {"success": True}

# --- Director Management ---
@router.get("/api/directors")
def list_directors(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    return db.query(Director).all()

@router.post("/api/directors")
def add_director(request: Request, name: str = Form(...), phone: str = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN": raise HTTPException(status_code=403)
    db.add(Director(name=name.strip(), phone=phone.strip()))
    db.commit()
    return {"success": True}

@router.delete("/api/directors/{id}")
def remove_director(request: Request, id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN": raise HTTPException(status_code=403)
    d = db.get(Director, id)
    if d:
        db.delete(d)
        db.commit()
    return {"success": True}

# --- Financial Users Management ---
@router.get("/api/financial_users")
def list_financial(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    return db.query(FinancialUser).all()

@router.post("/api/financial_users")
def add_financial(request: Request, name: str = Form(...), phone: str = Form(...), db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN": raise HTTPException(status_code=403)
    db.add(FinancialUser(name=name.strip(), phone=phone.strip()))
    db.commit()
    return {"success": True}

@router.delete("/api/financial_users/{id}")
def remove_financial(request: Request, id: int, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN": raise HTTPException(status_code=403)
    fu = db.get(FinancialUser, id)
    if fu:
        db.delete(fu)
        db.commit()
    return {"success": True}
