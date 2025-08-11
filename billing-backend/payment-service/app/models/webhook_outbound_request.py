from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped
from typing import Dict, Any, Optional
import uuid

from .base import BaseModel


class WebhookOutboundRequest(BaseModel):
    """Model for tracking outbound webhook requests to subscription service."""
    
    __tablename__ = "webhook_outbound_requests"
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), 
        nullable=False, 
        index=True
    )
    url: Mapped[str] = Column(String(500), nullable=False)
    payload: Mapped[Dict[str, Any]] = Column(JSONB, nullable=False)
    response_code: Mapped[Optional[int]] = Column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = Column(Text, nullable=True)
    retry_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<WebhookOutboundRequest(id={self.id}, transaction_id={self.transaction_id}, retry_count={self.retry_count})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if webhook request was completed successfully."""
        return self.completed_at is not None and self.response_code == 200
    
    @property
    def is_failed(self) -> bool:
        """Check if webhook request failed."""
        return (
            self.response_code is not None and 
            self.response_code >= 400
        )
    
    @property
    def is_pending(self) -> bool:
        """Check if webhook request is still pending."""
        return self.response_code is None
    
    @property
    def can_retry(self) -> bool:
        """Check if webhook can be retried."""
        return self.retry_count < 5 and not self.is_completed
    
    @property
    def event_id(self) -> str:
        """Get event ID from payload."""
        return self.payload.get("event_id", str(self.id))
    
    @property
    def subscription_id(self) -> str:
        """Get subscription ID from payload."""
        return self.payload.get("subscription_id")
    
    def mark_completed(self, response_code: int, response_body: str = None):
        """Mark webhook request as completed."""
        self.response_code = response_code
        self.response_body = response_body
        if response_code == 200:
            self.completed_at = datetime.utcnow()
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1
    
    def add_payload_field(self, key: str, value: Any):
        """Add field to payload."""
        if self.payload is None:
            self.payload = {}
        self.payload[key] = value 