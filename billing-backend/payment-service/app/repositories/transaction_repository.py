from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.models.transaction import Transaction
from .base_repository import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for Transaction operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Transaction, session)
    
    async def get_by_subscription_id(self, subscription_id: UUID) -> List[Transaction]:
        """Get all transactions for a subscription."""
        return await self.get_all(filters={"subscription_id": subscription_id})
    
    async def get_by_status(self, status: str) -> List[Transaction]:
        """Get transactions by status."""
        return await self.get_all(filters={"status": status})
    
    async def get_pending_transactions(self) -> List[Transaction]:
        """Get all pending transactions."""
        return await self.get_by_status("pending")
    
    async def get_processing_transactions(self) -> List[Transaction]:
        """Get all processing transactions."""
        return await self.get_by_status("processing")
    
    async def update_status(self, transaction_id: UUID, status: str, gateway_reference: str = None, error_message: str = None) -> Optional[Transaction]:
        """Update transaction status."""
        update_data = {"status": status}
        if gateway_reference:
            update_data["gateway_reference"] = gateway_reference
        if error_message:
            update_data["error_message"] = error_message
        
        return await self.update(transaction_id, update_data) 