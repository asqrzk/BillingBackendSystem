from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.plan import Plan
from .base_repository import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    """Repository for Plan operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Plan, session)
    
    async def get_active_plans(self) -> List[Plan]:
        """Get all active plans."""
        return await self.get_all(filters={"is_active": True})
    
    async def get_trial_plans(self) -> List[Plan]:
        """Get all trial plans based on features metadata."""
        try:
            # Query for plans where features contains trial key
            # This supports both {"trial": true} and {"trial": {...}} formats
            query = select(Plan).where(
                Plan.is_active == True,
                Plan.features.op("?")('"trial"')  # JSONB contains key "trial"
            )
            
            result = await self.session.execute(query)
            plans = result.scalars().all()
            
            # Additional filtering using the model's is_trial_plan property
            # to ensure consistency with metadata-based detection
            trial_plans = [plan for plan in plans if plan.is_trial_plan]
            
            return trial_plans
        except Exception as e:
            self.logger.error(f"Error getting trial plans: {e}")
            raise
    
    async def get_by_name(self, name: str) -> Optional[Plan]:
        """Get plan by name."""
        return await self.get_by_field("name", name)
    
    async def get_plans_by_billing_cycle(self, billing_cycle: str) -> List[Plan]:
        """Get plans by billing cycle."""
        return await self.get_all(filters={"billing_cycle": billing_cycle, "is_active": True})
    
    async def get_renewal_plan(self, trial_plan_id: int) -> Optional[Plan]:
        """Get the renewal plan for a trial plan.
        Uses simplified metadata format where renewal_plan is directly the plan ID.
        """
        try:
            trial_plan = await self.get_by_id(trial_plan_id)
            if not trial_plan or not trial_plan.is_trial_plan:
                return None
            
            # Use the plan's property which now handles the simplified format
            renewal_plan_id = trial_plan.trial_renewal_plan_id
            
            # Try integer lookup
            if renewal_plan_id:
                try:
                    return await self.get_by_id(int(renewal_plan_id))
                except Exception:
                    # Invalid integer format, skip
                    pass
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting renewal plan for trial {trial_plan_id}: {e}")
            raise 