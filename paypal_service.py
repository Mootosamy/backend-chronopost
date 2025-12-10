import os
from paypal_checkout_sdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
from paypal_checkout_sdk.orders import OrdersCreateRequest, OrdersGetRequest, OrdersCaptureRequest
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
            raise ValueError("PayPal credentials not configured")
        
        # Initialize PayPal environment
        if self.mode == "live":
            environment = LiveEnvironment(client_id=self.client_id, client_secret=self.client_secret)
        else:
            environment = SandboxEnvironment(client_id=self.client_id, client_secret=self.client_secret)
        
        self.client = PayPalHttpClient(environment)
        logger.info(f"PayPal service initialized in {self.mode} mode")
    
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
                        "currency_code": currency if currency != "Rs" else "USD",  # PayPal doesn't support MUR directly
                        "value": amount_normalized
                    },
                    "description": f"Payment for order {reference}"
                }],
                "application_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                    "brand_name": "Chronopost Mauritius Ltd",
                    "landing_page": "BILLING",
                    "user_action": "PAY_NOW"
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
                "currency": currency
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
        try:
            request = OrdersGetRequest(order_id)
            response = self.client.execute(request)
            
            return {
                "order_id": response.result.id,
                "status": response.result.status,
                "amount": response.result.purchase_units[0].amount.value,
                "currency": response.result.purchase_units[0].amount.currency_code,
                "payer": response.result.payer if hasattr(response.result, 'payer') else None
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
        try:
            request = OrdersCaptureRequest(order_id)
            response = self.client.execute(request)
            
            # Extract capture details
            capture = response.result.purchase_units[0].payments.captures[0]
            
            logger.info(f"PayPal order captured: {order_id}, capture_id: {capture.id}")
            
            return {
                "order_id": response.result.id,
                "status": response.result.status,
                "capture_id": capture.id,
                "amount": capture.amount.value,
                "currency": capture.amount.currency_code,
                "payer_email": response.result.payer.email_address if hasattr(response.result, 'payer') else None,
                "payer_name": response.result.payer.name.given_name + " " + response.result.payer.name.surname if hasattr(response.result, 'payer') else None,
                "payer_id": response.result.payer.payer_id if hasattr(response.result, 'payer') else None
            }
        except Exception as e:
            logger.error(f"Error capturing PayPal order: {str(e)}")
            raise Exception(f"Failed to capture PayPal order: {str(e)}")
    
    def verify_webhook_signature(self, headers: dict, body: str) -> bool:
        """
        Verify PayPal webhook signature (simplified version)
        In production, implement full webhook verification
        
        Args:
            headers: Request headers
            body: Request body
        
        Returns:
            True if signature is valid
        """
        # TODO: Implement full webhook signature verification
        # For now, return True (not secure in production)
        logger.warning("Webhook signature verification not fully implemented")
        return True
