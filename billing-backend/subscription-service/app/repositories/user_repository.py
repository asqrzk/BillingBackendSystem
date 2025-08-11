from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        return await self.get_by_field("email", email)
    
    async def get_with_subscriptions(self, user_id: int) -> Optional[User]:
        """Get user with their subscriptions."""
        return await self.get_by_id(user_id, relationships=["subscriptions"])
    
    async def get_with_usage_records(self, user_id: int) -> Optional[User]:
        """Get user with their usage records."""
        return await self.get_by_id(user_id, relationships=["usage_records"])
    
    async def get_users_with_active_subscriptions(self) -> List[User]:
        """Get all users with active subscriptions."""
        try:
            query = (
                select(User)
                .join(User.subscriptions)
                .where(User.subscriptions.any(status="active"))
                .options(selectinload(User.subscriptions))
            )
            
            result = await self.session.execute(query)
            return result.scalars().unique().all()
        except Exception as e:
            self.logger.error(f"Error getting users with active subscriptions: {e}")
            raise 