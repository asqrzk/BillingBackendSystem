import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.redis_client import redis_client


async def log_job_event(
    queue: str,
    action: str,
    status: str,
    message_id: Optional[str] = None,
    attempts: int = 0,
    info: Optional[Dict[str, Any]] = None,
) -> None:
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "queue": queue,
        "action": action,
        "status": status,
        "message_id": message_id,
        "attempts": attempts,
        "info": info or {},
    }
    try:
        if not redis_client.client:
            await redis_client.connect()
        await redis_client.client.lpush("q:log:jobs", json.dumps(event, default=str))
    except Exception:
        # Best-effort logging; swallow errors to avoid impacting main flow
        return 