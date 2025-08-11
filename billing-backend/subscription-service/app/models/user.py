from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Mapped
from typing import List, Optional

from .base import BaseModel


class User(BaseModel):
    """User model representing application users."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    email: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = Column(String(255), nullable=True)  # For authentication
    first_name: Mapped[str] = Column(String(100), nullable=True)
    last_name: Mapped[str] = Column(String(100), nullable=True)
    
    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    usage_records: Mapped[List["UserUsage"]] = relationship(
        "UserUsage", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email
    
    @property
    def active_subscription(self) -> "Subscription":
        """Get user's active subscription."""
        for subscription in self.subscriptions:
            if subscription.status in ["active", "trial"]:
                return subscription
        return None 