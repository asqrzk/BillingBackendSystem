from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from .common import BaseResponse
from .user import UserResponse
from .plan import PlanResponse


class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    
    plan_id: int
    status: str = Field(..., pattern="^(pending|active|trial|past_due|cancelled|revoked)$")


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription."""
    pass


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""
    
    plan_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(pending|active|trial|past_due|cancelled|revoked)$")


class SubscriptionCreateRequest(BaseModel):
    """Schema for subscription creation request."""
    
    plan_id: int = Field(..., description="Plan ID")


class TrialSubscriptionRequest(BaseModel):
    """Schema for trial subscription creation request."""
    
    trial_plan_id: int = Field(..., description="Trial plan ID")


class PlanChangeRequest(BaseModel):
    """Schema for plan change request."""
    
    new_plan_id: int = Field(..., description="New plan ID")


class SubscriptionResponse(BaseResponse):
    """Schema for subscription response."""
    
    id: UUID
    user_id: int
    plan_id: int
    status: str
    start_date: datetime
    end_date: datetime
    canceled_at: Optional[datetime]
    is_active: bool
    is_expired: bool
    is_trial: bool
    days_remaining: int
    created_at: datetime
    updated_at: datetime
    
    # Optional embedded objects
    user: Optional[UserResponse] = None
    plan: Optional[PlanResponse] = None
    
    @classmethod
    def from_orm(cls, subscription, include_user: bool = False, include_plan: bool = False):
        """Create response from ORM object."""
        data = cls(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_id=subscription.plan_id,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            canceled_at=subscription.canceled_at,
            is_active=subscription.is_active,
            is_expired=subscription.is_expired,
            is_trial=subscription.is_trial,
            days_remaining=subscription.days_remaining,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at
        )
        
        if include_user and subscription.user:
            data.user = UserResponse.from_orm(subscription.user)
        
        if include_plan and subscription.plan:
            data.plan = PlanResponse.from_orm(subscription.plan)
        
        return data


class SubscriptionListResponse(BaseResponse):
    """Schema for subscription list response."""
    
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    limit: int 