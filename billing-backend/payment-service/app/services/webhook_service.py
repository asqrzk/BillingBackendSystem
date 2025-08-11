from typing import Optional, List
from uuid import UUID

from app.models.webhook_outbound_request import WebhookOutboundRequest
from .base_service import BaseService


class WebhookService(BaseService):
    """Service for webhook delivery operations."""
    
    async def create_outbound_webhook(self, transaction_id: UUID, url: str, payload: dict) -> WebhookOutboundRequest:
        """Create an outbound webhook request."""
        try:
            webhook_data = {
                "transaction_id": transaction_id,
                "url": url,
                "payload": payload,
                "retry_count": 0
            }
            
            webhook = await self.webhook_outbound_repo.create(webhook_data)
            await self.commit()
            
            self.logger.info(
                f"Outbound webhook created",
                webhook_id=webhook.id,
                transaction_id=str(transaction_id),
                url=url
            )
            
            return webhook
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Failed to create outbound webhook: {e}")
            raise
    
    async def get_pending_webhooks(self) -> List[WebhookOutboundRequest]:
        """Get all pending webhook deliveries."""
        return await self.webhook_outbound_repo.get_pending_webhooks()
    
    async def mark_webhook_completed(self, webhook_id: int, response_code: int, response_body: str = None) -> bool:
        """Mark webhook as completed."""
        try:
            webhook = await self.webhook_outbound_repo.get_by_id(webhook_id)
            if not webhook:
                return False
            
            webhook.mark_completed(response_code, response_body)
            await self.webhook_outbound_repo.update(webhook_id, {
                "response_code": response_code,
                "response_body": response_body,
                "completed_at": webhook.completed_at
            })
            
            await self.commit()
            return True
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Failed to mark webhook completed: {e}")
            return False 