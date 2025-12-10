from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone
import uuid


class User(BaseModel):
    """Admin user model for authentication"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: EmailStr
    hashed_password: str
    is_admin: bool = True
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    """Model for creating a new user"""
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Model for user login"""
    username: str
    password: str


class PaymentLink(BaseModel):
    """Payment link model"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: f"PAY-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:9]}")
    order_name: str
    order_number: str
    amount: str  # Stored as string to preserve comma format
    currency: str
    client_first_name: str
    client_last_name: str
    client_email: EmailStr
    link: str
    status: str = "Pending"  # Pending, Completed, Failed, Expired
    reference: str = Field(default_factory=lambda: f"MRU-INV{int(datetime.now(timezone.utc).timestamp())}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paypal_order_id: Optional[str] = None


class PaymentLinkCreate(BaseModel):
    """Model for creating a payment link"""
    order_name: str
    order_number: str
    amount: str
    currency: str
    client_first_name: str
    client_last_name: str
    client_email: EmailStr


class Transaction(BaseModel):
    """Transaction model for payment processing"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_link_id: str
    paypal_order_id: str
    paypal_capture_id: Optional[str] = None
    amount: str
    currency: str
    status: str  # CREATED, APPROVED, COMPLETED, FAILED
    payer_email: Optional[str] = None
    payer_name: Optional[str] = None
    payer_id: Optional[str] = None
    payment_method: str = "paypal"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class WebhookLog(BaseModel):
    """Model for logging PayPal webhooks"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    event_id: str
    resource_type: str
    resource_id: str
    payload: dict
    verified: bool = False
    processed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
