from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, Optional
import uuid

from .base import BaseModel


class Subscription(BaseModel):
    """Subscription model representing user subscriptions to plans."""
    
    __tablename__ = "subscriptions"
    
    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[int] = Column(Integer, ForeignKey("plans.id"), nullable=False, index=True)
    status: Mapped[str] = Column(String(20), nullable=False, index=True)  # pending, active, trial, past_due, cancelled, revoked
    start_date: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    canceled_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")
    events: Mapped[List["SubscriptionEvent"]] = relationship(
        "SubscriptionEvent", 
        back_populates="subscription", 
        cascade="all, delete-orphan",
        order_by="SubscriptionEvent.created_at.desc()"
    )
    
    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status='{self.status}')>"
    
    def _as_aware_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize datetimes to timezone-aware UTC for safe comparisons."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        now_utc = datetime.now(timezone.utc)
        end = self._as_aware_utc(self.end_date)
        return self.status in ["active", "trial"] and end > now_utc
    
    @property
    def is_expired(self) -> bool:
        """Check if subscription has expired."""
        now_utc = datetime.now(timezone.utc)
        end = self._as_aware_utc(self.end_date)
        return end <= now_utc
    
    @property
    def days_remaining(self) -> int:
        """Get number of days remaining in current billing period."""
        if self.is_expired:
            return 0
        now_utc = datetime.now(timezone.utc)
        end = self._as_aware_utc(self.end_date)
        delta = end - now_utc
        return max(0, delta.days)
    
    @property
    def is_trial(self) -> bool:
        """Check if this is a trial subscription."""
        return self.status == "trial"
    
    @property
    def is_past_due(self) -> bool:
        """Check if subscription is past due."""
        return self.status == "past_due"
    
    @property
    def is_cancelled(self) -> bool:
        """Check if subscription is cancelled."""
        return self.status == "cancelled"
    
    def extend_subscription(self, months: int = 1):
        """Extend subscription by specified months."""
        if self.plan.billing_cycle == "yearly":
            self.end_date = self.end_date + timedelta(days=365)
        else:  # monthly
            # Add approximately one month (30 days)
            self.end_date = self.end_date + timedelta(days=30 * months)
    
    def calculate_prorated_amount(self, new_price: float) -> float:
        """Calculate prorated amount for plan changes."""
        if not self.is_active:
            return 0.0
        
        start = self._as_aware_utc(self.start_date)
        end = self._as_aware_utc(self.end_date)
        total_days = (end - start).days
        remaining_days = self.days_remaining
        current_price = float(self.plan.price)
        
        if total_days <= 0:
            return 0.0
        
        # Calculate prorated difference
        price_difference = new_price - current_price
        prorated_amount = (price_difference * remaining_days) / total_days
        
        return max(0.0, prorated_amount) 