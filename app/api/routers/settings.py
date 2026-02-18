from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from starlette.status import HTTP_302_FOUND

from app.core.database import get_db
from app.models import Configuracoes, Director, FinancialUser
from app.core.web import render, require_login

router = APIRouter()

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    config = db.query(Configuracoes).first()
    if not config:
        # Cria um objeto temporário padrão para evitar erro no template se não houver registro
        config = Configuracoes(
            whatsapp_ativo=False,
            whatsapp_modo_teste=True
        )
    
    return render("settings.html", request=request, user=user, title="Configurações", config=config)

# --- WhatsApp API Status ---
@router.get("/api/whatsapp/status")
@router.post("/api/settings/whatsapp/test")
async def get_whatsapp_status(request: Request, db: Session = Depends(get_db)):
    require_login(request, db)
    from app.services.whatsapp import verificar_conexao
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
async def update_settings_api(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    dados = await request.json()
    config = db.query(Configuracoes).first()
    if not config:
        config = Configuracoes()
        db.add(config)
    
    if "whatsapp_ativo" in dados: config.whatsapp_ativo = bool(dados["whatsapp_ativo"])
    if "whatsapp_modo_teste" in dados: config.whatsapp_modo_teste = bool(dados["whatsapp_modo_teste"])
    if "whatsapp_instancia" in dados: config.whatsapp_instancia = str(dados["whatsapp_instancia"]).strip()
    if "whatsapp_token" in dados: config.whatsapp_token = str(dados["whatsapp_token"]).strip()
    if "whatsapp_client_token" in dados: config.whatsapp_client_token = str(dados["whatsapp_client_token"]).strip()
    
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
