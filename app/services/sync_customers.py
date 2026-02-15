import re
import logging
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
logger = logging.getLogger("sync_customers")

def sync_erp_customers(file_path: str, db: Session):
    from app.main import Customer
    """
    Lê o relatório HTM do InfoCommerce e sincroniza o cadastro de clientes.
    """
    if not hasattr(db, 'commit'):
        # Just a safety check for the session object
        raise ValueError("Invalid database session")

    logger.info(f"Iniciando sincronização de clientes a partir de: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Erro ao ler arquivo ERP: {e}")
        return {"error": f"Erro ao ler arquivo: {e}"}

    soup = BeautifulSoup(content, 'html.parser')
    divs = []
    for div in soup.find_all('div'):
        style = div.get('style', '').lower()
        top = None
        left = None
        if 'top:' in style:
            try:
                top_str = re.search(r'top:(\d+)', style).group(1)
                top = int(top_str)
            except: pass
        if 'left:' in style:
            try:
                left_str = re.search(r'left:(\d+)', style).group(1)
                left = int(left_str)
            except: pass
        
        text = div.get_text(strip=True)
        if text:
            divs.append({'top': top, 'left': left, 'text': text})

    # Agrupar por 'top' para processar linha a linha
    rows = {}
    for d in divs:
        t = d['top']
        if t is None: continue
        if t not in rows: rows[t] = []
        rows[t].append(d)

    sorted_tops = sorted(rows.keys())
    
    customers_found = []
    current_customer = None
    
    # Padrões para identificar dados
    cpf_pattern = re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{4}\.\d{3}/\d{4}-\d{2}')
    # Padrão ultra-flexível para telefones do InfoCommerce (ex: (67)-9999-9999 ou 67 99999999)
    phone_pattern = re.compile(r'\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}')

    i = 0
    while i < len(sorted_tops):
        top = sorted_tops[i]
        line_divs = rows[top]
        line_elements = {d['left']: d['text'] for d in line_divs}
        
        # Identifica início de um cliente (Código no Left 54)
        if 54 in line_elements and str(line_elements[54]).isdigit():
            # Novo cliente detectado
            current_customer = {
                "external_key": str(line_elements[54]),
                "name": "",
                "address": "",
                "whatsapp": "",
                "cpf_cnpj": "",
            }
            
            # O processamento do cliente agora engloba a linha ATUAL e as próximas (até 300px)
            j = i
            while j < len(sorted_tops) and sorted_tops[j] - top < 300:
                next_top = sorted_tops[j]
                next_line = {d['left']: d['text'] for d in rows[next_top]}
                
                # Se for uma nova linha (j > i) e encontrar outro código erp diferente, interrompe
                if j > i and 54 in next_line:
                    next_code = str(next_line[54]).strip()
                    if next_code.isdigit() and next_code != current_customer["external_key"]:
                        break
                
                # Analisa todos os elementos da linha
                for l_pos, val in next_line.items():
                    val = val.strip()
                    if not val: continue
                    
                    # 1. Captura o Nome (está na linha do código, geralmente Left 102)
                    if j == i and l_pos > 54 and l_pos < 400:
                        # Evita capturar data ou telefone como nome
                        if not re.search(r'\d{2}/\d{2}', val) and not phone_pattern.search(val):
                            current_customer["name"] = (current_customer["name"] + " " + val).strip()
                    
                    # 2. Captura CPF/CNPJ
                    if cpf_pattern.search(val):
                        current_customer["cpf_cnpj"] = val
                    
                    # 3. Captura Telefone (Fixos ou Celulares)
                    digit_only = re.sub(r'\D', '', val)
                    # InfoCommerce usa (67)-3471-1111 ou 67 96734711
                    if (len(digit_only) >= 10 and len(digit_only) <= 12) or phone_pattern.search(val):
                        # Prioriza celular (11 dígitos) se houver múltiplos
                        if not current_customer["whatsapp"] or len(digit_only) == 11:
                            current_customer["whatsapp"] = val
                    
                    # 4. Captura Endereço (Colunas largas ou linhas subsequentes)
                    # Se j == i, pegamos colunas > 600 (Geralmente Cidade/Estado)
                    # Se j > i, pegamos colunas proximas a 102 (Endereço Rua)
                    is_addr_col = (j == i and l_pos > 600) or (j > i and l_pos > 80 and l_pos < 500)
                    if is_addr_col:
                        # Valida se não é Nome, CPF ou Telefone
                        if val not in current_customer["name"] and not cpf_pattern.search(val) and not (len(digit_only) >= 10 and digit_only.isdigit()):
                            if current_customer["address"]:
                                if val not in current_customer["address"]:
                                    current_customer["address"] += ", " + val
                            else:
                                current_customer["address"] = val
                j += 1
            
            # Validação mínima: Ter nome
            if current_customer["name"]:
                customers_found.append(current_customer)
            
            # Avançamos o ponteiro i para a última linha processada para este cliente
            i = j - 1
            
        i += 1
    
    logger.info(f"Processados {len(customers_found)} potenciais clientes do arquivo.")
    
    # Salvar no banco
    created = 0
    updated = 0
    
    for c_data in customers_found:
        ext_key = str(c_data["external_key"]).strip()
        # Limpa o nome para match melhor
        name = c_data["name"].strip().rstrip('-').strip()
        
        # 1. Tenta buscar pelo Código (external_key numérico)
        cust = db.query(Customer).filter(Customer.external_key == ext_key).first()
        
        # 2. Se não encontrar, tenta buscar pelo Nome
        if not cust:
            # Busca case-insensitive
            cust = db.query(Customer).filter(Customer.name.ilike(name)).first()
        
        if cust:
            # Se encontrou pelo nome, aproveitamos para atualizar o external_key para o código numérico
            if cust.external_key != ext_key:
                # logger.info(f"Atualizando indexador do cliente {name}: {cust.external_key} -> {ext_key}")
                cust.external_key = ext_key
            
            # Atualiza/Enriquece dados
            # Limpamos dados antes de salvar
            whatsapp_clean = re.sub(r'[^\d() -]', '', c_data["whatsapp"]).strip()
            address_clean = c_data["address"].strip().rstrip(',').strip()
            cpf_clean = re.sub(r'[^\d.-/]', '', c_data["cpf_cnpj"]).strip()
            
            if whatsapp_clean and (not cust.whatsapp or len(cust.whatsapp) < 8):
                cust.whatsapp = whatsapp_clean
            if address_clean and not cust.address:
                cust.address = address_clean
            if cpf_clean and not cust.cpf_cnpj:
                cust.cpf_cnpj = cpf_clean
            
            updated += 1
        else:
            # Cria novo apenas se tiver dados relevantes
            if len(name) > 3 and ext_key:
                new_cust = Customer(
                    external_key=ext_key,
                    name=name,
                    whatsapp=c_data["whatsapp"].strip(),
                    address=c_data["address"].strip(),
                    cpf_cnpj=c_data["cpf_cnpj"].strip(),
                    store="LOJA 1"
                )
                db.add(new_cust)
                created += 1
            
        # Commit periódico
        if (created + updated) % 200 == 0:
            db.commit()

    db.commit()
    logger.info(f"Sincronização finalizada: {created} novos, {updated} atualizados.")
    return {
        "success": True,
        "total": len(customers_found),
        "created": created,
        "updated": updated
    }
