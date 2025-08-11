from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.dialects.postgresql import insert

from app.models.user_usage import UserUsage
from .base_repository import BaseRepository


class UsageRepository(BaseRepository[UserUsage]):
    """Repository for UserUsage operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(UserUsage, session)
    
    async def get_user_feature_usage(self, user_id: int, feature_name: str) -> Optional[UserUsage]:
        """Get usage record for a specific user and feature."""
        try:
            query = select(UserUsage).where(
                and_(
                    UserUsage.user_id == user_id,
                    UserUsage.feature_name == feature_name
                )
            )
            
            result = await self.session.execute(query)
            return result.scalars().first()
        except Exception as e:
            self.logger.error(f"Error getting usage for user {user_id}, feature {feature_name}: {e}")
            raise
    
    async def get_user_all_usage(self, user_id: int) -> List[UserUsage]:
        """Get all usage records for a user."""
        return await self.get_all(filters={"user_id": user_id})
    
    async def get_user_usage(self, user_id: int) -> List[UserUsage]:
        """Compatibility method: get all usage records for a user."""
        return await self.get_user_all_usage(user_id)
    
    async def upsert_usage(
        self, 
        user_id: int, 
        feature_name: str, 
        usage_count: int, 
        reset_at: datetime
    ) -> UserUsage:
        """Upsert usage record (insert or update on conflict)."""
        try:
            # Use PostgreSQL's INSERT ... ON CONFLICT
            stmt = insert(UserUsage).values(
                user_id=user_id,
                feature_name=feature_name,
                usage_count=usage_count,
                reset_at=reset_at
            )
            
            # On conflict, set absolute usage_count and reset_at
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id', 'feature_name'],
                set_=dict(
                    usage_count=stmt.excluded.usage_count,
                    reset_at=stmt.excluded.reset_at,
                    updated_at=datetime.utcnow()
                )
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
            # Return the updated record
            return await self.get_user_feature_usage(user_id, feature_name)
            
        except Exception as e:
            self.logger.error(f"Error upserting usage for user {user_id}, feature {feature_name}: {e}")
            await self.session.rollback()
            raise
    
    async def reset_all_user_usage(self, user_id: int) -> int:
        """Reset all usage records for a specific user."""
        try:
            # Calculate next month first day
            now = datetime.utcnow()
            next_month_first = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            
            stmt = (
                update(UserUsage)
                .where(UserUsage.user_id == user_id)
                .values(usage_count=0, reset_at=next_month_first, updated_at=datetime.utcnow())
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount or 0
        except Exception as e:
            self.logger.error(f"Error resetting all usage for user {user_id}: {e}")
            await self.session.rollback()
            raise
    
    async def reset_expired_usage(self) -> int:
        """Reset usage for expired records."""
        try:
            # Get all expired records
            all_records = await self.get_all()
            expired_records = [r for r in all_records if r.is_expired]
            
            reset_count = 0
            for record in expired_records:
                # Calculate new reset time (next month)
                new_reset_at = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if new_reset_at.month == 12:
                    new_reset_at = new_reset_at.replace(year=new_reset_at.year + 1, month=1)
                else:
                    new_reset_at = new_reset_at.replace(month=new_reset_at.month + 1)
                
                await self.update(record.id, {
                    "usage_count": 0,
                    "reset_at": new_reset_at
                })
                reset_count += 1
            
            return reset_count
            
        except Exception as e:
            self.logger.error(f"Error resetting expired usage: {e}")
            raise
    
    async def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """Get usage statistics for a user."""
        try:
            usage_records = await self.get_user_all_usage(user_id)
            
            total_usage = sum(record.usage_count for record in usage_records)
            feature_breakdown = {
                record.feature_name: {
                    "usage_count": record.usage_count,
                    "reset_at": record.reset_at,
                    "is_expired": record.is_expired
                }
                for record in usage_records
            }
            
            return {
                "user_id": user_id,
                "total_usage": total_usage,
                "feature_count": len(usage_records),
                "features": feature_breakdown,
                "last_updated": max(
                    (record.updated_at for record in usage_records), 
                    default=None
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error getting usage stats for user {user_id}: {e}")
            raise 