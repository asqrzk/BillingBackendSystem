from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .common import BaseResponse


class PlanBase(BaseModel):
    """Base plan schema."""
    
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    currency: str = Field(default="AED", max_length=3)
    billing_cycle: str = Field(..., pattern="^(monthly|yearly)$")
    features: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class PlanCreate(PlanBase):
    """Schema for creating a plan."""
    pass


class PlanUpdate(BaseModel):
    """Schema for updating a plan."""
    
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    billing_cycle: Optional[str] = Field(None, pattern="^(monthly|yearly)$")
    features: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PlanResponse(BaseResponse):
    """Schema for plan response."""
    
    id: int
    name: str
    description: Optional[str]
    price: float
    currency: str
    billing_cycle: str
    features: Dict[str, Any]
    is_active: bool
    is_trial_plan: bool
    trial_period_days: float
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, plan):
        """Create response from ORM object."""
        return cls(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            price=float(plan.price),
            currency=plan.currency,
            billing_cycle=plan.billing_cycle,
            features=plan.features,
            is_active=plan.is_active,
            is_trial_plan=plan.is_trial_plan,
            trial_period_days=plan.trial_period_days,
            created_at=plan.created_at,
            updated_at=plan.updated_at
        ) 