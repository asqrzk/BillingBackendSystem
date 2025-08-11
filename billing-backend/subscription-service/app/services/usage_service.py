from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
import json

from app.models.user_usage import UserUsage
from app.schemas.usage import UsageCheckResponse, UsageResponse, UsageStatsResponse
from app.core.config import settings
from .base_service import BaseService


class UsageService(BaseService):
    """Service for usage tracking and management operations."""
    
    async def use_feature(self, user_id: int, feature_name: str, delta: int = 1) -> UsageCheckResponse:
        """
        Use a feature atomically with Redis-based limit checking.
        
        This method performs atomic usage tracking to prevent race conditions
        when multiple requests try to use features simultaneously.
        """
        try:
            # Get user's active subscription to determine limits
            subscription = await self.subscription_repo.get_active_subscription_by_user(user_id)
            if not subscription:
                raise ValueError(f"No active subscription found for user {user_id}")
            
            plan = subscription.plan
            feature_limits = plan.get_feature_limits()
            feature_limit = feature_limits.get(feature_name, 0)
            
            if feature_limit <= 0:
                raise ValueError(f"Feature '{feature_name}' is not available in current plan")
            
            # Calculate reset time for Redis (first day of next month as epoch string)
            now = datetime.utcnow()
            next_month_first = (now.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            reset_at_str = str(int(next_month_first.timestamp()))
            
            # Use Redis atomic helper for usage checking and incrementing
            result = await self.redis.atomic_usage_check(
                user_id=user_id,
                feature_name=feature_name,
                limit=feature_limit,
                delta=delta,
                reset_at=reset_at_str
            )
            
            current_usage = int(result.get('current_usage', 0))
            limit = int(result.get('limit', feature_limit))
            success = bool(result.get('success', False))
            
            # Only sync to database when increment succeeds
            if success:
                await self._sync_usage_to_db(user_id, feature_name, current_usage)
            
            # Calculate reset time (monthly reset) for API response
            reset_at = next_month_first
            
            return UsageCheckResponse(
                success=success,
                current_usage=current_usage,
                limit=limit,
                remaining=max(0, limit - current_usage),
                reset_at=reset_at
            )
            
        except Exception as e:
            self.logger.error(f"Error using feature {feature_name} for user {user_id}: {e}")
            raise
    
    async def get_user_usage(self, user_id: int) -> List[UsageResponse]:
        """Get all usage records for a user."""
        try:
            # Get user's active subscription for limits
            subscription = await self.subscription_repo.get_active_subscription_by_user(user_id)
            feature_limits = {}
            
            if subscription and subscription.plan:
                feature_limits = subscription.plan.get_feature_limits()
            
            # Get usage records from database
            usage_records = await self.usage_repo.get_user_usage(user_id)
            
            results = []
            for usage in usage_records:
                limit = feature_limits.get(usage.feature_name, 0)
                results.append(UsageResponse.from_orm(usage, limit))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting user usage for user {user_id}: {e}")
            raise
    
    async def get_user_feature_usage(self, user_id: int, feature_name: str) -> Optional[UsageResponse]:
        """Get specific feature usage for a user."""
        try:
            # Get user's active subscription for limits
            subscription = await self.subscription_repo.get_active_subscription_by_user(user_id)
            feature_limit = 0
            
            if subscription and subscription.plan:
                feature_limits = subscription.plan.get_feature_limits()
                feature_limit = feature_limits.get(feature_name, 0)
            
            # Get usage record from database
            usage = await self.usage_repo.get_user_feature_usage(user_id, feature_name)
            
            if not usage:
                return None
            
            return UsageResponse.from_orm(usage, feature_limit)
            
        except Exception as e:
            self.logger.error(f"Error getting feature usage for user {user_id}, feature {feature_name}: {e}")
            raise
    
    async def reset_user_usage(self, user_id: int, feature_name: str = None) -> int:
        """Reset usage for a user (admin function)."""
        try:
            if feature_name:
                # Reset specific feature
                success = await self.usage_repo.reset_usage(user_id, feature_name)
                
                # Also clear Redis cache
                await self.redis.client.delete(f"usage:{user_id}:{feature_name}")
                
                return 1 if success else 0
            else:
                # Reset all features for user
                count = await self.usage_repo.reset_all_user_usage(user_id)
                
                # Clear Redis cache for all features
                keys_pattern = f"usage:{user_id}:*"
                keys = await self.redis.client.keys(keys_pattern)
                if keys:
                    await self.redis.client.delete(*keys)
                
                return count
            
        except Exception as e:
            self.logger.error(f"Error resetting usage for user {user_id}: {e}")
            raise
    
    async def get_usage_stats(self, user_id: int) -> UsageStatsResponse:
        """Get usage statistics for a user."""
        try:
            # Get user's active subscription
            subscription = await self.subscription_repo.get_active_subscription_by_user(user_id)
            feature_limits = {}
            
            if subscription and subscription.plan:
                feature_limits = subscription.plan.get_feature_limits()
            
            # Get usage records
            usage_records = await self.usage_repo.get_user_usage(user_id)
            
            total_usage = 0
            total_limit = 0
            features = {}
            
            for usage in usage_records:
                limit = feature_limits.get(usage.feature_name, 0)
                total_usage += usage.usage_count
                total_limit += limit
                
                features[usage.feature_name] = {
                    "usage": usage.usage_count,
                    "limit": limit,
                    "remaining": max(0, limit - usage.usage_count),
                    "percentage": (usage.usage_count / limit * 100) if limit > 0 else 0,
                    "reset_at": usage.reset_at.isoformat()
                }
            
            # Calculate period
            now = datetime.utcnow()
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
            
            return UsageStatsResponse(
                total_usage=total_usage,
                total_limit=total_limit,
                features=features,
                period_start=period_start,
                period_end=period_end
            )
            
        except Exception as e:
            self.logger.error(f"Error getting usage stats for user {user_id}: {e}")
            raise
    
    async def sync_usage_schedule(self):
        """Scheduled task to sync Redis usage to database."""
        try:
            # Get all usage keys from Redis
            keys = await self.redis.client.keys("usage:*")
            
            synced_count = 0
            for key in keys:
                try:
                    # Parse key: usage:user_id:feature_name
                    parts = key.split(":")
                    if len(parts) == 3:
                        user_id = int(parts[1])
                        feature_name = parts[2]
                        current_usage = await self.redis.client.get(key)
                        
                        if current_usage:
                            await self._sync_usage_to_db(user_id, feature_name, int(current_usage))
                            synced_count += 1
                            
                except Exception as e:
                    self.logger.error(f"Error syncing usage key {key}: {e}")
                    continue
            
            self.logger.info(f"Synced {synced_count} usage records to database")
            
        except Exception as e:
            self.logger.error(f"Error in usage sync schedule: {e}")
    
    async def reset_expired_usage_schedule(self):
        """Scheduled task to reset expired usage counters."""
        try:
            count = await self.usage_repo.reset_expired_usage()
            
            if count > 0:
                self.logger.info(f"Reset {count} expired usage records")
                
                # Also clear corresponding Redis keys
                # This is a simplified approach - in production you'd want more sophisticated cleanup
                await self.redis.client.flushdb()  # Clear all Redis data
                
        except Exception as e:
            self.logger.error(f"Error in expired usage reset schedule: {e}")
    
    async def _sync_usage_to_db(self, user_id: int, feature_name: str, current_usage: int):
        """Sync current usage from Redis to database."""
        try:
            # Calculate reset time (first day of next month)
            now = datetime.utcnow()
            reset_at = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            
            # Upsert usage record
            await self.usage_repo.upsert_usage(
                user_id=user_id,
                feature_name=feature_name,
                usage_count=current_usage,
                reset_at=reset_at
            )
            
            # Ensure changes are persisted for subsequent reads
            await self.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error syncing usage to DB: {e}")
            # Don't raise here to avoid breaking the main usage flow 