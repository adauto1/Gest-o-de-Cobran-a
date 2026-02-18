from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models import Installment
from app.core.web import render, require_login
from app.services.conferencia_service import process_comparison

router = APIRouter()

@router.get("/conferencia", response_class=HTMLResponse)
def conferencia_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem acessar esta página.")
    return render("conferencia.html", request=request, user=user, title="Conferência de Títulos", active_page="conferencia")

@router.post("/api/conferencia/processar")
async def processar_conferencia(
    request: Request,
    file_receber: Optional[UploadFile] = File(None),
    file_recebidos: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    require_login(request, db)
    
    content_receber = await file_receber.read() if file_receber else None
    content_recebidos = await file_recebidos.read() if file_recebidos else None
    
    results = process_comparison(db, content_receber, content_recebidos)
    return results

@router.post("/api/conferencia/aplicar")
async def aplicar_conferencia(
    request: Request,
    installment_ids: List[int],
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem aplicar atualizações.")
    
    updated_count = 0
    now = datetime.utcnow()
    
    for inst_id in installment_ids:
        inst = db.query(Installment).get(inst_id)
        if inst and inst.status != "QUITADA":
            inst.status = "QUITADA"
            inst.paid_at = now
            inst.updated_at = now
            updated_count += 1
            
    db.commit()
    return {"success": True, "updated": updated_count}
