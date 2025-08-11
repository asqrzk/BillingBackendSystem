from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped
from typing import Optional

from .base import BaseModel


class UserUsage(BaseModel):
    """Model for tracking user feature usage."""
    
    __tablename__ = "user_usage"
    __table_args__ = (
        UniqueConstraint('user_id', 'feature_name', name='_user_feature_uc'),
    )
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feature_name: Mapped[str] = Column(String(50), nullable=False, index=True)
    usage_count: Mapped[int] = Column(Integer, default=0, nullable=False)
    reset_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="usage_records")
    
    def __repr__(self) -> str:
        return f"<UserUsage(id={self.id}, user_id={self.user_id}, feature='{self.feature_name}', count={self.usage_count})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if usage period has expired."""
        return self.reset_at <= datetime.utcnow()
    
    def reset_usage(self, new_reset_at: datetime):
        """Reset usage count and update reset time."""
        self.usage_count = 0
        self.reset_at = new_reset_at
    
    def increment_usage(self, delta: int = 1):
        """Increment usage count."""
        self.usage_count += delta
    
    def check_limit(self, limit: int) -> bool:
        """Check if usage is within limit."""
        return self.usage_count < limit
    
    def get_remaining_usage(self, limit: int) -> int:
        """Get remaining usage count."""
        return max(0, limit - self.usage_count) 