# test_paypal.py
import sys
sys.path.append('.')

try:
    from paypal_service import PayPalService
    print("✅ PayPalService importé avec succès")
    
    service = PayPalService()
    print(f"✅ Service créé")
    
    if hasattr(service, 'is_initialized'):
        print(f"Service initialisé: {service.is_initialized()}")
    else:
        print("⚠️ Méthode is_initialized() non trouvée")
        
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
