from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped
from typing import Dict, Any, Optional
import uuid

from .base import BaseModel


class GatewayWebhookRequest(BaseModel):
    """Model for tracking webhook requests from payment gateway."""
    
    __tablename__ = "gateway_webhook_requests"
    __table_args__ = (
        UniqueConstraint('transaction_id', name='_gateway_webhook_transaction_uc'),
    )
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), 
        nullable=False, 
        index=True
    )
    payload: Mapped[Dict[str, Any]] = Column(JSONB, nullable=False)
    processed: Mapped[bool] = Column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<GatewayWebhookRequest(id={self.id}, transaction_id={self.transaction_id}, processed={self.processed})>"
    
    @property
    def is_processed(self) -> bool:
        """Check if webhook has been processed."""
        return self.processed
    
    @property
    def gateway_event_type(self) -> str:
        """Get gateway event type from payload."""
        return self.payload.get("event_type", "unknown")
    
    @property
    def gateway_reference(self) -> str:
        """Get gateway reference from payload."""
        return self.payload.get("gateway_reference")
    
    @property
    def payment_status(self) -> str:
        """Get payment status from payload."""
        return self.payload.get("status")
    
    @property
    def amount(self) -> float:
        """Get payment amount from payload."""
        return self.payload.get("amount", 0.0)
    
    def mark_processed(self):
        """Mark webhook as processed."""
        self.processed = True
        self.processed_at = datetime.utcnow()
    
    def get_payload_field(self, field: str, default: Any = None) -> Any:
        """Get field from payload."""
        return self.payload.get(field, default) 