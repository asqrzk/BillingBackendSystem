from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import Dict, Any, Optional
import uuid

from .base import BaseModel


class SubscriptionEvent(BaseModel):
    """Model for tracking subscription events and changes."""
    
    __tablename__ = "subscription_events"
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    subscription_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), 
        ForeignKey("subscriptions.id"), 
        nullable=False, 
        index=True
    )
    event_type: Mapped[str] = Column(String(50), nullable=False, index=True)
    transaction_id: Mapped[Optional[uuid.UUID]] = Column(UUID(as_uuid=True), nullable=True)
    old_plan_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("plans.id"),
        nullable=True
    )
    new_plan_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("plans.id"),
        nullable=True
    )
    effective_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    event_metadata: Mapped[Dict[str, Any]] = Column("metadata", JSONB, default=dict, nullable=False)
    
    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="events")
    old_plan: Mapped[Optional["Plan"]] = relationship("Plan", foreign_keys=[old_plan_id])
    new_plan: Mapped[Optional["Plan"]] = relationship("Plan", foreign_keys=[new_plan_id])
    
    def __repr__(self) -> str:
        return f"<SubscriptionEvent(id={self.id}, type='{self.event_type}', subscription_id={self.subscription_id})>"
    
    @property
    def is_plan_change(self) -> bool:
        """Check if this event represents a plan change."""
        return self.event_type in ["plan_change_scheduled", "plan_changed"]
    
    @property
    def is_payment_related(self) -> bool:
        """Check if this event is payment related."""
        return self.event_type in ["payment_success", "payment_failed", "payment_retry"]
    
    @property
    def is_lifecycle_event(self) -> bool:
        """Check if this is a subscription lifecycle event."""
        return self.event_type in ["created", "activated", "cancelled", "expired", "renewed"] 