from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .common import BaseResponse


class GatewayWebhookPayload(BaseModel):
    """Schema for incoming gateway webhook payload."""
    
    event_type: str = Field(..., description="Gateway event type")
    transaction_id: UUID = Field(..., description="Transaction ID")
    gateway_reference: str = Field(..., description="Gateway reference")
    status: str = Field(..., description="Payment status")
    amount: float = Field(..., description="Payment amount")
    currency: str = Field(default="AED", description="Payment currency")
    occurred_at: datetime = Field(..., description="When the event occurred")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GatewayResponse(BaseResponse):
    """Schema for gateway response."""
    
    status: str = Field(..., description="Processing status")
    message: str = Field(default="Webhook received", description="Response message")
    transaction_id: Optional[UUID] = Field(None, description="Transaction ID if provided")


class MockGatewayPaymentRequest(BaseModel):
    """Schema for mock gateway payment request."""
    
    transaction_id: UUID = Field(..., description="Internal transaction ID")
    amount: float = Field(..., ge=0, description="Payment amount")
    currency: str = Field(default="AED", description="Currency")
    card_number: str = Field(..., description="Card number")
    card_expiry: str = Field(..., description="Card expiry")
    card_cvv: str = Field(..., description="Card CVV")
    cardholder_name: str = Field(..., description="Cardholder name")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MockGatewayPaymentResponse(BaseModel):
    """Schema for mock gateway payment response."""
    
    gateway_reference: str = Field(..., description="Gateway reference")
    status: str = Field(..., description="Payment status")
    message: str = Field(..., description="Status message")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict) 