from datetime import datetime, date, time
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.services.compliance import calcular_data_disparo, is_feriado_nacional, is_domingo, TZ

def run_tests():
    with open("compliance_results.txt", "w", encoding="utf-8") as f:
        f.write("🔹 Testando Lógica de Compliance 🔹\n")
        
        # Caso 1: Vencimento Normal (Segunda 12/02/2026 - Pós Carnaval?)
        # Carnaval 2026 é 17/02. 12/02 é Quinta.
        venc = date(2026, 2, 12) 
        # Regra D+3 -> 15/02 (Domingo).
        # 16/02 (Seg - Carnaval na lista) -> Pula
        # 17/02 (Ter - Carnaval na lista) -> Pula
        # 18/02 (Qua - Cinzas/Normal) -> Alvo
        target_esperado = datetime(2026, 2, 18, 9, 0, tzinfo=TZ)
        
        resultado = calcular_data_disparo(venc, 3)
        
        status = '✅' if resultado == target_esperado else '❌'
        f.write(f"Teste 1 (Dom -> Seg): {status}\n")
        f.write(f"   Venc: {venc} + 3 dias = 15/02 (Dom)\n")
        f.write(f"   Esperado: {target_esperado}\n")
        f.write(f"   Obtido:   {resultado}\n")

        # Caso 2: Feriado Nacional (15/11 - Proclamação)
        # 2024: 15/11 é Sexta.
        venc = date(2024, 11, 12) # Terça
        # Regra D+3 -> 15/11 (Sexta - Feriado). Deve pular para 16/11 (Sábado).
        # Sábado é permitido? Sim.
        target_esperado = datetime(2024, 11, 16, 9, 0, tzinfo=TZ)
        
        resultado = calcular_data_disparo(venc, 3)
        
        status = '✅' if resultado == target_esperado else '❌'
        f.write(f"\nTeste 2 (Feriado -> Sábado): {status}\n")
        f.write(f"   Venc: {venc} + 3 dias = 15/11 (Feriado)\n")
        f.write(f"   Esperado: {target_esperado}\n")
        f.write(f"   Obtido:   {resultado}\n")
        
        # Caso 3: Feriado Caindo no Domingo?
        # 2025: 02/11 (Finados) é Domingo.
        # Venc: 28/10 (Terça). D+5 = 02/11 (Dom/Feriado).
        # Pula pra 03/11 (Segunda).
        venc = date(2025, 10, 28)
        target_esperado = datetime(2025, 11, 3, 9, 0, tzinfo=TZ)
        
        resultado = calcular_data_disparo(venc, 5)

        status = '✅' if resultado == target_esperado else '❌'
        f.write(f"\nTeste 3 (Dom+Feriado -> Seg): {status}\n")
        f.write(f"   Venc: {venc} + 5 dias = 02/11 (Dom/Feriado)\n")
        f.write(f"   Esperado: {target_esperado}\n")
        f.write(f"   Obtido:   {resultado}\n")
        
        # Caso 4: Horário (Ajuste para 09:00)
        # Função calcular_data_disparo já força 09:00.
        # Vamos testar normalização direta.
        from app.services.compliance import normalizar_para_janela_comercial
        
        dt_input = datetime(2024, 5, 20, 19, 30, tzinfo=TZ) # Seg 19:30
        # Deve ir para Terça 09:00
        target_esperado = datetime(2024, 5, 21, 9, 0, tzinfo=TZ)
        resultado = normalizar_para_janela_comercial(dt_input)
        
        status = '✅' if resultado == target_esperado else '❌'
        f.write(f"\nTeste 4 (19:30 -> Next Day 09:00): {status}\n")
        f.write(f"   Input:    {dt_input}\n")
        f.write(f"   Esperado: {target_esperado}\n")
        f.write(f"   Obtido:   {resultado}\n")

if __name__ == "__main__":
    run_tests()
