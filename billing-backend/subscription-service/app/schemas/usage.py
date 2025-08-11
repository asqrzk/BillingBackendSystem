from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .common import BaseResponse


class UsageRequest(BaseModel):
    """Schema for feature usage request."""
    
    feature_name: str = Field(..., max_length=50, description="Feature name")
    delta: int = Field(default=1, ge=1, description="Usage increment")


class UsageCheckResponse(BaseResponse):
    """Schema for usage check response."""
    
    success: bool
    current_usage: int
    limit: int
    remaining: int
    reset_at: Optional[datetime] = None
    
    @property
    def usage_percentage(self) -> float:
        """Calculate usage percentage."""
        if self.limit <= 0:
            return 0.0
        return (self.current_usage / self.limit) * 100
    
    @property
    def is_limit_exceeded(self) -> bool:
        """Check if usage limit is exceeded."""
        return self.current_usage >= self.limit


class UsageResponse(BaseResponse):
    """Schema for usage response."""
    
    user_id: int
    feature_name: str
    usage_count: int
    limit: int
    remaining: int
    reset_at: datetime
    last_updated: datetime
    
    @classmethod
    def from_orm(cls, usage, limit: int):
        """Create response from ORM object."""
        return cls(
            user_id=usage.user_id,
            feature_name=usage.feature_name,
            usage_count=usage.usage_count,
            limit=limit,
            remaining=max(0, limit - usage.usage_count),
            reset_at=usage.reset_at,
            last_updated=usage.updated_at
        )


class UsageStatsResponse(BaseResponse):
    """Schema for usage statistics response."""
    
    total_usage: int
    total_limit: int
    features: dict
    period_start: datetime
    period_end: datetime 