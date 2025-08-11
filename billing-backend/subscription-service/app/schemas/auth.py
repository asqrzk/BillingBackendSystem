from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re


class LoginRequest(BaseModel):
    """Schema for user login request."""
    
    email: EmailStr
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: int
    email: str


class RegisterRequest(BaseModel):
    """Schema for user registration request."""
    
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100, description="Password (8-100 characters)")
    first_name: Optional[str] = Field(None, max_length=50, pattern=r"^[a-zA-Z\s'-]+$")
    last_name: Optional[str] = Field(None, max_length=50, pattern=r"^[a-zA-Z\s'-]+$")
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        
        return v
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        """Validate name fields."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 2:
                raise ValueError('Name must be at least 2 characters long')
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""
    
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password (8-100 characters)")
    
    @validator('new_password')
    def validate_new_password_strength(cls, v):
        """Validate new password strength requirements."""
        if len(v) < 8:
            raise ValueError('New password must be at least 8 characters long')
        
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('New password must contain at least one letter')
        
        if not re.search(r'\d', v):
            raise ValueError('New password must contain at least one number')
        
        return v 