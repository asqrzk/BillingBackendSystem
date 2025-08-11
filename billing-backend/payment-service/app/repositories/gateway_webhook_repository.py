from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.gateway_webhook_request import GatewayWebhookRequest
from .base_repository import BaseRepository


class GatewayWebhookRepository(BaseRepository[GatewayWebhookRequest]):
    """Repository for GatewayWebhookRequest operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(GatewayWebhookRequest, session)
    
    async def get_by_transaction_id(self, transaction_id: UUID) -> Optional[GatewayWebhookRequest]:
        """Get webhook request by transaction ID."""
        return await self.get_by_field("transaction_id", transaction_id)
    
    async def get_unprocessed_webhooks(self) -> List[GatewayWebhookRequest]:
        """Get all unprocessed webhook requests."""
        return await self.get_all(filters={"processed": False}) 