import os
from paypal_checkout_sdk.client import PayPalClient
from paypal_checkout_sdk.services.orders import OrdersService
from paypal_checkout_sdk.enums import Environment
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class PayPalService:
    """PayPal payment service using PayPal Checkout SDK v1.2.2"""
    
    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_SECRET")
        self.mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
        
        if not self.client_id or not self.client_secret:
            logger.warning("PayPal credentials not configured")
            self.client = None
            self.orders_service = None
            return
        
        try:
            # Déterminer l'environnement
            environment = Environment.SANDBOX if self.mode == "sandbox" else Environment.LIVE
            
            # Initialiser le client PayPal
            self.client = PayPalClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                environment=environment
            )
            
            # Initialiser le service orders
            self.orders_service = OrdersService(self.client)
            
            logger.info(f"✅ PayPal service initialized in {self.mode} mode")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize PayPal: {str(e)}")
            self.client = None
            self.orders_service = None
    
    def create_order(self, amount: str, currency: str, reference: str, 
                     return_url: str, cancel_url: str) -> Dict:
        """Create a PayPal order"""
        if not self.orders_service:
            raise Exception("PayPal service not initialized. Check your credentials.")
        
        try:
            # Normaliser le montant
            amount_normalized = amount.replace(',', '.').replace(' ', '')
            
            # PayPal ne supporte pas Rs (MUR) directement, utiliser USD
            paypal_currency = "USD" if currency == "Rs" else currency
            
            # Préparer les données de la commande
            order_data = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": reference,
                    "amount": {
                        "currency_code": paypal_currency,
                        "value": amount_normalized
                    },
                    "description": f"Payment for order {reference}"
                }],
                "application_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                    "brand_name": "Chronopost Mauritius Ltd",
                    "landing_page": "BILLING",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING"
                }
            }
            
            # Créer la commande
            response = self.orders_service.create_order(order_data)
            
            # Extraire l'URL d'approbation
            approval_url = None
            if hasattr(response, 'links'):
                for link in response.links:
                    if hasattr(link, 'rel') and link.rel == "approve":
                        approval_url = link.href
                        break
            
            logger.info(f"✅ PayPal order created: {response.id}")
            
            return {
                "order_id": response.id,
                "status": response.status,
                "approval_url": approval_url,
                "amount": amount_normalized,
                "currency": paypal_currency,
                "paypal_response": {
                    "id": response.id,
                    "status": response.status,
                    "links": [{"rel": link.rel, "href": link.href} for link in response.links] if hasattr(response, 'links') else []
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating PayPal order: {str(e)}")
            raise Exception(f"Failed to create PayPal order: {str(e)}")
    
    def get_order(self, order_id: str) -> Dict:
        """Get order details"""
        if not self.orders_service:
            raise Exception("PayPal service not initialized")
        
        try:
            response = self.orders_service.get_order(order_id)
            
            return {
                "order_id": response.id,
                "status": response.status,
                "amount": response.purchase_units[0].amount.value if response.purchase_units else None,
                "currency": response.purchase_units[0].amount.currency_code if response.purchase_units else None,
                "create_time": response.create_time if hasattr(response, 'create_time') else None,
                "update_time": response.update_time if hasattr(response, 'update_time') else None
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting PayPal order: {str(e)}")
            raise Exception(f"Failed to get PayPal order: {str(e)}")
    
    def capture_order(self, order_id: str) -> Dict:
        """Capture a PayPal order"""
        if not self.orders_service:
            raise Exception("PayPal service not initialized")
        
        try:
            # Capturer la commande
            response = self.orders_service.capture_order(order_id)
            
            logger.info(f"✅ PayPal order captured: {order_id}")
            
            # Extraire les détails de capture
            result = {
                "order_id": response.id,
                "status": response.status,
                "capture_time": response.create_time if hasattr(response, 'create_time') else None
            }
            
            # Ajouter les infos de capture si disponibles
            if (hasattr(response, 'purchase_units') and response.purchase_units and
                hasattr(response.purchase_units[0], 'payments') and
                hasattr(response.purchase_units[0].payments, 'captures') and
                response.purchase_units[0].payments.captures):
                
                capture = response.purchase_units[0].payments.captures[0]
                result.update({
                    "capture_id": capture.id,
                    "amount": capture.amount.value,
                    "currency": capture.amount.currency_code,
                    "capture_status": capture.status
                })
            
            # Ajouter les infos du payeur si disponibles
            if hasattr(response, 'payer'):
                payer = response.payer
                result.update({
                    "payer_email": payer.email_address if hasattr(payer, 'email_address') else None,
                    "payer_id": payer.payer_id if hasattr(payer, 'payer_id') else None,
                    "payer_name": f"{payer.name.given_name} {payer.name.surname}" if hasattr(payer, 'name') else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error capturing PayPal order: {str(e)}")
            raise Exception(f"Failed to capture PayPal order: {str(e)}")
    
    def is_initialized(self) -> bool:
        """Check if PayPal service is properly initialized"""
        return self.orders_service is not None
