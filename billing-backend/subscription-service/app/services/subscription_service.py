from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.exc import IntegrityError

from app.models.subscription import Subscription
from app.models.subscription_event import SubscriptionEvent
from app.schemas.subscription import SubscriptionCreateRequest, TrialSubscriptionRequest
from app.core.config import settings
from .base_service import BaseService
from app.schemas.queue import QueueMessageEnvelope
import hashlib


class SubscriptionService(BaseService):
    """Service for subscription management operations."""
    
    async def create_subscription(self, request: SubscriptionCreateRequest) -> Subscription:
        """Create a new subscription."""
        try:
            # Validate user exists
            user = await self.user_repo.get_by_id(request.user_id)
            if not user:
                raise ValueError(f"User with ID {request.user_id} not found")
            
            # Validate plan exists and is active
            plan = await self.plan_repo.get_by_id(request.plan_id)
            if not plan or not plan.is_active:
                raise ValueError(f"Plan with ID {request.plan_id} not found or inactive")
            
            # Check for existing active subscription
            existing_subscription = await self.subscription_repo.get_active_subscription_by_user(request.user_id)
            if existing_subscription:
                raise ValueError(f"User {request.user_id} already has an active subscription")
            
            # Calculate subscription dates
            start_date = datetime.utcnow()
            if plan.billing_cycle == "yearly":
                end_date = start_date + timedelta(days=365)
            else:  # monthly
                end_date = start_date + timedelta(days=30)
            
            # Create subscription
            subscription_data = {
                "user_id": request.user_id,
                "plan_id": request.plan_id,
                "status": "pending",
                "start_date": start_date,
                "end_date": end_date
            }
            
            subscription = await self.subscription_repo.create(subscription_data)
            
            # Create subscription event
            event_data = {
                "subscription_id": subscription.id,
                "event_type": "created",
                "event_metadata": {"plan_name": plan.name, "amount": float(plan.price)}
            }
            
            event = SubscriptionEvent(**event_data)
            self.session.add(event)
            
            # Queue payment initiation
            await self._queue_payment_initiation(subscription.id, float(plan.price))
            
            # Load plan relationship before committing for response serialization
            await self.session.refresh(subscription, ["plan"])
            
            await self.commit()
            
            self.logger.info(f"Subscription created", 
                           subscription_id=str(subscription.id), 
                           user_id=request.user_id,
                           plan_id=str(request.plan_id))
            
            return subscription
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Error creating subscription: {e}")
            raise
    
    async def create_trial_subscription(self, request: TrialSubscriptionRequest) -> Subscription:
        """Create a trial subscription."""
        try:
            # Validate user exists
            user = await self.user_repo.get_by_id(request.user_id)
            if not user:
                raise ValueError(f"User with ID {request.user_id} not found")
            
            # Validate trial plan
            plan = await self.plan_repo.get_by_id(request.trial_plan_id)
            if not plan or not plan.is_active or not plan.is_trial_plan:
                raise ValueError(f"Trial plan with ID {request.trial_plan_id} not found or invalid")
            
            # Check for existing active subscription
            existing_subscription = await self.subscription_repo.get_active_subscription_by_user(request.user_id)
            if existing_subscription:
                raise ValueError(f"User {request.user_id} already has an active subscription")
            
            # Check for existing pending subscriptions by querying directly
            from sqlalchemy import select, and_
            from app.models.subscription import Subscription as SubscriptionModel
            
            pending_query = select(SubscriptionModel).where(
                and_(
                    SubscriptionModel.user_id == request.user_id,
                    SubscriptionModel.status.in_(["pending"])
                )
            )
            result = await self.session.execute(pending_query)
            pending_subscription = result.scalars().first()
            
            if pending_subscription:
                raise ValueError(f"User {request.user_id} already has a pending subscription")
            
            # Calculate trial dates
            start_date = datetime.utcnow()
            trial_days = plan.trial_period_days
            end_date = start_date + timedelta(days=trial_days)
            
            # Create trial subscription (not active yet)
            subscription_data = {
                "user_id": request.user_id,
                "plan_id": request.trial_plan_id,
                "status": "pending",
                "start_date": start_date,
                "end_date": end_date
            }
            
            subscription = await self.subscription_repo.create(subscription_data)
            
            # Create subscription event
            event_data = {
                "subscription_id": subscription.id,
                "event_type": "trial_started",
                "event_metadata": {
                    "trial_days": trial_days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "status": "pending"
                }
            }
            
            event = SubscriptionEvent(**event_data)
            self.session.add(event)
            
            # Queue trial payment (1 AED charge + immediate refund)
            await self._queue_trial_payment(subscription.id)
            
            # Load plan relationship before committing for response serialization
            await self.session.refresh(subscription, ["plan"])
            
            await self.commit()
            
            self.logger.info(
                f"Trial subscription created",
                subscription_id=subscription.id,
                user_id=request.user_id,
                trial_days=trial_days
            )
            
            return subscription
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Error creating trial subscription: {e}")
            raise
    
    async def change_plan(self, subscription_id: UUID, new_plan_id: int) -> Subscription:
        """Change subscription plan."""
        try:
            # Get current subscription
            subscription = await self.subscription_repo.get_with_relationships(subscription_id)
            if not subscription:
                raise ValueError(f"Subscription {subscription_id} not found")
            
            if not subscription.is_active:
                raise ValueError(f"Subscription {subscription_id} is not active")
            
            # Get new plan
            new_plan = await self.plan_repo.get_by_id(new_plan_id)
            if not new_plan or not new_plan.is_active:
                raise ValueError(f"Plan {new_plan_id} not found or inactive")
            
            current_plan = subscription.plan
            
            # For upgrades, initiate a payment with action 'upgrade'
            idemp = hashlib.sha256(f"{subscription_id}:upgrade:{new_plan_id}:{int(datetime.utcnow().timestamp())//3600}".encode()).hexdigest()
            envelope = QueueMessageEnvelope(
                action="upgrade",
                correlation_id=str(subscription_id),
                idempotency_key=idemp,
                payload={
                    "subscription_id": str(subscription_id),
                    "old_plan_id": int(current_plan.id),
                    "new_plan_id": int(new_plan_id),
                    "amount": float(new_plan.price),
                    "currency": "AED"
                }
            )
            await self.redis.queue_message("q:sub:payment_initiation", envelope.model_dump())
            
            self.logger.info(f"Plan change queued", 
                           subscription_id=str(subscription_id),
                           old_plan=current_plan.name,
                           new_plan=new_plan.name)
            
            return subscription
            
        except Exception as e:
            self.logger.error(f"Error changing plan: {e}")
            raise
    
    async def cancel_subscription(self, subscription_id: UUID) -> Subscription:
        """Cancel a subscription immediately."""
        try:
            subscription = await self.subscription_repo.get_with_relationships(subscription_id)
            if not subscription:
                raise ValueError(f"Subscription {subscription_id} not found")
            
            if subscription.is_cancelled:
                raise ValueError(f"Subscription {subscription_id} is already cancelled")
            
            # Update subscription status
            subscription = await self.subscription_repo.update_status(subscription_id, "cancelled")
            
            # Create cancellation event
            event_data = {
                "subscription_id": subscription_id,
                "event_type": "cancelled",
                "event_metadata": {"cancelled_by": "user", "cancellation_reason": "immediate"}
            }
            
            event = SubscriptionEvent(**event_data)
            self.session.add(event)
            
            await self.commit()
            
            self.logger.info(f"Subscription cancelled", 
                           subscription_id=str(subscription_id))
            
            return subscription
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Error cancelling subscription: {e}")
            raise
    
    async def get_subscription(self, subscription_id: UUID) -> Optional[Subscription]:
        """Get subscription by ID with relationships."""
        return await self.subscription_repo.get_with_relationships(subscription_id)
    
    async def get_user_subscriptions(self, user_id: int) -> List[Subscription]:
        """Get all subscriptions for a user."""
        return await self.subscription_repo.get_by_user_id(user_id)
    
    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get active subscription for a user."""
        return await self.subscription_repo.get_active_subscription_by_user(user_id)
    
    async def process_subscription_renewal(self, subscription_id: UUID) -> bool:
        """Process subscription renewal (called by worker)."""
        try:
            subscription = await self.subscription_repo.get_with_relationships(subscription_id)
            if not subscription:
                self.logger.error(f"Subscription {subscription_id} not found for renewal")
                return False
            
            current_plan = subscription.plan
            renewal_amount = float(current_plan.price)
            
            # For trial subscriptions, check if there's a renewal plan
            if subscription.is_trial:
                renewal_plan = await self.plan_repo.get_renewal_plan(current_plan.id)
                if renewal_plan:
                    # Update subscription to use renewal plan
                    await self.subscription_repo.update(subscription_id, {
                        "plan_id": renewal_plan.id
                    })
                    renewal_amount = float(renewal_plan.price)
            
            # Queue payment for renewal
            await self._queue_payment_initiation(subscription_id, renewal_amount, is_renewal=True)
            
            self.logger.info(f"Subscription renewal queued", 
                           subscription_id=str(subscription_id),
                           amount=renewal_amount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing subscription renewal: {e}")
            return False
    
    async def _queue_payment_initiation(self, subscription_id: UUID, amount: float, is_renewal: bool = False):
        """Queue payment initiation message (enveloped)."""
        import hashlib
        action = "renewal" if is_renewal else "initial"
        idemp = hashlib.sha256(f"{subscription_id}:{action}:{int(datetime.utcnow().timestamp())//3600}".encode()).hexdigest()
        envelope = QueueMessageEnvelope(
            action=action,
            correlation_id=str(subscription_id),
            idempotency_key=idemp,
            payload={
                "subscription_id": str(subscription_id),
                "amount": amount,
                "currency": "AED",
                "renewal": is_renewal
            }
        )
        await self.redis.queue_message("q:sub:payment_initiation", envelope.model_dump())
 
    async def _queue_trial_payment(self, subscription_id: UUID):
        """Queue trial payment message (enveloped)."""
        idemp = hashlib.sha256(f"{subscription_id}:trial:{int(datetime.utcnow().timestamp())//3600}".encode()).hexdigest()
        envelope = QueueMessageEnvelope(
            action="trial",
            correlation_id=str(subscription_id),
            idempotency_key=idemp,
            payload={
                "subscription_id": str(subscription_id),
                "amount": 1.00,
                "currency": "AED",
                "trial": True
            }
        )
        await self.redis.queue_message("q:sub:trial_payment", envelope.model_dump()) 

    