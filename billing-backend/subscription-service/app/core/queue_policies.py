from dataclasses import dataclass
from typing import Dict
from app.core.config import settings


@dataclass
class QueuePolicy:
    max_retries: int
    base_delay_seconds: int
    backoff_multiplier: float
    max_delay_seconds: int
    jitter_seconds: int
    lock_ttl_seconds: int
    visibility_timeout_seconds: int


DEFAULT_POLICY = QueuePolicy(
    max_retries=5,
    base_delay_seconds=60,
    backoff_multiplier=2.0,
    max_delay_seconds=3600,
    jitter_seconds=10,
    lock_ttl_seconds=180,
    visibility_timeout_seconds=300,
)


QUEUE_POLICIES: Dict[str, QueuePolicy] = {
    "q:sub:payment_initiation": DEFAULT_POLICY,
    "q:sub:trial_payment": QueuePolicy(
        max_retries=3,
        base_delay_seconds=60,
        backoff_multiplier=2.0,
        max_delay_seconds=600,
        jitter_seconds=5,
        lock_ttl_seconds=120,
        visibility_timeout_seconds=240,
    ),
    "q:sub:plan_change": DEFAULT_POLICY,
    "q:sub:usage_sync": DEFAULT_POLICY,
} 