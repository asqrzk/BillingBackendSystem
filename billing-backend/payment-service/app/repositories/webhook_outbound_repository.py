from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.webhook_outbound_request import WebhookOutboundRequest
from .base_repository import BaseRepository


class WebhookOutboundRepository(BaseRepository[WebhookOutboundRequest]):
    """Repository for WebhookOutboundRequest operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(WebhookOutboundRequest, session)
    
    async def get_by_transaction_id(self, transaction_id: UUID) -> List[WebhookOutboundRequest]:
        """Get webhook requests by transaction ID."""
        return await self.get_all(filters={"transaction_id": transaction_id})
    
    async def get_pending_webhooks(self) -> List[WebhookOutboundRequest]:
        """Get all pending webhook requests."""
        return await self.get_all(filters={"response_code": None})
    
    async def get_failed_retryable_webhooks(self) -> List[WebhookOutboundRequest]:
        """Get failed webhook requests that can be retried."""
        # This is a simplified version - in reality you'd need more complex filtering
        all_webhooks = await self.get_all()
        return [w for w in all_webhooks if w.can_retry and w.is_failed] 