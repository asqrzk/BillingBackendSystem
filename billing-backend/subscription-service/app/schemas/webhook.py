from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .common import BaseResponse


class WebhookPayload(BaseModel):
    """Schema for incoming webhook payload from payment service."""
    
    event_id: str = Field(..., description="Unique event identifier")
    transaction_id: UUID = Field(..., description="Transaction ID")
    subscription_id: UUID = Field(..., description="Subscription ID")
    status: str = Field(..., description="Payment status")
    amount: float = Field(..., description="Payment amount")
    currency: str = Field(default="AED", description="Payment currency")
    occurred_at: datetime = Field(..., description="When the event occurred")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WebhookResponse(BaseResponse):
    """Schema for webhook response."""
    
    status: str = Field(..., description="Processing status")
    message: str = Field(default="Webhook received", description="Response message")
    event_id: Optional[str] = Field(None, description="Event ID if provided")


class WebhookRetryInfo(BaseModel):
    """Schema for webhook retry information."""
    
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=5, description="Maximum retry attempts")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry time")
    last_error: Optional[str] = Field(None, description="Last error message") 