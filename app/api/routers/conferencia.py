from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models import Installment, ConferenciaTitulos
from app.core.web import render, require_login
from app.services.conferencia_inteligente_service import process_smart_reconciliation
import json

router = APIRouter()

@router.get("/conferencia", response_class=HTMLResponse)
def conferencia_page(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem acessar esta página.")
    
    # Buscar o processamento mais recente
    last_process = db.query(ConferenciaTitulos).order_by(ConferenciaTitulos.data_processamento.desc()).first()
    detalhes = []
    resumo = None
    if last_process:
        detalhes = json.loads(last_process.detalhes_json)
        resumo = json.loads(last_process.resumo_json)
        # Garantir que as novas chaves existam para não quebrar o template
        for key in ["confirmados_qtd", "suspeitos_qtd", "extras_qtd", "confirmados_valor", "suspeitos_valor", "extras_valor"]:
            resumo.setdefault(key, 0)
        resumo["data"] = last_process.data_processamento.strftime("%d/%m/%Y %H:%M")

    return render("conferencia.html", request=request, user=user, title="Conferência Inteligente", 
                  active_page="conferencia", detalhes=detalhes, resumo=resumo)

@router.post("/api/conferencia/processar")
async def processar_conferencia(
    request: Request,
    file_recebido: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    require_login(request, db)
    content_recebido = await file_recebido.read() if file_recebido else None
    results = process_smart_reconciliation(db, content_recebido)
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

@router.post("/api/conferencia/zerar")
async def zerar_conferencia(
    request: Request,
    db: Session = Depends(get_db)
):
    user = require_login(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem zerar o relatório.")
    
    db.query(ConferenciaTitulos).delete()
    db.commit()
    return {"success": True}
