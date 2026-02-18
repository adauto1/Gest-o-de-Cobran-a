from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.models import User
from app.core.web import render, require_login
from app.api.routers.rules import router as rules_router # Temporary until rehash

router = APIRouter()

@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    users = db.query(User).order_by(User.name.asc()).all()
    return render("users.html", request=request, user=user, title="Usuários", users=users, msg=request.query_params.get("msg"))

@router.post("/users")
def users_create(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    store: str = Form(None),
    db: Session = Depends(get_db)
):
    admin = require_login(request, db)
    if admin.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    
    from app.core.security import hash_password
    db.add(User(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role.strip().upper(),
        store=store.strip() if store else None,
        active=True
    ))
    db.commit()
    return RedirectResponse("/users?msg=Usuário criado com sucesso!", status_code=302)

@router.post("/users/{user_id}/toggle")
def users_toggle(request: Request, user_id: int, db: Session = Depends(get_db)):
    admin = require_login(request, db)
    if admin.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas ADMIN")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if u.id == admin.id:
        raise HTTPException(status_code=400, detail="Não pode desativar a si mesmo")
    u.active = not u.active
    db.commit()
    return RedirectResponse("/users?msg=Status atualizado.", status_code=302)
