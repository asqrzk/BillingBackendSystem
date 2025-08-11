from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.payment_webhook_request import PaymentWebhookRequest
from .base_repository import BaseRepository


class WebhookRepository(BaseRepository[PaymentWebhookRequest]):
    """Repository for PaymentWebhookRequest operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(PaymentWebhookRequest, session)
    
    async def get_by_event_id(self, event_id: str) -> Optional[PaymentWebhookRequest]:
        """Get webhook request by event ID."""
        return await self.get_by_field("event_id", event_id)
    
    async def get_unprocessed_webhooks(self) -> List[PaymentWebhookRequest]:
        """Get all unprocessed webhook requests."""
        return await self.get_all(filters={"processed": False})
    
    async def get_failed_webhooks(self, max_retries: int = 5) -> List[PaymentWebhookRequest]:
        """Get webhook requests that have failed processing."""
        try:
            query = select(PaymentWebhookRequest).where(
                PaymentWebhookRequest.processed == False,
                PaymentWebhookRequest.retry_count >= max_retries
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting failed webhooks: {e}")
            raise
    
    async def mark_processed(self, webhook_id: int) -> Optional[PaymentWebhookRequest]:
        """Mark webhook as processed."""
        return await self.update(webhook_id, {
            "processed": True,
            "processed_at": datetime.utcnow()
        })
    
    async def increment_retry_count(self, webhook_id: int, error_message: str = None) -> Optional[PaymentWebhookRequest]:
        """Increment retry count and optionally set error message."""
        webhook = await self.get_by_id(webhook_id)
        if not webhook:
            return None
        
        update_data = {"retry_count": webhook.retry_count + 1}
        if error_message:
            update_data["error_message"] = error_message
        
        return await self.update(webhook_id, update_data)
    
    async def create_webhook_request(self, event_id: str, payload: dict) -> PaymentWebhookRequest:
        """Create a new webhook request."""
        webhook_data = {
            "event_id": event_id,
            "payload": payload,
            "processed": False,
            "retry_count": 0
        }
        
        return await self.create(webhook_data) 