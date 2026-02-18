import os

# Use raw bytes to avoid any encoding/newline issues in the script itself
content = b"""from decimal import Decimal
from datetime import date, datetime
import re
from typing import Optional, List
from urllib.parse import quote

def format_money(v) -> str:
    try:
        if v is None: return "R$ 0,00"
        d = Decimal(str(v))
        s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0,00"

def parse_decimal(v: str) -> Decimal:
    if not v: return Decimal("0")
    s = str(v).strip().replace("R$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except:
        return Decimal("0")

def parse_date_br(v: str) -> date:
    s = str(v).strip()
    if not s: raise ValueError("Empty date string")
    if re.match(r"^\\d{4}-\\d{2}-\\d{2}$", s):
        y,m,d = s.split("-")
        return date(int(y),int(m),int(d))
    m = re.match(r"^(\\d{2})[/-](\\d{2})[/-](\\d{4})$", s)
    if m:
        d,mo,y = m.groups()
        return date(int(y),int(mo),int(d))
    raise ValueError(f"Invalid date: {v}")

def bucket_priority(max_overdue: int) -> int:
    if max_overdue >= 90: return 5
    if max_overdue >= 30: return 4
    if max_overdue >= 5:  return 2
    return 1

def get_regua_nivel(customer_profile: str, max_overdue: int) -> str:
    if customer_profile and customer_profile != "AUTOMATICO":
        return customer_profile
    p = bucket_priority(max_overdue)
    if p >= 5: return "INTENSA"
    if p >= 3: return "MODERADA"
    return "LEVE"

def wa_link(phone: str, msg: str) -> str:
    if not phone: return ""
    p = "".join(filter(str.isdigit, phone))
    if not p.startswith("55"): p = "55" + p
    return f"https://wa.me/{p}?text={quote(msg)}"

def stores_list(db) -> List[str]:
    from app.models import Customer
    res = db.query(Customer.store).distinct().all()
    return sorted([r[0] for r in res if r[0]])

def rule_for_overdue(db, overdue_days: int, level: str = "LEVE"):
    from app.models import CollectionRule
    rules = db.query(CollectionRule).filter(
        CollectionRule.active == True,
        CollectionRule.level == level
    ).all()
    matched = [r for r in rules if r.start_days <= overdue_days <= r.end_days]
    if not matched:
        return None
    matched.sort(key=lambda r: (r.priority, r.start_days), reverse=True)
    return matched[0]
"""

def fix():
    target = "app/core/helpers.py"
    # Binary write
    with open(target, "wb") as f:
        f.write(content)
    print(f"Successfully wrote {os.path.abspath(target)}")

if __name__ == "__main__":
    fix()
