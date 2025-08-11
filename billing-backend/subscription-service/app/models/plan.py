from sqlalchemy import Column, String, DECIMAL, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import List, Dict, Any

from .base import BaseModel


class Plan(BaseModel):
    """Plan model representing subscription plans."""
    
    __tablename__ = "plans"
    
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[str] = Column(Text, nullable=True)
    price: Mapped[float] = Column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = Column(String(3), default="AED", nullable=False)
    billing_cycle: Mapped[str] = Column(String(20), nullable=False)  # monthly, yearly
    features: Mapped[Dict[str, Any]] = Column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", 
        back_populates="plan"
    )
    
    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name='{self.name}', price={self.price})>"
    
    @property
    def is_trial_plan(self) -> bool:
        """Check if this is a trial plan based on features metadata."""
        if not isinstance(self.features, dict):
            return False
        
        # Check if trial is explicitly set to true (boolean)
        trial_flag = self.features.get("trial")
        return trial_flag is True
    
    @property
    def trial_period_days(self) -> float:
        """Get trial period in days from metadata."""
        if not isinstance(self.features, dict):
            return 0.0
            
        # If it's a trial plan, look for period_days, otherwise return 0
        if self.is_trial_plan:
            return float(self.features.get("period_days", 14))  # Default to 14 days if not specified
        
        return 0.0
    
    @property
    def trial_renewal_plan_id(self) -> str:
        """Get the plan ID for trial renewal from metadata."""
        if not isinstance(self.features, dict):
            return None
            
        # Only look for renewal_plan if this is a trial plan
        if self.is_trial_plan:
            renewal_plan = self.features.get("renewal_plan")
            if renewal_plan is not None:
                return str(renewal_plan)
        
        return None
    
    @property
    def trial_renewal_plan_name(self) -> str:
        """Get the plan name for trial renewal from metadata."""
        # This simplified format uses IDs only, not names
        # Keeping this method for backward compatibility
        return None
    
    def get_feature_limit(self, feature_name: str) -> int:
        """Get limit for a specific feature."""
        limits = self.features.get("limits", {})
        return limits.get(feature_name, 0)
    
    def get_feature_limits(self) -> Dict[str, int]:
        """Get all feature limits for this plan."""
        return self.features.get("limits", {})
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if plan has a specific feature."""
        plan_features = self.features.get("features", {})
        if isinstance(plan_features, dict):
            return plan_features.get(feature_name, False)
        return feature_name in plan_features 