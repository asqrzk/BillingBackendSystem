from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped

from .base import Base


class PaymentWebhookRequest(Base):
    """Model for tracking webhook requests from payment service (aligned with DB schema: no updated_at)."""
    
    __tablename__ = "payment_webhook_requests"
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = Column(JSONB, nullable=False)
    processed: Mapped[bool] = Column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    retry_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    created_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    
    def __repr__(self) -> str:
        return f"<PaymentWebhookRequest(id={self.id}, event_id='{self.event_id}', processed={self.processed})>"
    
    @property
    def is_processed(self) -> bool:
        return self.processed
    
    @property
    def transaction_id(self) -> Optional[str]:
        return (self.payload or {}).get("transaction_id")
    
    @property
    def subscription_id(self) -> Optional[str]:
        return (self.payload or {}).get("subscription_id")
    
    @property
    def payment_status(self) -> Optional[str]:
        return (self.payload or {}).get("status")
    
    @property
    def amount(self) -> float:
        return float((self.payload or {}).get("amount", 0.0))
    
    def mark_processed(self):
        self.processed = True
        self.processed_at = datetime.utcnow()
    
    def add_error(self, error_message: str):
        self.error_message = error_message
        self.retry_count = (self.retry_count or 0) + 1 