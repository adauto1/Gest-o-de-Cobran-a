from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_302_FOUND

from app.core.database import get_db
from app.models import User
from app.core.web import render
from app.core.security import verify_password

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render("login.html", request=request, title="Login")

@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.active or not verify_password(password, user.password_hash):
        return render("login.html", request=request, title="Login", error="Credenciais inválidas ou usuário inativo.")
    
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=HTTP_302_FOUND)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)
