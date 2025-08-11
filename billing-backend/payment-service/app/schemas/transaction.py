from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, validator
import re

from .common import BaseResponse


class TransactionBase(BaseModel):
    """Base transaction schema."""
    
    amount: Decimal = Field(..., ge=0.01, le=999999.99, description="Transaction amount")
    currency: str = Field(default="AED", max_length=3, pattern=r"^[A-Z]{3}$")
    subscription_id: Optional[UUID] = None
    gateway_reference: Optional[str] = Field(None, max_length=100)
    

class TransactionCreate(TransactionBase):
    """Schema for creating a transaction."""
    pass


class PaymentRequest(BaseModel):
    """Schema for payment processing request."""
    
    amount: Decimal = Field(..., ge=0.01, le=999999.99, description="Payment amount (0.01 - 999999.99)")
    currency: str = Field(default="AED", max_length=3, pattern=r"^[A-Z]{3}$", description="3-letter currency code")
    card_number: str = Field(..., min_length=13, max_length=19, description="Card number (13-19 digits)")
    card_expiry: str = Field(..., pattern=r"^\d{2}/\d{2}$", description="Card expiry (MM/YY format)")
    card_cvv: str = Field(..., min_length=3, max_length=4, pattern=r"^\d{3,4}$", description="Card CVV (3-4 digits)")
    cardholder_name: str = Field(..., min_length=2, max_length=100, description="Cardholder name (2-100 characters)")
    trial: bool = Field(default=False, description="Is this a trial payment")
    renewal: bool = Field(default=False, description="Is this a renewal payment")
    
    @validator('card_number')
    def validate_card_number(cls, v):
        """Validate card number format."""
        # Remove spaces and hyphens
        card_clean = re.sub(r'[\s\-]', '', v)
        
        # Check if all digits
        if not card_clean.isdigit():
            raise ValueError('Card number must contain only digits')
        
        # Basic length check
        if len(card_clean) < 13 or len(card_clean) > 19:
            raise ValueError('Card number must be between 13 and 19 digits')
        
        # Basic Luhn algorithm check
        def luhn_check(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10 == 0
        
        if not luhn_check(card_clean):
            raise ValueError('Invalid card number (failed Luhn check)')
        
        return card_clean
    
    @validator('card_expiry')
    def validate_card_expiry(cls, v):
        """Validate card expiry date."""
        from datetime import datetime
        
        try:
            month, year = v.split('/')
            month = int(month)
            year = int(year) + 2000  # Convert YY to YYYY
            
            if month < 1 or month > 12:
                raise ValueError('Invalid expiry month (must be 01-12)')
            
            # Check if card has expired
            current_date = datetime.now()
            if year < current_date.year or (year == current_date.year and month < current_date.month):
                raise ValueError('Card has expired')
            
        except (ValueError, AttributeError):
            raise ValueError('Invalid expiry format (use MM/YY)')
        
        return v
    
    @validator('cardholder_name')
    def validate_cardholder_name(cls, v):
        """Validate cardholder name."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError('Cardholder name must be at least 2 characters')
        
        # Allow letters, spaces, hyphens, apostrophes, and periods
        if not re.match(r"^[a-zA-Z\s\-'.]+$", v):
            raise ValueError('Cardholder name contains invalid characters')
        
        return v
    
    @validator('amount')
    def validate_amount_business_rules(cls, v):
        """Validate business rules for payment amounts."""
        if v <= 0:
            raise ValueError('Payment amount must be greater than 0')
        
        # Set reasonable limits
        if v > Decimal('999999.99'):
            raise ValueError('Payment amount too large (maximum: 999,999.99)')
        
        if v < Decimal('0.01'):
            raise ValueError('Payment amount too small (minimum: 0.01)')
        
        return v


class TransactionResponse(BaseResponse):
    """Schema for transaction response."""
    
    id: UUID
    subscription_id: Optional[UUID]
    amount: Decimal
    currency: str
    status: str
    gateway_reference: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime


class PaymentResponse(BaseResponse):
    """Schema for payment processing response."""
    
    transaction_id: UUID
    status: str
    amount: Decimal
    currency: str
    gateway_reference: Optional[str]
    processed_at: datetime
    message: str


class RefundRequest(BaseModel):
    """Schema for refund request."""
    
    reason: Optional[str] = Field(None, max_length=500, description="Reason for refund")
    amount: Optional[Decimal] = Field(None, ge=0.01, le=999999.99, description="Partial refund amount")
    
    @validator('reason')
    def validate_reason(cls, v):
        """Validate refund reason."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class RefundResponse(BaseResponse):
    """Schema for refund response."""
    
    refund_id: UUID
    original_transaction_id: UUID
    amount: Decimal
    currency: str
    status: str
    reason: Optional[str]
    processed_at: datetime 