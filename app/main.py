from __future__ import annotations
import os
import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND
from sqlalchemy.orm import Session

# --- Core & Models ---
from app.core.database import Base, engine, get_db
from app.models import User
from app.core.security import hash_password
from app.core.web import render
from app.services.notifications import director_notification_loop, financial_notification_loop

# --- Routers ---
from app.api.routers import (
    customers, queue, rules, import_data, auth, users, actions, messages, dashboard, commissions, settings
)

# --- Logging Estruturado ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gestor de Cobrança — Portal Móveis")

# Middleware
SECRET_KEY = os.getenv("SESSION_SECRET", "CHANGE-ME-IN-PROD")
if SECRET_KEY == "CHANGE-ME-IN-PROD":
    logger.warning(
        "[SEGURANÇA] SESSION_SECRET usando valor padrão inseguro! "
        "Defina a variável de ambiente SESSION_SECRET em produção."
    )
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Registered Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(queue.router)
app.include_router(rules.router)
app.include_router(import_data.router)
app.include_router(actions.router)
app.include_router(messages.router)
app.include_router(dashboard.router)
app.include_router(commissions.router)
app.include_router(settings.router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login")
    return await request.app.default_exception_handler(request, exc)

@app.get("/")
def root_redirect():
    return RedirectResponse("/dashboard")

@app.on_event("startup")
async def startup_event():
    # Admin Auto-creation (Simple check)
    db = next(get_db())
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@portalmoveis.local")
    admin = db.query(User).filter(User.email == admin_email).first()
    if not admin:
        admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
        db.add(User(
            name="Administrador",
            email=admin_email,
            password_hash=hash_password(admin_pass),
            role="ADMIN",
            active=True
        ))
        db.commit()
        logger.info(f"[SISTEMA] Usuário admin criado: {admin_email}")
    db.close()

    # Iniciar os serviços de background
    asyncio.create_task(director_notification_loop())
    asyncio.create_task(financial_notification_loop())
    logger.info("[SISTEMA] Serviços de notificação em background iniciados.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
