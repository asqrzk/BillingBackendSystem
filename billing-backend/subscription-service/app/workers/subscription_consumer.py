import asyncio
import json
from typing import Dict, Any

from .celery_app import celery_app
from .base_consumer import BaseConsumer
from app.core.database import AsyncSessionLocal
from app.services.subscription_service import SubscriptionService
from app.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionConsumer(BaseConsumer):
    """Consumer for subscription-related tasks."""
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Process subscription-related messages."""
        try:
            async with AsyncSessionLocal() as session:
                service = SubscriptionService(session)
                
                # Handle subscription renewal
                if "subscription_id" in message and "renewal" in message:
                    subscription_id = message["subscription_id"]
                    success = await service.process_subscription_renewal(subscription_id)
                    return success
                
                # Add other subscription message types here
                logger.warning(f"Unknown subscription message type: {message}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing subscription message: {e}")
            return False


@celery_app.task(bind=True, max_retries=5)
def process_payment_initiation(self, message_data: str):
    """Process payment initiation queue messages for renewals with retries."""
    try:
        import asyncio
        import httpx
        from app.core.config import settings
        from app.core.auth import create_service_token
        
        message = json.loads(message_data)
        logger.info(f"Processing payment initiation: {message}")
        
        # Unwrap envelope-compatible messages
        payload = message.get("payload", {}) if isinstance(message, dict) else {}
        top = message if isinstance(message, dict) else {}
        action = top.get("action") or payload.get("action") or ("renewal" if payload.get("renewal") else None)
        
        subscription_id = payload.get("subscription_id") or top.get("subscription_id")
        amount = payload.get("amount") or top.get("amount")
        currency = payload.get("currency") or top.get("currency") or "AED"
        
        # Flags inferred from action/payload
        is_trial = bool(payload.get("trial") or top.get("trial"))
        is_renewal = bool(payload.get("renewal") or top.get("renewal") or (action == "renewal"))
        is_upgrade = bool((action == "upgrade") or payload.get("upgrade") or top.get("upgrade"))
        new_plan_id = payload.get("new_plan_id") or top.get("new_plan_id")
        old_plan_id = payload.get("old_plan_id") or top.get("old_plan_id")
        
        # Call payment service internal endpoint for initiation
        async def make_payment_call():
            async with httpx.AsyncClient() as client:
                payment_data = {
                    "amount": amount,
                    "currency": currency,
                    "card_number": "4242424242424242",
                    "card_expiry": "12/25",
                    "card_cvv": "123",
                    "cardholder_name": "Initiation User",
                    "trial": is_trial,
                    "renewal": is_renewal,
                    "upgrade": is_upgrade,
                    "new_plan_id": new_plan_id,
                    "old_plan_id": old_plan_id,
                }
                
                service_token = create_service_token("subscription-service")
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {service_token}"
                }
                
                payment_url = f"{settings.PAYMENT_SERVICE_URL}/v1/payments/internal/process"
                return await client.post(
                    payment_url,
                    json=payment_data,
                    headers=headers,
                    params={"subscription_id": subscription_id}
                )
        
        response = asyncio.run(make_payment_call())
        if response.status_code == 201:
            logger.info(f"Payment initiation successful for subscription {subscription_id}")
            return {"status": "success", "subscription_id": subscription_id}
        else:
            logger.error(f"Payment initiation failed [{response.status_code}]: {response.text}")
            # Exponential backoff
            delay = int(getattr(settings, "PAYMENT_RETRY_DELAY_SECONDS", 60)) * max(1, self.request.retries + 1)
            raise self.retry(countdown=delay)
        
    except self.MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for payment initiation: {message_data}")
        raise
    except Exception as e:
        logger.error(f"Payment initiation failed: {e}")
        delay = int(getattr(settings, "PAYMENT_RETRY_DELAY_SECONDS", 60)) * max(1, self.request.retries + 1)
        raise self.retry(countdown=delay, exc=e)


@celery_app.task(bind=True, max_retries=3)
def process_trial_payment(self, message_data: str):
    """Process trial payment queue messages."""
    try:
        import asyncio
        import httpx
        from app.core.config import settings
        from app.core.auth import create_service_token
        
        message = json.loads(message_data)
        logger.info(f"Processing trial payment: {message}")
        
        # Extract from nested payload structure
        payload = message.get("payload", {})
        subscription_id = payload.get("subscription_id") or message.get("subscription_id")
        amount = payload.get("amount") or message.get("amount", 1.00)
        currency = payload.get("currency") or message.get("currency", "AED")
        
        # Call payment service internal endpoint
        async def make_payment_call():
            async with httpx.AsyncClient() as client:
                payment_data = {
                    "amount": amount,
                    "currency": currency,
                    "card_number": "4242424242424242",  # Success card for trial
                    "card_expiry": "12/25",
                    "card_cvv": "123",
                    "cardholder_name": "Trial User",
                    "trial": True,
                    "renewal": False
                }
                
                service_token = create_service_token("subscription-service")
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {service_token}"
                }
                
                payment_url = f"{settings.PAYMENT_SERVICE_URL}/v1/payments/internal/process"
                response = await client.post(
                    payment_url,
                    json=payment_data,
                    headers=headers,
                    params={"subscription_id": subscription_id}
                )
                
                if response.status_code == 201:
                    logger.info(f"Trial payment successful for subscription {subscription_id}")
                    return {"status": "success", "subscription_id": subscription_id}
                else:
                    logger.error(f"Trial payment failed: {response.status_code} - {response.text}")
                    return {"status": "failed", "subscription_id": subscription_id}
        
        result = asyncio.run(make_payment_call())
        return result
        
    except Exception as e:
        logger.error(f"Trial payment failed: {e}")
        raise self.retry(countdown=60, exc=e)


@celery_app.task(bind=True, max_retries=3)
def process_plan_change(self, message_data: str):
    """Process plan change queue messages."""
    try:
        message = json.loads(message_data)
        logger.info(f"Processing plan change: {message}")
        
        subscription_id = message.get("subscription_id")
        old_plan_id = message.get("old_plan_id")
        new_plan_id = message.get("new_plan_id")
        
        logger.info(f"Plan change for subscription {subscription_id}: {old_plan_id} -> {new_plan_id}")
        
        # Simulate processing
        return {"status": "processed", "subscription_id": subscription_id}
        
    except Exception as e:
        logger.error(f"Plan change failed: {e}")
        raise self.retry(countdown=60, exc=e)


@celery_app.task(bind=True, max_retries=5)
def process_subscription_renewal(self, message_data: str):
    """Process subscription renewal."""
    try:
        message = json.loads(message_data)
        logger.info(f"Processing subscription renewal: {message}")
        
        # This would trigger the actual renewal process
        subscription_id = message.get("subscription_id")
        
        # Run async function in sync context
        async def run_renewal():
            async with AsyncSessionLocal() as session:
                service = SubscriptionService(session)
                return await service.process_subscription_renewal(subscription_id)
        
        success = asyncio.run(run_renewal())
        
        if success:
            logger.info(f"Subscription renewal completed for {subscription_id}")
            return {"status": "renewed", "subscription_id": subscription_id}
        else:
            raise Exception("Renewal failed")
            
    except Exception as e:
        logger.error(f"Subscription renewal failed: {e}")
        raise self.retry(countdown=300, exc=e)


@celery_app.task(bind=True)
def schedule_renewals():
    """Scheduled task to check for subscriptions that need renewal."""
    try:
        async def run_scheduling():
            async with AsyncSessionLocal() as session:
                service = SubscriptionService(session)
                # Find subscriptions that need renewal (e.g., ending in next 24 hours)
                # This would be implemented in the service layer
                logger.info("Checking for subscriptions that need renewal scheduling")
                # Implementation would query for expiring subscriptions and queue renewal tasks
        
        asyncio.run(run_scheduling())
        logger.info("Renewal scheduling completed")
        
    except Exception as e:
        logger.error(f"Renewal scheduling failed: {e}")
        raise 