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
            "venc": "", "valor": 0.0, "status": ""
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


def process_smart_reconciliation(db: Session, html_recebido: bytes = None):
    """
    Confere as parcelas QUITADAS/PARCIAL do ERP contra o banco do app.

    Chave de identificação: Pedido (left:132) + Vencimento (left:588)

    Classificação:
    - NORMAL      (verde):   Existe no app + valores coincidem (quitada normalmente)
    - DIVERGENCIA (amarelo): Existe no app + valores divergem
    - SUSPEITA    (vermelho): NÃO existe no app — nunca apareceu nas importações
    """
    import logging
    logger = logging.getLogger(__name__)

    # 1. Parsear relatório ERP e filtrar apenas QUITADA e PARCIAL
    all_erp = parse_rdprint_html(html_recebido) if html_recebido else []
    erp_items = [i for i in all_erp if i["status"] in ("QUITADA", "PARCIAL")]
    logger.info(f"[Conferencia] {len(erp_items)} itens QUITADA/PARCIAL de {len(all_erp)} no relatório")

    # 2. Construir índice do app por (contract_id = pedido) + vencimento
    all_insts = db.query(Installment).join(Customer).all()
    app_by_key = {}
    for inst in all_insts:
        venc_str = inst.due_date.strftime("%d/%m/%Y")
        key = f"{inst.contract_id}_{venc_str}"
        app_by_key[key] = inst

    detailed_results = []
    resumo = {
        "normal_qtd": 0, "normal_valor": 0.0,
        "divergencia_qtd": 0, "divergencia_valor": 0.0,
        "suspeita_qtd": 0, "suspeita_valor": 0.0,
    }

    # 3. Classificar cada item do ERP
    for erp in erp_items:
        pedido = erp.get("pedido", "").strip()
        venc = erp["venc"]
        erp_valor = erp["valor"]
        display_id = pedido or erp.get("doc", "N/A")

        key = f"{pedido}_{venc}"
        inst = app_by_key.get(key)
        cliente_nome = inst.customer.name if inst else erp["cliente"]

        if inst:
            # Comparar com open_amount (valor em aberto no app)
            app_valor = float(inst.open_amount) if inst.open_amount and float(inst.open_amount) > 0 else float(inst.amount)
            valores_ok = abs(erp_valor - app_valor) <= 0.01

            if valores_ok:
                # ✅ Quitada normalmente
                detailed_results.append({
                    "cliente": cliente_nome,
                    "doc": display_id,
                    "venc": venc,
                    "valor_erp": erp_valor,
                    "valor_app": app_valor,
                    "status_erp": erp["status"],
                    "situacao": "QUITADA NORMALMENTE",
                    "classe": "situacao-success",
                    "grupo": "NORMAL",
                })
                resumo["normal_qtd"] += 1
                resumo["normal_valor"] += erp_valor
            else:
                # ⚠️ Divergência de valor
                detailed_results.append({
                    "cliente": cliente_nome,
                    "doc": display_id,
                    "venc": venc,
                    "valor_erp": erp_valor,
                    "valor_app": app_valor,
                    "status_erp": erp["status"],
                    "situacao": "DIVERGÊNCIA DE VALOR",
                    "classe": "situacao-warning",
                    "grupo": "DIVERGENCIA",
                })
                resumo["divergencia_qtd"] += 1
                resumo["divergencia_valor"] += erp_valor
        else:
            # 🔴 Suspeita de exclusão
            detailed_results.append({
                "cliente": erp["cliente"],
                "doc": display_id,
                "venc": venc,
                "valor_erp": erp_valor,
                "valor_app": None,
                "status_erp": erp["status"],
                "situacao": "SUSPEITA DE EXCLUSÃO",
                "classe": "situacao-danger",
                "grupo": "SUSPEITA",
            })
            resumo["suspeita_qtd"] += 1
            resumo["suspeita_valor"] += erp_valor

    # 4. Salvar histórico no banco
    conferencia = ConferenciaTitulos(
        resumo_json=json.dumps(resumo),
        detalhes_json=json.dumps(detailed_results),
    )
    db.add(conferencia)
    db.commit()

    return {"resumo": resumo, "detalhes": detailed_results}
