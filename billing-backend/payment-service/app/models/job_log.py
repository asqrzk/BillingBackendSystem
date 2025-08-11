from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped

from app.core.database import Base


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    service: Mapped[str] = Column(String(50), nullable=False)  # e.g., payment|subscription
    queue: Mapped[str] = Column(String(100), index=True, nullable=False)
    message_id: Mapped[Optional[str]] = Column(String(100), index=True)
    correlation_id: Mapped[Optional[str]] = Column(String(100), index=True)
    idempotency_key: Mapped[Optional[str]] = Column(String(100), index=True)
    action: Mapped[Optional[str]] = Column(String(50))
    status: Mapped[str] = Column(String(20), index=True)  # received|processing|success|retry|failed|dead
    attempts: Mapped[int] = Column(Integer, default=0)
    last_error: Mapped[Optional[Text]] = Column(Text)
    next_retry_at: Mapped[Optional[DateTime]] = Column(DateTime)
    created_at: Mapped[DateTime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[DateTime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False) 