from app.services.whatsapp import enviar_whatsapp

def test_integration():
    print("--- Teste de Integração App -> Z-API ---")
    
    # Número de teste do usuário
    telefone = "5567996524740" 
    msg = "Teste Final de Integração - Se receber isso, o sistema está PRONTO para deploy! 🚀"
    
    # MODO_TESTE = False para enviar de verdade
    try:
        resultado = enviar_whatsapp(telefone, msg, modo_teste=False)
        
        print(f"Resultado: {resultado}")
        
        if resultado.get("success") and resultado.get("modo") == "ENVIADO":
            print("\n✅ SUCESSO! Mensagem enviada via API Oficial.")
        else:
            print("\n❌ FALHA! Verifique o erro acima.")
            
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    test_integration()
