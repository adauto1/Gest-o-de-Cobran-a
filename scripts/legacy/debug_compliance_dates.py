from datetime import date
from app.services.compliance import calcular_data_disparo

# 15/02/2026 is Sunday
base_date = date(2026, 2, 15)

# Simulate rules D+0 (Start=0 of relative date or Start=3 of 12/02)
# In scenario:
# C001: 12/02 + 3 = 15/02.
# C002: 08/02 + 7 = 15/02.
# So nominal trigger is 15/02.

adjusted = calcular_data_disparo(base_date, 0) # 15/02 + 0 -> Shifted
print(f"Nominal 15/02/2026 -> Shifted: {adjusted}")

# Check 16/02, 17/02, 18/02
print(f"16/02 adj: {calcular_data_disparo(date(2026, 2, 16), 0)}")
print(f"17/02 adj: {calcular_data_disparo(date(2026, 2, 17), 0)}")
print(f"18/02 adj: {calcular_data_disparo(date(2026, 2, 18), 0)}")
