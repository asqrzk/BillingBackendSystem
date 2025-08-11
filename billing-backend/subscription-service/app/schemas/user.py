from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from .common import BaseResponse


class UserBase(BaseModel):
    """Base user schema."""
    
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a user."""
    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class UserResponse(BaseResponse):
    """Schema for user response."""
    
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, user):
        """Create response from ORM object."""
        return cls(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            created_at=user.created_at,
            updated_at=user.updated_at
        ) 