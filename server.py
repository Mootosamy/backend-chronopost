from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel, EmailStr, Field, ConfigDict
import os
import logging
import uuid
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone
from email_service import send_payment_email
from models import (
    User, UserCreate, UserLogin, 
    PaymentLink, PaymentLinkCreate,
    Transaction, WebhookLog
)
from auth_service import (
    verify_password, get_password_hash, 
    create_access_token, get_current_user_id
)
from paypal_service import PayPalService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncMongoClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize PayPal service
try:
    paypal_service = PayPalService()
except Exception as e:
    logger.error(f"Failed to initialize PayPal service: {str(e)}")
    paypal_service = None

# Security
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="Payment System API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# ==================== Authentication Functions ====================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user ID"""
    token = credentials.credentials
    user_id = get_current_user_id(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Verify user exists in database
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user_id

async def init_admin_user():
    """Initialize admin user if not exists"""
    try:
        logger.info("Skipping MongoDB admin initialization for PayPal testing")
        return
    except Exception as e:
        logger.error(f"MongoDB init error (ignored for testing): {str(e)}")

# ==================== Root & Health Check ====================

@api_router.get("/")
async def root():
    return {
        "message": "Payment System API",
        "version": "1.0.0",
        "status": "operational"
    }

@api_router.get("/test-cors")
async def test_cors(request: Request):
    """Test CORS configuration for frontend-backend link"""
    origin = request.headers.get("origin", "unknown")
    
    return {
        "status": "success",
        "message": "Backend-Frontend CORS test",
        "backend": "Render",
        "frontend_domain": "portal.merchant.cim.mu",
        "request_origin": origin,
        "cors_allowed": origin in ALLOWED_ORIGINS,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
@api_router.get("/test-cors")
async def test_cors(request: Request):
    """Test CORS configuration for frontend-backend link"""
    origin = request.headers.get("origin", "unknown")
    
    return {
        "status": "success",
        "message": "Backend-Frontend CORS test",
        "backend": "Render",
        "frontend_domain": "portal.merchant.cim.mu",
        "request_origin": origin,
        "cors_allowed": origin in ALLOWED_ORIGINS,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ==================== Authentication Routes ====================

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    """Admin login endpoint"""
    user = await db.users.find_one({"username": credentials.username}, {"_id": 0})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.get("is_active"):
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    # Create access token
    access_token = create_access_token(data={"sub": user["id"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False)
        }
    }

@api_router.get("/auth/me")
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """Get current user information"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

@api_router.post("/auth/register")
async def register(user_data: UserCreate, current_user_id: str = Depends(get_current_user)):
    """Register a new admin user (requires authentication)"""
    # Check if username already exists
    existing_user = await db.users.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists
    existing_email = await db.users.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_admin=True,
        is_active=True
    )
    
    doc = new_user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    await db.users.insert_one(doc)
    
    return {
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email
        }
    }

# ==================== Payment Links Routes ====================

@api_router.post("/payment-links", response_model=PaymentLink)
async def create_payment_link(
    payment_data: PaymentLinkCreate,
    user_id: str = Depends(get_current_user)
):
    """Create a new payment link"""
    try:
        payment_link_id = f"PAY-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{os.urandom(4).hex()}"
        payment_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/payment/{payment_link_id}"
        
        payment_link = PaymentLink(
            id=payment_link_id,
            order_name=payment_data.order_name,
            order_number=payment_data.order_number,
            amount=payment_data.amount,
            currency=payment_data.currency,
            client_first_name=payment_data.client_first_name,
            client_last_name=payment_data.client_last_name,
            client_email=payment_data.client_email,
            link=payment_url,
            status="Pending"
        )
        
        doc = payment_link.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        
        await db.payment_links.insert_one(doc)
        
        logger.info(f"Payment link created: {payment_link_id}")
        
        return payment_link
        
    except Exception as e:
        logger.error(f"Error creating payment link: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment link: {str(e)}")

@api_router.get("/payment-links", response_model=List[PaymentLink])
async def get_payment_links(user_id: str = Depends(get_current_user)):
    """Get all payment links"""
    payment_links = await db.payment_links.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for link in payment_links:
        if isinstance(link.get('created_at'), str):
            link['created_at'] = datetime.fromisoformat(link['created_at'])
        if isinstance(link.get('updated_at'), str):
            link['updated_at'] = datetime.fromisoformat(link['updated_at'])
    
    return payment_links

@api_router.get("/payment-links/{payment_id}")
async def get_payment_link(payment_id: str):
    """Get a specific payment link (public endpoint)"""
    payment_link = await db.payment_links.find_one({"id": payment_id}, {"_id": 0})
    
    if not payment_link:
        raise HTTPException(status_code=404, detail="Payment link not found")
    
    if isinstance(payment_link.get('created_at'), str):
        payment_link['created_at'] = datetime.fromisoformat(payment_link['created_at'])
    if isinstance(payment_link.get('updated_at'), str):
        payment_link['updated_at'] = datetime.fromisoformat(payment_link['updated_at'])
    
    return payment_link

@api_router.put("/payment-links/{payment_id}/status")
async def update_payment_link_status(
    payment_id: str,
    status: str,
    paypal_order_id: Optional[str] = None
):
    """Update payment link status (can be called by webhook or after payment)"""
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if paypal_order_id:
        update_data["paypal_order_id"] = paypal_order_id
    
    result = await db.payment_links.update_one(
        {"id": payment_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Payment link not found")
    
    return {"message": "Status updated successfully"}

# ==================== Email Routes ====================

class PaymentEmailData(BaseModel):
    recipient_email: EmailStr
    order_name: str
    order_number: str
    amount: str
    currency: str
    client_first_name: str
    client_last_name: str
    payment_link: str
    reference: str

@api_router.get("/preview-email")
async def preview_email_template():
    """Preview the email template HTML"""
    from email_service import create_payment_email_template
    from fastapi.responses import HTMLResponse
    
    sample_data = {
        'order_name': 'Sample Order',
        'order_number': 'ORD-12345',
        'amount': '1000.00',
        'currency': 'Rs',
        'client_first_name': 'John',
        'client_last_name': 'Doe',
        'payment_link': 'https://example.com/payment/PAY-123',
        'reference': 'REF-123'
    }
    
    html_content = create_payment_email_template(sample_data)
    return HTMLResponse(content=html_content)

@api_router.post("/send-payment-email")
async def send_payment_email_endpoint(
    email_data: PaymentEmailData,
    user_id: str = Depends(get_current_user)
):
    """Send payment link email to customer"""
    try:
        payment_data = {
            'order_name': email_data.order_name,
            'order_number': email_data.order_number,
            'amount': email_data.amount,
            'currency': email_data.currency,
            'client_first_name': email_data.client_first_name,
            'client_last_name': email_data.client_last_name,
            'payment_link': email_data.payment_link,
            'reference': email_data.reference
        }
        
        result = await send_payment_email(email_data.recipient_email, payment_data)
        
        return {
            "message": "Email sent successfully",
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# ==================== PayPal Payment Routes ====================

@api_router.post("/paypal/create-order")
async def create_paypal_order(payment_id: str):
    """Create a PayPal order for a payment link"""
    if not paypal_service:
        raise HTTPException(status_code=500, detail="PayPal service not configured")
    
    payment_link = await db.payment_links.find_one({"id": payment_id}, {"_id": 0})
    if not payment_link:
        raise HTTPException(status_code=404, detail="Payment link not found")
    
    if payment_link.get("status") != "Pending":
        raise HTTPException(status_code=400, detail="Payment link is not in pending status")
    
    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return_url = f"{frontend_url}/payment/{payment_id}/success"
        cancel_url = f"{frontend_url}/payment/{payment_id}/cancel"
        
        order_result = paypal_service.create_order(
            amount=payment_link['amount'],
            currency=payment_link['currency'],
            reference=payment_link['reference'],
            return_url=return_url,
            cancel_url=cancel_url
        )
        
        await db.payment_links.update_one(
            {"id": payment_id},
            {"$set": {
                "paypal_order_id": order_result['order_id'],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        transaction = Transaction(
            payment_link_id=payment_id,
            paypal_order_id=order_result['order_id'],
            amount=order_result['amount'],
            currency=order_result['currency'],
            status="CREATED"
        )
        
        doc = transaction.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.transactions.insert_one(doc)
        
        logger.info(f"PayPal order created: {order_result['order_id']} for payment {payment_id}")
        
        return {
            "order_id": order_result['order_id'],
            "approval_url": order_result['approval_url'],
            "status": order_result['status']
        }
        
    except Exception as e:
        logger.error(f"Error creating PayPal order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class CaptureOrderRequest(BaseModel):
    order_id: str
    payment_id: str

@api_router.post("/paypal/capture-order")
async def capture_paypal_order(data: CaptureOrderRequest):
    """Capture a PayPal order after approval"""
    if not paypal_service:
        raise HTTPException(status_code=500, detail="PayPal service not configured")
    
    try:
        capture_result = paypal_service.capture_order(data.order_id)
        
        await db.transactions.update_one(
            {"paypal_order_id": data.order_id},
            {"$set": {
                "status": capture_result['status'],
                "paypal_capture_id": capture_result['capture_id'],
                "payer_email": capture_result.get('payer_email'),
                "payer_name": capture_result.get('payer_name'),
                "payer_id": capture_result.get('payer_id'),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        await db.payment_links.update_one(
            {"id": data.payment_id},
            {"$set": {
                "status": "Completed",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logger.info(f"PayPal order captured: {data.order_id} for payment {data.payment_id}")
        
        return {
            "message": "Payment completed successfully",
            "order_id": data.order_id,
            "capture_id": capture_result['capture_id'],
            "status": capture_result['status'],
            "payer_email": capture_result.get('payer_email'),
            "payer_name": capture_result.get('payer_name'),
            "amount": capture_result['amount'],
            "currency": capture_result['currency']
        }
        
    except Exception as e:
        logger.error(f"Error capturing PayPal order: {str(e)}")
        
        await db.transactions.update_one(
            {"paypal_order_id": data.order_id},
            {"$set": {
                "status": "FAILED",
                "metadata": {"error": str(e)}
            }}
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/paypal/order/{order_id}")
async def get_paypal_order(order_id: str):
    """Get PayPal order details"""
    if not paypal_service:
        raise HTTPException(status_code=500, detail="PayPal service not configured")
    
    try:
        order_details = paypal_service.get_order(order_id)
        return order_details
    except Exception as e:
        logger.error(f"Error getting PayPal order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Webhook Routes ====================

@api_router.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    """Handle PayPal webhook events"""
    try:
        body = await request.body()
        headers = dict(request.headers)
        
        import json
        payload = json.loads(body)
        
        webhook_log = WebhookLog(
            event_type=payload.get('event_type', 'unknown'),
            event_id=payload.get('id', 'unknown'),
            resource_type=payload.get('resource_type', 'unknown'),
            resource_id=payload.get('resource', {}).get('id', 'unknown'),
            payload=payload,
            verified=True
        )
        
        doc = webhook_log.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.webhook_logs.insert_one(doc)
        
        event_type = payload.get('event_type')
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            order_id = payload.get('resource', {}).get('supplementary_data', {}).get('related_ids', {}).get('order_id')
            
            if order_id:
                await db.transactions.update_one(
                    {"paypal_order_id": order_id},
                    {"$set": {
                        "status": "COMPLETED",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                payment_link = await db.payment_links.find_one({"paypal_order_id": order_id})
                if payment_link:
                    await db.payment_links.update_one(
                        {"id": payment_link['id']},
                        {"$set": {
                            "status": "Completed",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                
                logger.info(f"Webhook: Payment completed for order {order_id}")
        
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            order_id = payload.get('resource', {}).get('supplementary_data', {}).get('related_ids', {}).get('order_id')
            
            if order_id:
                await db.transactions.update_one(
                    {"paypal_order_id": order_id},
                    {"$set": {"status": "DENIED"}}
                )
                
                payment_link = await db.payment_links.find_one({"paypal_order_id": order_id})
                if payment_link:
                    await db.payment_links.update_one(
                        {"id": payment_link['id']},
                        {"$set": {
                            "status": "Failed",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                
                logger.warning(f"Webhook: Payment denied for order {order_id}")
        
        await db.webhook_logs.update_one(
            {"id": webhook_log.id},
            {"$set": {"processed": True}}
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==================== Transaction Routes ====================

@api_router.get("/transactions")
async def get_transactions(user_id: str = Depends(get_current_user)):
    """Get all transactions"""
    transactions = await db.transactions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for trans in transactions:
        if isinstance(trans.get('created_at'), str):
            trans['created_at'] = datetime.fromisoformat(trans['created_at'])
        if trans.get('completed_at') and isinstance(trans['completed_at'], str):
            trans['completed_at'] = datetime.fromisoformat(trans['completed_at'])
    
    return transactions

@api_router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str, user_id: str = Depends(get_current_user)):
    """Get a specific transaction"""
    transaction = await db.transactions.find_one({"id": transaction_id}, {"_id": 0})
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if isinstance(transaction.get('created_at'), str):
        transaction['created_at'] = datetime.fromisoformat(transaction['created_at'])
    if transaction.get('completed_at') and isinstance(transaction['completed_at'], str):
        transaction['completed_at'] = datetime.fromisoformat(transaction['completed_at'])
    
    return transaction

# ==================== App Configuration ====================

app.include_router(api_router)

# Liste explicite des domaines autorisés
ALLOWED_ORIGINS = [
    "https://portal.merchant.cim.mu",      # Votre domaine principal
    "http://portal.merchant.cim.mu",       # Version HTTP (au cas où)
    "https://www.portal.merchant.cim.mu",  # Avec www
    "http://localhost:3000",               # Dev React
    "http://localhost:5173",               # Dev Vite
    "http://127.0.0.1:5500",               # Live Server
]

# Récupère les origines depuis les variables d'environnement (si définies)
env_origins = os.environ.get('CORS_ORIGINS', '')
if env_origins:
    ALLOWED_ORIGINS.extend(env_origins.split(','))

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ==================== App Events ====================

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Payment System API...")
    await init_admin_user()
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_db_client():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    await client.close()
    logger.info("Database connection closed")

