import asyncio
import json
from typing import Dict, Any

from .celery_app import celery_app
from .base_consumer import BaseConsumer
from app.core.database import AsyncSessionLocal
from app.services.webhook_service import WebhookService
from app.core.logging import get_logger

logger = get_logger(__name__)


class WebhookConsumer(BaseConsumer):
    """Consumer for webhook-related tasks."""
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Process webhook-related messages."""
        try:
            async with AsyncSessionLocal() as session:
                service = WebhookService(session)
                
                # Handle webhook processing
                if "event_id" in message:
                    event_id = message["event_id"]
                    payload = message
                    success = await service.process_webhook_event(event_id, payload)
                    return success
                
                logger.warning(f"Unknown webhook message type: {message}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            return False


@celery_app.task(bind=True, max_retries=5)
def process_webhook_processing(self, message_data: str):
    """Process webhook processing queue messages."""
    try:
        message = json.loads(message_data)
        logger.info(f"Processing webhook: {message}")
        
        event_id = message.get("event_id")
        payload = message
        
        # Run async function in sync context
        async def run_processing():
            async with AsyncSessionLocal() as session:
                service = WebhookService(session)
                return await service.process_webhook_event(event_id, payload)
        
        success = asyncio.run(run_processing())
        
        if success:
            logger.info(f"Webhook processing completed for event {event_id}")
            return {"status": "processed", "event_id": event_id}
        else:
            raise Exception("Webhook processing failed")
            
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise self.retry(countdown=120, exc=e)


@celery_app.task(bind=True, max_retries=3)
def retry_failed_webhooks(self):
    """Scheduled task to retry failed webhook processing."""
    try:
        async def run_retry():
            async with AsyncSessionLocal() as session:
                service = WebhookService(session)
                # Get failed webhooks and retry them
                # Implementation depends on webhook service design
                logger.info("Checking for failed webhooks to retry")
        
        asyncio.run(run_retry())
        logger.info("Failed webhook retry check completed")
        
    except Exception as e:
        logger.error(f"Failed webhook retry failed: {e}")
        raise 