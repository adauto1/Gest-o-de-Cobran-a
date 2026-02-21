import re
import json
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.models import Installment, Customer, ConferenciaTitulos


def parse_valor_br(texto):
    try:
        v = texto.strip().replace('.', '').replace(',', '.')
        return float(v)
    except:
        return 0.0


def parse_rdprint_html(content: bytes):
    """Parses RDPrint 5.0 HTML using flexible Regex for coordinate-based layout."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        text_content = content.decode('utf-8', errors='ignore')
    except:
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

    if not elements:
        return []

    # Agrupar por linhas (tolerância de 5px na vertical)
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
        # Linha válida: precisa ter data de vencimento na posição ~588
        has_venc = any(
            re.match(r'\d{2}/\d{2}/\d{4}', el['text'])
            for el in row if 578 <= el['left'] <= 598
        )
        if not has_venc:
            continue

        item = {
            "cliente": "", "doc": "", "pedido": "",
            "venc": "", "valor": 0.0, "status": "QUITADA"
        }

        for el in row:
            l, txt = el['left'], el['text']
            if abs(l - 132) <= 10:
                item["pedido"] = txt.strip()
            elif abs(l - 264) <= 10:
                item["cliente"] = txt.upper()
            elif abs(l - 522) <= 10:
                item["doc"] = txt.strip()
            elif abs(l - 588) <= 10:
                item["venc"] = txt.strip()
            elif abs(l - 648) <= 10:
                item["valor"] = parse_valor_br(txt)
            elif abs(l - 762) <= 10:
                item["status"] = txt.upper()

        if item["cliente"] and item["venc"] and item["valor"] > 0:
            data.append(item)

    logger.info(f"[Conferencia] Parsed {len(data)} items from ERP report")
    return data


def _nome_clean(nome: str) -> str:
    return " ".join(nome.strip().upper().split())


def process_smart_reconciliation(db: Session, html_recebido: bytes = None):
    """
    Confere as parcelas QUITADAS do ERP contra o banco do app.

    Lógica (ERP é a base de verdade para o período):
    - CONFIRMADO: ERP quitada + App PAGA → tudo certo
    - SUSPEITO:   ERP quitada + App ABERTA → precisa baixar no app
    - NÃO ENCONTRADA: ERP quitada + não existe no App → cancelada/excluída no ERP
    """
    # 1. Parsear relatório ERP (LIQUIDADOS do período)
    erp_items = parse_rdprint_html(html_recebido) if html_recebido else []

    # 2. Carregar TODAS as parcelas do app (sem filtro de data)
    all_insts = db.query(Installment).join(Customer).all()

    # Índices para lookup rápido
    # Chave primária: nome_limpo + vencimento + valor
    app_by_nome_venc_valor = {}
    # Chave secundária: contract_id + vencimento (fallback)
    app_by_doc_venc = {}

    for inst in all_insts:
        venc_str = inst.due_date.strftime("%d/%m/%Y")
        v_float = float(inst.amount)
        key_nome = f"{_nome_clean(inst.customer.name)}_{venc_str}_{v_float:.2f}"
        key_doc = f"{inst.contract_id}_{venc_str}"
        app_by_nome_venc_valor[key_nome] = inst
        app_by_doc_venc[key_doc] = inst

    detailed_results = []
    resumo = {
        "confirmados_qtd": 0, "confirmados_valor": 0.0,
        "suspeitos_qtd": 0, "suspeitos_valor": 0.0,
        "extras_qtd": 0, "extras_valor": 0.0,
    }

    # 3. Para cada item do ERP, buscar correspondente no app
    for erp in erp_items:
        nome_c = _nome_clean(erp['cliente'])
        venc = erp['venc']
        valor = erp['valor']

        key_nome = f"{nome_c}_{venc}_{valor:.2f}"
        key_doc = f"{erp['doc']}_{venc}"

        inst = app_by_nome_venc_valor.get(key_nome) or app_by_doc_venc.get(key_doc)

        # ID para exibição: pedido do ERP se existir, senão doc, senão contract_id do app
        display_id = (
            erp["pedido"] if erp.get("pedido")
            else erp["doc"] if erp.get("doc")
            else (inst.contract_id if inst else "N/A")
        )
        cliente_nome = inst.customer.name if inst else erp['cliente']

        if inst:
            if inst.status == "PAGA":
                # ✅ ERP quitada e App registrou como paga
                detailed_results.append({
                    "cliente": cliente_nome, "doc": display_id,
                    "venc": venc, "valor": valor,
                    "status_erp": erp["status"],
                    "situacao": "CONFIRMADO",
                    "classe": "situacao-success",
                    "grupo": "CONFIRMADOS",
                })
                resumo["confirmados_qtd"] += 1
                resumo["confirmados_valor"] += valor

            else:
                # ⚠️ ERP quitada mas App ainda não baixou
                detailed_results.append({
                    "cliente": cliente_nome, "doc": display_id,
                    "venc": venc, "valor": valor,
                    "status_erp": erp["status"],
                    "situacao": f"ABERTA NO APP ({inst.status})",
                    "classe": "situacao-danger",
                    "grupo": "SUSPEITOS",
                })
                resumo["suspeitos_qtd"] += 1
                resumo["suspeitos_valor"] += valor

        else:
            # ℹ️ ERP quitada mas não encontrada no App (cancelada/excluída no ERP)
            detailed_results.append({
                "cliente": erp['cliente'], "doc": display_id,
                "venc": venc, "valor": valor,
                "status_erp": erp["status"],
                "situacao": "NÃO ENCONTRADA NO APP",
                "classe": "situacao-warning",
                "grupo": "EXTRAS",
            })
            resumo["extras_qtd"] += 1
            resumo["extras_valor"] += valor

    # 4. Salvar histórico
    conferencia = ConferenciaTitulos(
        resumo_json=json.dumps(resumo),
        detalhes_json=json.dumps(detailed_results),
    )
    db.add(conferencia)
    db.commit()

    return {"resumo": resumo, "detalhes": detailed_results}
