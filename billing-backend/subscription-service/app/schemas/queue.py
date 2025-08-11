from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class QueueMessageEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attempts: int = 0
    max_attempts: Optional[int] = None
    payload: Dict[str, Any]


class DeliveryResult(BaseModel):
    status: str  # success|retry|failed|no_message
    queue: str
    message_id: Optional[str] = None
    attempts: int = 0
    max_attempts: Optional[int] = None
    next_retry_at: Optional[datetime] = None
    error: Optional[str] = None 