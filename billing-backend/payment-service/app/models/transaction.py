from sqlalchemy import Column, String, DECIMAL, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped
from typing import Dict, Any, Optional
import uuid

from .base import BaseModel


class Transaction(BaseModel):
    """Transaction model representing payment transactions."""
    
    __tablename__ = "transactions"
    
    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    subscription_id: Mapped[Optional[uuid.UUID]] = Column(
        UUID(as_uuid=True), 
        nullable=True,
        index=True
    )
    amount: Mapped[float] = Column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = Column(String(3), default="AED", nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False, index=True)  # pending, processing, success, failed, refund_initiated, refund_complete, refund_error
    gateway_reference: Mapped[Optional[str]] = Column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    transaction_metadata: Mapped[Dict[str, Any]] = Column("metadata", JSONB, default=dict, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, amount={self.amount}, status='{self.status}')>"
    
    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status == "pending"
    
    @property
    def is_processing(self) -> bool:
        """Check if transaction is processing."""
        return self.status == "processing"
    
    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == "success"
    
    @property
    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.status == "failed"
    
    @property
    def is_refund(self) -> bool:
        """Check if this is a refund transaction."""
        return self.status in ["refund_initiated", "refund_complete", "refund_error"]
    
    @property
    def is_trial_transaction(self) -> bool:
        """Check if this is a trial transaction."""
        return self.transaction_metadata.get("trial", False)
    
    @property
    def is_renewal_transaction(self) -> bool:
        """Check if this is a renewal transaction."""
        return self.transaction_metadata.get("renewal", False)
    
    def update_status(self, new_status: str, gateway_reference: str = None, error_message: str = None):
        """Update transaction status and optional gateway reference."""
        self.status = new_status
        if gateway_reference:
            self.gateway_reference = gateway_reference
        if error_message:
            self.error_message = error_message
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to transaction."""
        if self.transaction_metadata is None:
            self.transaction_metadata = {}
        self.transaction_metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        if self.transaction_metadata is None:
            return default
        return self.transaction_metadata.get(key, default) 