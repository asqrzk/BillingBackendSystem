from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.subscription import Subscription
from .base_repository import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    """Repository for Subscription operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Subscription, session)
    
    async def get_by_user_id(self, user_id: int) -> List[Subscription]:
        """Get all subscriptions for a user (with plan preloaded)."""
        try:
            query = (
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .options(selectinload(Subscription.plan))
                .order_by(Subscription.start_date.desc())
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting subscriptions for user {user_id}: {e}")
            raise
    
    async def get_active_subscription_by_user(self, user_id: int) -> Optional[Subscription]:
        """Get active subscription for a user."""
        try:
            query = (
                select(Subscription)
                .where(
                    and_(
                        Subscription.user_id == user_id,
                        Subscription.status.in_(["active", "trial", "pending"]),
                        Subscription.end_date > datetime.utcnow()
                    )
                )
                .options(selectinload(Subscription.plan))
                .order_by(Subscription.start_date.desc())
            )
            
            result = await self.session.execute(query)
            return result.scalars().first()
        except Exception as e:
            self.logger.error(f"Error getting active subscription for user {user_id}: {e}")
            raise
    
    async def get_with_relationships(self, subscription_id: UUID) -> Optional[Subscription]:
        """Get subscription with user and plan relationships."""
        return await self.get_by_id(
            subscription_id, 
            relationships=["user", "plan", "events"]
        )
    
    async def get_expiring_subscriptions(self, days_ahead: int = 3) -> List[Subscription]:
        """Get subscriptions expiring within specified days."""
        try:
            expiry_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
            future_date = datetime.utcnow().replace(
                day=datetime.utcnow().day + days_ahead,
                hour=23, 
                minute=59, 
                second=59
            )
            
            query = (
                select(Subscription)
                .where(
                    and_(
                        Subscription.status.in_(["active", "trial"]),
                        Subscription.end_date >= expiry_date,
                        Subscription.end_date <= future_date
                    )
                )
                .options(selectinload(Subscription.user), selectinload(Subscription.plan))
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting expiring subscriptions: {e}")
            raise
    
    async def get_past_due_subscriptions(self) -> List[Subscription]:
        """Get subscriptions that are past due."""
        try:
            query = (
                select(Subscription)
                .where(
                    or_(
                        Subscription.status == "past_due",
                        and_(
                            Subscription.status.in_(["active", "trial"]),
                            Subscription.end_date < datetime.utcnow()
                        )
                    )
                )
                .options(selectinload(Subscription.user), selectinload(Subscription.plan))
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting past due subscriptions: {e}")
            raise
    
    async def get_trial_subscriptions(self) -> List[Subscription]:
        """Get all trial subscriptions."""
        return await self.get_all(
            filters={"status": "trial"},
            relationships=["user", "plan"]
        )
    
    async def update_status(self, subscription_id: UUID, status: str) -> Optional[Subscription]:
        """Update subscription status."""
        update_data = {"status": status}
        if status == "cancelled":
            update_data["canceled_at"] = datetime.utcnow()
        
        return await self.update(subscription_id, update_data)
    
    async def extend_subscription(self, subscription_id: UUID, end_date: datetime) -> Optional[Subscription]:
        """Extend subscription end date."""
        return await self.update(subscription_id, {"end_date": end_date}) 