import re
import json
import logging
import unicodedata
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import ReportSnapshot, ReportItem, ConferenciaTitulos

def normalize_name(name: str) -> str:
    """Remove acentos, converte para maiúsculas e normaliza espaços."""
    if not name:
        return ""
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_str = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', ascii_str.upper()).strip()

def parse_valor_cents(texto: str) -> int:
    """Converte valor string pt-BR formatado para um inteiro (centavos)."""
    if not texto:
        return 0
    try:
        v = texto.strip().replace('.', '').replace(',', '.')
        return int(float(v) * 100)
    except Exception:
        return 0

def parse_date_yyyy_mm_dd(texto: str):
    """"Converte DD/MM/YYYY para objeto data (sem hora)."""
    if not texto: return None
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except Exception:
        return None

def detect_report_type(html_text: str) -> str:
    up = html_text.upper()
    if "RECEBIDOS" in up:
        return "RECEBIDOS"
    return "A_RECEBER"

def normalize_pedido(pedido: str) -> str:
    if not pedido: return ""
    return re.sub(r'\D', '', pedido)

def parse_rdprint_html(content: bytes) -> list:
    """Parses RDPrint 5.0 HTML com layout baseado em coordenadas CSS."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        text_content = content.decode('utf-8', errors='ignore')
    except Exception:
        text_content = str(content)

    soup = BeautifulSoup(text_content, 'html.parser')
    elements = []

    for div in soup.find_all(['div', 'span', 'p']):
        style = div.get('style', '')
        if not style:
            continue

        top_match = re.search(r'top\s*:\s*(\d+)', style, re.I)
        left_match = re.search(r'left\s*:\s*(\d+)', style, re.I)

        if top_match and left_match:
            top = int(top_match.group(1))
            left = int(left_match.group(1))

            pre_tag = div.find('pre')
            if pre_tag:
                clean_text = pre_tag.get_text().strip()
            else:
                clean_text = div.get_text(strip=True)

            clean_text = clean_text.replace('&nbsp;', ' ').strip()
            if clean_text:
                elements.append({'top': top, 'left': left, 'text': clean_text})

    if not elements: return []

    elements.sort(key=lambda x: (x['top'], x['left']))
    rows = []
    curr_row = [elements[0]]
    curr_y = elements[0]['top']
    for el in elements[1:]:
        if abs(el['top'] - curr_y) <= 5:
            curr_row.append(el)
        else:
            rows.append(curr_row)
            curr_row = [el]
            curr_y = el['top']
    rows.append(curr_row)

    data = []
    for row in rows:
        # Linha válida: precisa ter data de vencimento na posição ~550 a 600
        has_venc = any(
            re.match(r'\d{2}/\d{2}/\d{4}', el['text'])
            for el in row if 550 <= el['left'] <= 600
        )
        if not has_venc:
            continue

        item = {
            "cliente": "", "doc": "", "pedido": "", "dav": "",
            "venc": "", "valor_raw": "", "status": ""
        }

        for el in row:
            l, txt = el['left'], el['text']
            
            # Posições variam levemente. Adaptar p/ capturar tudo.
            if abs(l - 132) <= 15:
                item["pedido"] = txt.strip()
            elif abs(l - 264) <= 15:
                item["cliente"] = txt.upper()
            elif abs(l - 522) <= 15:
                item["doc"] = txt.strip()
            elif abs(l - 588) <= 15:
                item["venc"] = txt.strip()
            elif abs(l - 648) <= 15:
                item["valor_raw"] = txt.strip()
            elif abs(l - 762) <= 15:
                item["status"] = txt.upper()
                
            # Exemplo de DAV - o layout real do usuário pode ter DAV em outra coluna (ex: 700 ou 400).
            # Vou capturar qualquer string "DAV" solto na row se houver para não perder, mas geralmente não está mapeado no script anterior.
            if "DAV" in txt.upper() or abs(l - 400) <= 15:
                 if not item["doc"] and not item["pedido"] and not item["cliente"] and len(txt) < 15:
                     item["dav"] = txt.strip()

        if item["cliente"] and item["venc"] and item["valor_raw"]:
            data.append(item)

    return data

def build_snapshot_items(db: Session, snapshot_type: str, parsed_items: list, html_bytes: bytes, filename: str):
    """
    Cria um snapshot e converte parsed data em ReportItems.
    """
    hash_arq = hashlib.sha256(html_bytes).hexdigest()
    snapshot = ReportSnapshot(
        report_type=snapshot_type,
        arquivo_nome=filename,
        hash_arquivo=hash_arq,
        total_itens=len(parsed_items)
    )
    db.add(snapshot)
    db.flush()
    
    valid_count = 0
    for item in parsed_items:
        v_cents = parse_valor_cents(item.get("valor_raw"))
        v_date = parse_date_yyyy_mm_dd(item.get("venc"))
        
        # Ignora lixo sem valor ou sem data
        if v_cents == 0 or not v_date: continue
        
        venc_str = v_date.strftime('%Y-%m-%d')
        p_norm = normalize_pedido(item.get("pedido"))
        ndco_norm = item.get("doc", "").strip()
        dav_norm = item.get("dav", "").strip()
        
        # Hash do item imutável (Chave principal de Match)
        chave_str = f"{p_norm}|{venc_str}|{v_cents}|{dav_norm}|{ndco_norm}"
        hash_it = hashlib.sha256(chave_str.encode('utf-8')).hexdigest()
        
        db.add(ReportItem(
            snapshot_id=snapshot.id,
            pedido_norm=p_norm,
            venc_norm=v_date,
            valor_centavos=v_cents,
            n_doc=ndco_norm,
            dav=dav_norm,
            cliente_nome=item.get("cliente", ""),
            status_erp=item.get("status", ""),
            hash_item=hash_it
        ))
        valid_count += 1
        
    snapshot.total_itens = valid_count
    db.flush()
    return snapshot

def make_match_key(item) -> str:
    """Cria a chave exata para matching rigoroso."""
    if hasattr(item, "hash_item") and item.hash_item:
        return item.hash_item  # Aproveita o hash se já calculado no DB
    venc = item.venc_norm.strftime('%Y-%m-%d') if item.venc_norm else ""
    chave_str = f"{item.pedido_norm}|{venc}|{item.valor_centavos}|{item.dav}|{item.n_doc}"
    return hashlib.sha256(chave_str.encode('utf-8')).hexdigest()

def process_smart_reconciliation(db: Session, html_recebido: bytes = None, filename: str = "upload.html"):
    import logging
    logger = logging.getLogger(__name__)

    if not html_recebido:
        return {"error": "Nenhum arquivo enviado."}
        
    html_text = html_recebido.decode('utf-8', errors='ignore')
    report_type = detect_report_type(html_text)
    
    parsed_items = parse_rdprint_html(html_recebido)
    if not parsed_items:
        return {"error": "Nenhum título encontrado (ou layout incompatível)."}
        
    logger.info(f"Relatório {report_type} enviado com {len(parsed_items)} itens.")
    
    current_snapshot = build_snapshot_items(db, report_type, parsed_items, html_recebido, filename)
    db.commit()

    if report_type == "RECEBIDOS":
        return {
            "resumo": {},
            "detalhes": [],
            "msg": f"Sucesso! Relatório RECEBIDOS (Snapshot #{current_snapshot.id} | {current_snapshot.total_itens} itens) salvo como prova anti-fraude."
        }

    a_receber_snaps = db.query(ReportSnapshot).filter(
        ReportSnapshot.report_type == "A_RECEBER"
    ).order_by(desc(ReportSnapshot.id)).limit(2).all()
    
    recebidos_snap = db.query(ReportSnapshot).filter(
        ReportSnapshot.report_type == "RECEBIDOS"
    ).order_by(desc(ReportSnapshot.id)).first()
    
    if len(a_receber_snaps) < 2:
        return {
            "resumo": {}, 
            "detalhes": [], 
            "msg": f"Upload salvo (Snapshot #{current_snapshot.id}). Faça upload de mais um A_RECEBER para ativar o cruzamento (temos {len(a_receber_snaps)} de 2)."
        }
        
    snap_a_rec_curr = a_receber_snaps[0]
    snap_a_rec_prev = a_receber_snaps[1]
    
    curr_items = db.query(ReportItem).filter(ReportItem.snapshot_id == snap_a_rec_curr.id).all()
    prev_items = db.query(ReportItem).filter(ReportItem.snapshot_id == snap_a_rec_prev.id).all()
    rec_items = db.query(ReportItem).filter(ReportItem.snapshot_id == recebidos_snap.id).all() if recebidos_snap else []
    
    curr_by_hash = {make_match_key(i): i for i in curr_items}
    curr_by_pedido = {}
    for i in curr_items:
        if i.pedido_norm:
            curr_by_pedido.setdefault(i.pedido_norm, []).append(i)
            
    rec_by_hash = {make_match_key(i): i for i in rec_items}
    rec_by_pedido = {}
    for i in rec_items:
        if i.pedido_norm:
            rec_by_pedido.setdefault(i.pedido_norm, []).append(i)

    str_snap_ant = f"#{snap_a_rec_prev.id} - {snap_a_rec_prev.created_at.strftime('%d/%m %H:%M')} ({len(prev_items)} itens)"
    str_snap_atu = f"#{snap_a_rec_curr.id} - {snap_a_rec_curr.created_at.strftime('%d/%m %H:%M')} ({len(curr_items)} itens)"
    str_snap_rec = f"#{recebidos_snap.id} - {recebidos_snap.created_at.strftime('%d/%m %H:%M')} ({len(rec_items)} itens)" if recebidos_snap else "Sem base"

    resumo = {
        "normal_qtd": 0, "normal_valor": 0.0,
        "divergencia_qtd": 0, "divergencia_valor": 0.0,
        "suspeita_qtd": 0, "suspeita_valor": 0.0,
        "total_analisado": len(curr_items),
        "diagnostico": [],
        "snap_a_rec_prev_str": str_snap_ant,
        "snap_a_rec_curr_str": str_snap_atu,
        "snap_rec_str": str_snap_rec
    }
    
    detalhes = []

    for prev in prev_items:
        h = make_match_key(prev)
        
        # 1. Se existe a mesma chave exata no Atual de A Receber, ignorar (ainda não foi pago)
        if h in curr_by_hash:
            continue
            
        situacao = ""
        evidencia = ""
        grupo = ""
        classe = ""
        motivo_diagnostico = ""
        
        # O item sumiu de ontem para hoje.
        # Passo Único: É Baixa/Suspeita ou Divergência/Manipulação?
        # A prioridade é: Esse item específico (hash exato) foi RECEBIDO?
        rec_match = rec_by_hash.get(h)
        if rec_match:
            if rec_match.status_erp in ("QUITADA", "PARCIAL", "QUITADO"):
                grupo = "BAIXA JUSTIFICADA"
                situacao = "Pago"
                classe = "situacao-success"
                evidencia = f"Prova (Snap #{recebidos_snap.id}): {rec_match.status_erp}"
                resumo["normal_qtd"] += 1
                resumo["normal_valor"] += (prev.valor_centavos / 100.0)
                motivo_diagnostico = f"BAIXA: Hash {h[:8]} validado nos RECEBIDOS. Status: {rec_match.status_erp}"
            else:
                grupo = "SUSPEITA"
                situacao = "Recebidos s/ Quitação"
                evidencia = rec_match.status_erp
                classe = "situacao-danger"
                resumo["suspeita_qtd"] += 1
                resumo["suspeita_valor"] += (prev.valor_centavos / 100.0)
                motivo_diagnostico = f"SUSPEITA: Hash {h[:8]} está nos RECEBIDOS mas não foi quitado."
        else:
            # Não está em RECEBIDOS. Item sumiu misteriosamente!
            # Precisamos ver se o Pedido ou Identificador base continuou na carteira (manipulação)
            if prev.pedido_norm and prev.pedido_norm in curr_by_pedido:
                # O Pedido continua hoje! Mas o hash mudou (sumiu)
                # Verifica se a exata parcela sofreu alteração (mesmo DAV ou N_DOC)
                curr_matches = curr_by_pedido[prev.pedido_norm]
                is_divergencia = False
                for c in curr_matches:
                    if (prev.n_doc and c.n_doc == prev.n_doc) or (prev.dav and c.dav == prev.dav):
                        is_divergencia = True
                        evidencia = f"Aberto Hoje: {c.venc_norm.strftime('%d/%m')} R${c.valor_centavos/100:.2f}"
                        break
                
                if is_divergencia:
                    grupo = "DIVERGENCIA"
                    situacao = "Alterou Venc/Valor"
                    classe = "situacao-warning"
                    resumo["divergencia_qtd"] += 1
                    resumo["divergencia_valor"] += (prev.valor_centavos / 100.0)
                    motivo_diagnostico = "DIVERGÊNCIA: Mesma Parcela (DAV/Doc) encontrada em A_HOJE, mas Vencimento/Valor foram manipulados."
                else:
                    grupo = "PARCELA REMOVIDA"
                    situacao = "Removida (Mesmo Pedido)"
                    classe = "situacao-warning"
                    evidencia = "Itens do pedido ainda em aberto"
                    # Pode usar resumir divergencia ou suspeita, vamos manter nas chaves fixas: Suspeita 
                    resumo["suspeita_qtd"] += 1
                    resumo["suspeita_valor"] += (prev.valor_centavos / 100.0)
                    motivo_diagnostico = "PARCELA REMOVIDA DO MESMO PEDIDO: O pedido existe hoje, mas esta parcela sumiu."
            else:
                grupo = "SUSPEITA"
                situacao = "Sumiu s/ Evidência"
                classe = "situacao-danger"
                resumo["suspeita_qtd"] += 1
                resumo["suspeita_valor"] += (prev.valor_centavos / 100.0)
                motivo_diagnostico = f"SUSPEITA C/ RISCO DE EXCLUSÃO: Hash {h[:8]} evaporou. Não achamos o pedido e não está como Quitado."

        # Diagnostic limited to 10 lines as requested
        if len(resumo["diagnostico"]) < 10:
            resumo["diagnostico"].append({
                "chave_crua": f"{prev.pedido_norm} | {prev.venc_norm} | {prev.valor_centavos} | {prev.dav} | {prev.n_doc}",
                "hash": h,
                "motivo": motivo_diagnostico,
                "cliente": prev.cliente_nome
            })

        detalhes.append({
            "cliente": prev.cliente_nome,
            "pedido": prev.pedido_norm,
            "venc": prev.venc_norm.strftime('%d/%m/%Y') if prev.venc_norm else "",
            "valor": prev.valor_centavos / 100.0,
            "situacao": situacao,
            "evidencia": evidencia,
            "snapshot_ant": str_snap_ant,
            "snapshot_atu": str_snap_atu,
            "grupo": grupo,
            "classe": classe
        })

    conferencia = ConferenciaTitulos(
        resumo_json=json.dumps(resumo),
        detalhes_json=json.dumps(detalhes),
    )
    db.add(conferencia)
    db.commit()

    logger.info(f"[Conferencia] Completa! OK={resumo['normal_qtd']} DIV={resumo['divergencia_qtd']} SUS={resumo['suspeita_qtd']}")
    return {"resumo": resumo, "detalhes": detalhes, "msg": f"Análise do {report_type} calculada com base nos Snapshots."}
