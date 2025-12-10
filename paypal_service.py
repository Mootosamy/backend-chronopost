# paypal_service.py
import os
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersGetRequest, OrdersCaptureRequest
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PayPalService:
    """PayPal payment service using PayPal Checkout SDK"""
    
    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_SECRET")
        self.mode = os.getenv("PAYPAL_MODE", "sandbox")
        
        if not self.client_id or not self.client_secret:
            logger.warning("PayPal credentials not configured - PayPal service will not work")
            # Ne pas lever d'exception immédiatement, permettre à l'application de démarrer
            self.client = None
            return
        
        # Initialize PayPal environment
        try:
            if self.mode == "live":
                environment = LiveEnvironment(
                    client_id=self.client_id, 
                    client_secret=self.client_secret
                )
            else:
                environment = SandboxEnvironment(
                    client_id=self.client_id, 
                    client_secret=self.client_secret
                )
            
            self.client = PayPalHttpClient(environment)
            logger.info(f"PayPal service initialized in {self.mode} mode")
            
        except Exception as e:
            logger.error(f"Failed to initialize PayPal client: {str(e)}")
            self.client = None
    
    def create_order(self, amount: str, currency: str, reference: str, 
                     return_url: str, cancel_url: str) -> Dict:
        """
        Create a PayPal order
        
        Args:
            amount: Amount as string (e.g., "1465.50")
            currency: Currency code (e.g., "USD", "EUR")
            reference: Merchant reference number
            return_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
        
        Returns:
            Dictionary with order details
        """
        if not self.client:
            raise Exception("PayPal client not initialized. Check your credentials.")
        
        try:
            # Convert amount format if needed (replace comma with dot)
            amount_normalized = amount.replace(',', '.').replace(' ', '')
            
            request = OrdersCreateRequest()
            request.prefer('return=representation')
            
            request.request_body({
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": reference,
                    "amount": {
                        "currency_code": "USD" if currency == "Rs" else currency,  # Convertir Rs (MUR) en USD
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
            })
            
            response = self.client.execute(request)
            
            # Extract approval URL
            approval_url = None
            for link in response.result.links:
                if link.rel == "approve":
                    approval_url = link.href
                    break
            
            logger.info(f"PayPal order created: {response.result.id}")
            
            return {
                "order_id": response.result.id,
                "status": response.result.status,
                "approval_url": approval_url,
                "amount": amount_normalized,
                "currency": currency,
                "paypal_response": response.result.dict()
            }
        except Exception as e:
            logger.error(f"Error creating PayPal order: {str(e)}")
            raise Exception(f"Failed to create PayPal order: {str(e)}")
    
    def get_order(self, order_id: str) -> Dict:
        """
        Get PayPal order details
        
        Args:
            order_id: PayPal order ID
        
        Returns:
            Dictionary with order details
        """
        if not self.client:
            raise Exception("PayPal client not initialized. Check your credentials.")
        
        try:
            request = OrdersGetRequest(order_id)
            response = self.client.execute(request)
            
            return {
                "order_id": response.result.id,
                "status": response.result.status,
                "amount": response.result.purchase_units[0].amount.value,
                "currency": response.result.purchase_units[0].amount.currency_code,
                "payer": response.result.payer if hasattr(response.result, 'payer') else None,
                "paypal_response": response.result.dict()
            }
        except Exception as e:
            logger.error(f"Error getting PayPal order: {str(e)}")
            raise Exception(f"Failed to get PayPal order: {str(e)}")
    
    def capture_order(self, order_id: str) -> Dict:
        """
        Capture (complete) a PayPal order
        
        Args:
            order_id: PayPal order ID
        
        Returns:
            Dictionary with capture details
        """
        if not self.client:
            raise Exception("PayPal client not initialized. Check your credentials.")
        
        try:
            request = OrdersCaptureRequest(order_id)
            response = self.client.execute(request)
            
            # Extract capture details
            capture = response.result.purchase_units[0].payments.captures[0]
            
            logger.info(f"PayPal order captured: {order_id}, capture_id: {capture.id}")
            
            result = {
                "order_id": response.result.id,
                "status": response.result.status,
                "capture_id": capture.id,
                "amount": capture.amount.value,
                "currency": capture.amount.currency_code,
                "capture_status": capture.status,
                "paypal_response": response.result.dict()
            }
            
            # Ajouter les informations du payeur si disponibles
            if hasattr(response.result, 'payer'):
                payer = response.result.payer
                result.update({
                    "payer_email": payer.email_address,
                    "payer_name": f"{payer.name.given_name} {payer.name.surname}",
                    "payer_id": payer.payer_id
                })
            
            return result
        except Exception as e:
            logger.error(f"Error capturing PayPal order: {str(e)}")
            raise Exception(f"Failed to capture PayPal order: {str(e)}")
    
    def verify_webhook_signature(self, headers: dict, body: str) -> bool:
        """
        Verify PayPal webhook signature
        
        Args:
            headers: Request headers
            body: Request body
        
        Returns:
            True if signature is valid
        """
        # Pour l'instant, retourner True pour le développement
        # IMPORTANT: Implémenter la vérification complète en production
        logger.warning("Webhook signature verification not fully implemented")
        return True
    
    def is_initialized(self) -> bool:
        """Check if PayPal service is properly initialized"""
        return self.client is not None
