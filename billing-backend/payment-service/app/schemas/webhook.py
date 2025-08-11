from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .common import BaseResponse


class WebhookOutboundPayload(BaseModel):
    """Schema for outbound webhook payload to subscription service."""
    
    event_id: str = Field(..., description="Unique event identifier")
    transaction_id: UUID = Field(..., description="Transaction ID")
    subscription_id: UUID = Field(..., description="Subscription ID")
    status: str = Field(..., description="Payment status")
    amount: float = Field(..., description="Payment amount")
    currency: str = Field(default="AED", description="Payment currency")
    occurred_at: datetime = Field(..., description="When the event occurred")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WebhookDeliveryResponse(BaseResponse):
    """Schema for webhook delivery response."""
    
    webhook_id: int = Field(..., description="Webhook request ID")
    transaction_id: UUID = Field(..., description="Transaction ID")
    url: str = Field(..., description="Webhook URL")
    status: str = Field(..., description="Delivery status")
    response_code: Optional[int] = Field(None, description="HTTP response code")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    can_retry: bool = Field(..., description="Whether webhook can be retried")
    created_at: datetime = Field(..., description="When webhook was created")
    completed_at: Optional[datetime] = Field(None, description="When webhook was completed")
    
    @classmethod
    def from_orm(cls, webhook_request):
        """Create response from ORM object."""
        return cls(
            webhook_id=webhook_request.id,
            transaction_id=webhook_request.transaction_id,
            url=webhook_request.url,
            status="completed" if webhook_request.is_completed else "pending" if webhook_request.is_pending else "failed",
            response_code=webhook_request.response_code,
            retry_count=webhook_request.retry_count,
            can_retry=webhook_request.can_retry,
            created_at=webhook_request.created_at,
            completed_at=webhook_request.completed_at
        )


class WebhookRetryInfo(BaseModel):
    """Schema for webhook retry information."""
    
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=5, description="Maximum retry attempts")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry time")
    last_error: Optional[str] = Field(None, description="Last error message") 