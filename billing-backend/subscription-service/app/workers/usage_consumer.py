import asyncio
import json
from typing import Dict, Any

from .celery_app import celery_app
from .base_consumer import BaseConsumer
from app.core.database import AsyncSessionLocal
from app.services.usage_service import UsageService
from app.core.logging import get_logger

logger = get_logger(__name__)


class UsageConsumer(BaseConsumer):
    """Consumer for usage-related tasks."""
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Process usage-related messages."""
        try:
            async with AsyncSessionLocal() as session:
                service = UsageService(session)
                
                # Handle usage sync
                if "user_id" in message and "feature_name" in message:
                    await service.sync_usage_to_database(
                        message["user_id"],
                        message["feature_name"],
                        message.get("delta", 1),
                        message.get("reset_at")
                    )
                    return True
                
                logger.warning(f"Unknown usage message type: {message}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing usage message: {e}")
            return False


@celery_app.task(bind=True, max_retries=3)
def process_usage_sync(self, message_data: str):
    """Process usage sync queue messages."""
    try:
        message = json.loads(message_data)
        logger.info(f"Processing usage sync: {message}")
        
        user_id = message.get("user_id")
        feature_name = message.get("feature_name")
        delta = message.get("delta", 1)
        
        logger.info(f"Usage sync for user {user_id}, feature {feature_name}, delta {delta}")
        
        # Simulate processing - in real implementation this would sync Redis to DB
        return {"status": "synced", "user_id": user_id, "feature": feature_name}
        
    except Exception as e:
        logger.error(f"Usage sync failed: {e}")
        raise self.retry(countdown=60, exc=e)


@celery_app.task(bind=True)
def sync_usage_to_database():
    """Scheduled task to sync Redis usage data to database."""
    try:
        async def run_sync():
            async with AsyncSessionLocal() as session:
                service = UsageService(session)
                await service.sync_usage_schedule()
        
        asyncio.run(run_sync())
        logger.info("Usage sync to database completed")
        
    except Exception as e:
        logger.error(f"Usage sync to database failed: {e}")
        raise


@celery_app.task(bind=True)
def reset_expired_usage():
    """Scheduled task to reset expired usage counters."""
    try:
        async def run_reset():
            async with AsyncSessionLocal() as session:
                service = UsageService(session)
                await service.reset_expired_usage_schedule()
        
        asyncio.run(run_reset())
        logger.info("Expired usage reset completed")
        
    except Exception as e:
        logger.error(f"Expired usage reset failed: {e}")
        raise 