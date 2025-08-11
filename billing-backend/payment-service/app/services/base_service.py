from abc import ABC
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.repositories import (
    TransactionRepository,
    GatewayWebhookRepository,
    WebhookOutboundRepository
)


class BaseService(ABC):
    """Base service class with common functionality."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(self.__class__.__name__)
        
        # Initialize repositories
        self.transaction_repo = TransactionRepository(session)
        self.gateway_webhook_repo = GatewayWebhookRepository(session)
        self.webhook_outbound_repo = WebhookOutboundRepository(session)
        
        # Redis client for queue operations
        self.redis = redis_client
    
    async def commit(self):
        """Commit the current transaction."""
        try:
            await self.session.commit()
        except Exception as e:
            self.logger.error(f"Error committing transaction: {e}")
            await self.session.rollback()
            raise
    
    async def rollback(self):
        """Rollback the current transaction."""
        try:
            await self.session.rollback()
        except Exception as e:
            self.logger.error(f"Error rolling back transaction: {e}")
            raise 