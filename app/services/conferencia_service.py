import re
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Installment, Customer

def parse_date_str(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except:
        return None

def parse_valor_br(texto):
    try:
        v = texto.strip().replace('.', '').replace(',', '.')
        return float(v)
    except:
        return 0.0

def parse_rdprint_50(content: bytes):
    """
    Parses RDPrint 5.0 HTML based on fixed left positions:
    54 -> Data emissão (DD/MM/AAAA)
    132 -> Pedido
    204 -> D.A.V. (opcional)
    264 -> Nome do cliente
    522 -> N.Doc (contract_id no nosso banco)
    588 -> Vencimento
    648 -> Valor
    762 -> Status (EM ABERTO, VENCIDA, QUITADA)
    """
    soup = BeautifulSoup(content, "html.parser")
    
    # Regex para extrair left:XX
    re_left = re.compile(r'left:(\d+)')
    re_top = re.compile(r'top:(\d+)')

    elements = []
    for div in soup.find_all("div"):
        style = div.get("style", "")
        lm = re_left.search(style)
        tm = re_top.search(style)
        if lm and tm:
            text = div.get_text(" ", strip=True)
            if not text: continue
            elements.append({
                'top': int(tm.group(1)),
                'left': int(lm.group(1)),
                'text': text
            })

    if not elements:
        return []

    # Agrupar por linhas (top similar)
    elements.sort(key=lambda x: (x['top'], x['left']))
    rows = []
    if elements:
        curr_row = [elements[0]]
        curr_y = elements[0]['top']
        for el in elements[1:]:
            if abs(el['top'] - curr_y) <= 4:
                curr_row.append(el)
            else:
                rows.append(curr_row)
                curr_row = [el]
                curr_y = el['top']
        rows.append(curr_row)

    structured_data = []
    for row in rows:
        # Procurar elemento na posição left:54 que seja uma data
        # Linhas válidas começam com data na pos 54
        start_el = next((el for el in row if el['left'] == 54), None)
        if not start_el or not re.match(r'\d{2}/\d{2}/\d{4}', start_el['text']):
            continue
        
        item = {
            "emissao": start_el['text'],
            "cliente": "",
            "doc": "",
            "vencimento": "",
            "valor": 0.0,
            "valor_str": "",
            "status": ""
        }

        for el in row:
            l = el['left']
            txt = el['text']
            if l == 264: item["cliente"] = txt
            elif l == 522: item["doc"] = txt
            elif l == 588: item["vencimento"] = txt
            elif l == 648: 
                item["valor_str"] = txt
                item["valor"] = parse_valor_br(txt)
            elif l == 762: item["status"] = txt

        # Chave de identificação: N.Doc + Vencimento
        if item["doc"] and item["vencimento"]:
            structured_data.append(item)

    return structured_data

def process_comparison(db: Session, html_receber: bytes = None, html_recebidos: bytes = None):
    """
    Compara os dados do ERP com o Banco do App.
    """
    erp_data = {} # Key: doc + vencimento
    
    # 1. Parsear arquivos do ERP
    if html_receber:
        for item in parse_rdprint_50(html_receber):
            key = f"{item['doc']}_{item['vencimento']}"
            erp_data[key] = item

    if html_recebidos:
        for item in parse_rdprint_50(html_recebidos):
            key = f"{item['doc']}_{item['vencimento']}"
            # Se já estiver (apenas atualiza status se for recebidos, embora deva ser único)
            erp_data[key] = item

    # 2. Buscar parcelas em aberto/vencidas do banco
    # Carregamos parcelas que não estão quitadas no nosso banco para conferir
    app_installments = db.query(Installment).join(Customer).filter(
        Installment.status != "QUITADA"
    ).all()

    results = []
    matched_keys = set()

    for inst in app_installments:
        venc_str = inst.due_date.strftime("%d/%m/%Y")
        key = f"{inst.contract_id}_{venc_str}"
        
        erp_item = erp_data.get(key)
        
        entry = {
            "id": inst.id,
            "cliente": inst.customer.name,
            "doc": inst.contract_id,
            "vencimento": venc_str,
            "valor_app": float(inst.amount),
            "valor_erp": None,
            "status_app": inst.status,
            "status_erp": None,
            "situacao": "SEM_ALTERACAO", # Default
            "classe": "" # CSS class
        }

        if erp_item:
            matched_keys.add(key)
            entry["valor_erp"] = erp_item["valor"]
            entry["status_erp"] = erp_item["status"]
            
            # Comparação
            if erp_item["status"] == "QUITADA":
                entry["situacao"] = "QUITADA_NO_ERP"
                entry["classe"] = "situacao-quitada"
            elif abs(erp_item["valor"] - float(inst.amount)) > 0.01:
                entry["situacao"] = "DIVERGENCIA_VALOR"
                entry["classe"] = "situacao-divergente"
            else:
                entry["situacao"] = "SOLIDO" # Tudo OK
                entry["classe"] = "situacao-ok"
        else:
            # Não está nos relatórios do ERP mas está no banco como aberta
            entry["situacao"] = "CANCELADA_OU_EXCLUIDA"
            entry["classe"] = "situacao-cancelada"
        
        results.append(entry)

    # 3. Identificar títulos no ERP que NÃO estão no banco (Novos - Opcional, mas útil)
    # Segundo o requisito, o foco é o que sumiu ou mudou, mas podemos listar novos se quiser.
    # Por ora, focamos no requisito "conferência".

    return results
