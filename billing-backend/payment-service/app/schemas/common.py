from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
from uuid import UUID


# Path Parameter Validation Schemas
class UUIDPath(BaseModel):
    """Path parameter validation for UUID."""
    
    id: UUID = Field(..., description="Valid UUID")


class UserIdPath(BaseModel):
    """Path parameter validation for user ID."""
    
    user_id: int = Field(..., ge=1, description="User ID (positive integer)")


class SubscriptionIdPath(BaseModel):
    """Path parameter validation for subscription ID."""
    
    subscription_id: UUID = Field(..., description="Subscription UUID")


class TransactionIdPath(BaseModel):
    """Path parameter validation for transaction ID."""
    
    transaction_id: UUID = Field(..., description="Transaction UUID")


class PlanIdPath(BaseModel):
    """Path parameter validation for plan ID."""
    
    plan_id: int = Field(..., description="Plan ID")


class WebhookIdPath(BaseModel):
    """Path parameter validation for webhook ID."""
    
    webhook_id: int = Field(..., ge=1, description="Webhook ID (positive integer)")


class BaseResponse(BaseModel):
    """Base response schema with consistent structure."""
    
    success: bool = True
    message: Optional[str] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            # Add custom encoders if needed
        }


class SuccessResponse(BaseResponse):
    """Standard success response."""
    
    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(BaseResponse):
    """Standard error response."""
    
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Query parameters for pagination."""
    
    page: int = Field(default=1, ge=1, le=1000, description="Page number (1-1000)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (1-100)")
    
    @validator('page')
    def validate_page(cls, v):
        """Validate page number."""
        if v < 1:
            raise ValueError('Page number must be at least 1')
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        """Validate page size."""
        if v < 1:
            raise ValueError('Limit must be at least 1')
        if v > 100:
            raise ValueError('Limit cannot exceed 100')
        return v
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.limit


class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


class TransactionSortBy(str, Enum):
    """Transaction sorting options."""
    CREATED_AT = "created_at"
    AMOUNT = "amount"
    STATUS = "status"
    PROCESSED_AT = "processed_at"


class TransactionFilterParams(BaseModel):
    """Query parameters for filtering transactions."""
    
    status: Optional[str] = Field(None, pattern=r"^(pending|processing|successful|failed|refunded)$")
    subscription_id: Optional[str] = Field(None, description="Filter by subscription ID")
    amount_min: Optional[float] = Field(None, ge=0, description="Minimum amount")
    amount_max: Optional[float] = Field(None, ge=0, description="Maximum amount")
    
    # Date range filters
    created_from: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Created date from (YYYY-MM-DD)")
    created_to: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Created date to (YYYY-MM-DD)")
    
    # Sorting
    sort_by: TransactionSortBy = Field(default=TransactionSortBy.CREATED_AT)
    sort_order: SortOrder = Field(default=SortOrder.DESC)
    
    @validator('amount_min', 'amount_max')
    def validate_amounts(cls, v):
        """Validate amount filters."""
        if v is not None and v < 0:
            raise ValueError('Amount must be non-negative')
        return v


class DateRangeParams(BaseModel):
    """Query parameters for date range filtering."""
    
    start_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)")
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format."""
        if v is not None:
            try:
                from datetime import datetime
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return v


class PaginatedResponse(BaseResponse):
    """Response schema for paginated results."""
    
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")
    
    @classmethod
    def create(cls, items: List[Any], total: int, page: int, limit: int, **kwargs):
        """Create paginated response."""
        total_pages = (total + limit - 1) // limit  # Ceiling division
        
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
            **kwargs
        )


class HealthCheckResponse(BaseResponse):
    """Health check response schema."""
    
    status: str = Field(..., pattern=r"^(healthy|unhealthy)$")
    service: str
    version: Optional[str] = None
    environment: Optional[str] = None
    checks: Optional[Dict[str, Any]] = None
    uptime_seconds: Optional[int] = None
    timestamp: Optional[str] = None 