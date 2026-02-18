import os

CONTENT = """from decimal import Decimal
from datetime import date, datetime
import re
from typing import Optional

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
"""

def fix():
    path = "app/core/utils.py"
    if os.path.exists(path):
        os.remove(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(CONTENT)
    print(f"Fixed {path}")

if __name__ == "__main__":
    fix()
