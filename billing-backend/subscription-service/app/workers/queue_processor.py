import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from .celery_app import celery_app
from .base_consumer import BaseConsumer
from app.core.database import AsyncSessionLocal
from app.core.redis_client import redis_client
from app.core.logging import get_logger
from app.core.queue_policies import QUEUE_POLICIES

logger = get_logger(__name__)


class QueueProcessorConsumer(BaseConsumer):
    """Consumer for general queue processing tasks."""
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """Process general queue messages."""
        try:
            # Handle different types of queue maintenance messages
            message_type = message.get("type")
            
            if message_type == "delayed_queue_check":
                await self._process_delayed_queues()
                return True
            elif message_type == "queue_cleanup":
                await self._cleanup_old_messages()
                return True
            
            logger.warning(f"Unknown queue processor message type: {message}")
            return False
                
        except Exception as e:
            logger.error(f"Error processing queue message: {e}")
            return False
    
    async def _process_delayed_queues(self):
        """Process delayed queue messages that are ready."""
        try:
            if not redis_client.client:
                await redis_client.connect()
            
            # Move ready delayed → main for all sub queues
            for main in [
                "q:sub:payment_initiation",
                "q:sub:trial_payment",
                "q:sub:plan_change",
                "q:sub:usage_sync",
            ]:
                moved = await redis_client.move_ready_delayed_to_main(main)
                if moved:
                    logger.info(f"Moved {moved} delayed messages to {main}")
        except Exception as e:
            logger.error(f"Error processing delayed queues: {e}")
            raise
    
    async def _cleanup_old_messages(self):
        """Clean up old failed/completed messages."""
        try:
            if not redis_client.client:
                await redis_client.connect()
            
            # Clean up old failed messages (older than 7 days)
            cutoff_time = datetime.utcnow().timestamp() - (7 * 24 * 60 * 60)
            
            failed_queues = [
                "q:sub:payment_initiation:failed",
                "q:sub:trial_payment:failed",
                "q:sub:plan_change:failed"
            ]
            
            for queue in failed_queues:
                # Remove old messages from failed queues
                # This is a simplified cleanup - in production you'd want more sophisticated logic
                current_length = await redis_client.get_queue_length(queue)
                if current_length > 1000:  # If too many failed messages
                    # Keep only the latest 100
                    for _ in range(current_length - 100):
                        await redis_client.client.rpop(queue)
                    
                    logger.info(f"Cleaned up old messages from {queue}")
            
        except Exception as e:
            logger.error(f"Error cleaning up queues: {e}")
            raise


async def _compute_backoff(queue_name: str, attempts: int) -> int:
    policy = QUEUE_POLICIES.get(queue_name)
    base = getattr(policy, 'base_delay_seconds', 60)
    mult = getattr(policy, 'backoff_multiplier', 2.0)
    cap = getattr(policy, 'max_delay_seconds', 3600)
    jitter = getattr(policy, 'jitter_seconds', 10)
    import random
    delay = min(int(base * (mult ** max(0, attempts))), cap)
    return max(0, delay + random.randint(0, jitter))


async def _claim_lock_process(queue_main: str, handler_task, action_label: str):
    queue_processing = f"{queue_main}:processing"
    msg = await redis_client.claim_message(queue_main, queue_processing, timeout=1)
    if not msg:
        return "no_message"
    try:
        raw = json.loads(msg)
    except Exception:
        raw = msg
    attempts = int((raw or {}).get("attempts", 0) if isinstance(raw, dict) else 0)
    lock_ttl = getattr(QUEUE_POLICIES.get(queue_main, object()), 'lock_ttl_seconds', 120)
    lock_key = f"lock:{queue_main}:{hash(msg)}"
    got = await redis_client.set_lock(lock_key, ttl_seconds=lock_ttl or 120)
    if not got:
        await redis_client.remove_from_processing(queue_processing, msg)
        await redis_client.queue_message(queue_main, raw if isinstance(raw, dict) else {"payload": raw})
        return "retry"
    try:
        # Delegate to specific handler
        return await handler_task(msg)
    except Exception as e:
        attempts_next = attempts + 1
        max_retries = getattr(QUEUE_POLICIES.get(queue_main, object()), 'max_retries', 5)
        await redis_client.remove_from_processing(queue_processing, msg)
        if attempts_next <= max_retries:
            if isinstance(raw, dict):
                raw["attempts"] = attempts_next
                await redis_client.queue_delayed_message(queue_main, raw, delay_seconds=await _compute_backoff(queue_main, attempts_next))
            else:
                await redis_client.queue_delayed_message(queue_main, {"payload": raw, "attempts": attempts_next}, delay_seconds=await _compute_backoff(queue_main, attempts_next))
            return "retry"
        else:
            if not redis_client.client:
                await redis_client.connect()
            await redis_client.client.lpush(f"{queue_main}:failed", msg)
            return "failed"
    finally:
        await redis_client.release_lock(lock_key)


@celery_app.task(bind=True)
def poll_payment_initiation_queue(self):
    """BRPOPLPUSH + lock wrapper for payment initiation."""
    async def _run():
        from .subscription_consumer import process_payment_initiation
        async def handler(message_json: str):
            # hand off to existing task
            process_payment_initiation.apply_async(args=[message_json])
            return "dispatched"
        return await _claim_lock_process("q:sub:payment_initiation", handler, "payment_initiation")
    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())


@celery_app.task(bind=True)
def poll_trial_payment_queue(self):
    """BRPOPLPUSH + lock wrapper for trial payment."""
    async def _run():
        from .subscription_consumer import process_trial_payment
        async def handler(message_json: str):
            process_trial_payment.apply_async(args=[message_json])
            return "dispatched"
        return await _claim_lock_process("q:sub:trial_payment", handler, "trial_payment")
    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())


@celery_app.task(bind=True)
def poll_plan_change_queue(self):
    """BRPOPLPUSH + lock wrapper for plan change."""
    async def _run():
        from .subscription_consumer import process_plan_change
        async def handler(message_json: str):
            process_plan_change.apply_async(args=[message_json])
            return "dispatched"
        return await _claim_lock_process("q:sub:plan_change", handler, "plan_change")
    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())


@celery_app.task(bind=True)
def poll_usage_sync_queue(self):
    """BRPOPLPUSH + lock wrapper for usage sync."""
    async def _run():
        from .usage_consumer import process_usage_sync
        async def handler(message_json: str):
            process_usage_sync.apply_async(args=[message_json])
            return "dispatched"
        return await _claim_lock_process("q:sub:usage_sync", handler, "usage_sync")
    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())


@celery_app.task(bind=True)
def process_delayed_queues():
    """Scheduled task to process delayed queue messages."""
    try:
        async def run_processing():
            processor = QueueProcessorConsumer(None)
            await processor._process_delayed_queues()
        
        asyncio.run(run_processing())
        logger.info("Delayed queue processing completed")
        
    except Exception as e:
        logger.error(f"Delayed queue processing failed: {e}")
        raise


@celery_app.task(bind=True)
def cleanup_old_queue_messages():
    """Scheduled task to clean up old queue messages."""
    try:
        async def run_cleanup():
            processor = QueueProcessorConsumer(None)
            await processor._cleanup_old_messages()
        
        asyncio.run(run_cleanup())
        logger.info("Queue cleanup completed")
        
    except Exception as e:
        logger.error(f"Queue cleanup failed: {e}")
        raise


@celery_app.task(bind=True)
def monitor_queue_health():
    """Scheduled task to monitor queue health and send alerts."""
    try:
        async def run_monitoring():
            if not redis_client.client:
                await redis_client.connect()
            
            # Check queue depths and send alerts if too high
            alert_threshold = 1000
            
            queues_to_monitor = [
                "q:sub:payment_initiation",
                "q:sub:trial_payment",
                "q:sub:plan_change",
                "q:sub:usage_sync"
            ]
            
            for queue in queues_to_monitor:
                depth = await redis_client.get_queue_length(queue)
                if depth > alert_threshold:
                    logger.warning(f"Queue {queue} has high depth: {depth}")
                    # In production, you'd send alerts here
            
            logger.info("Queue health monitoring completed")
        
        asyncio.run(run_monitoring())
        
    except Exception as e:
        logger.error(f"Queue health monitoring failed: {e}")
        raise


@celery_app.task(bind=True)
def sweep_processing_queues(self):
    """Visibility sweeper: return orphaned :processing items to delayed/failed per policy."""
    try:
        async def _run():
            if not redis_client.client:
                await redis_client.connect()
            queues = [
                "q:sub:payment_initiation",
                "q:sub:trial_payment",
                "q:sub:plan_change",
                "q:sub:usage_sync",
            ]
            results = {}
            for main in queues:
                processing = f"{main}:processing"
                items = await redis_client.client.lrange(processing, 0, -1)
                swept = 0
                for msg in items:
                    try:
                        raw = json.loads(msg)
                    except Exception:
                        raw = {}
                    mid = (raw.get("id") if isinstance(raw, dict) else None) or str(hash(msg))
                    lock_key = f"lock:{main}:{mid}"
                    lock_exists = await redis_client.client.exists(lock_key)
                    if lock_exists:
                        continue
                    # No lock -> orphan
                    attempts = int((raw or {}).get("attempts", 0) if isinstance(raw, dict) else 0) + 1
                    await redis_client.remove_from_processing(processing, msg)
                    policy = QUEUE_POLICIES.get(main)
                    max_try = getattr(policy, 'max_retries', 5)
                    if attempts <= max_try:
                        if isinstance(raw, dict):
                            raw["attempts"] = attempts
                            await redis_client.queue_delayed_message(main, raw, delay_seconds=await _compute_backoff(main, attempts))
                        else:
                            await redis_client.queue_delayed_message(main, {"payload": raw, "attempts": attempts}, delay_seconds=await _compute_backoff(main, attempts))
                    else:
                        await redis_client.client.lpush(f"{main}:failed", msg)
                    swept += 1
                results[main] = swept
            logger.info(f"Processing sweeper results: {results}")
        
        asyncio.run(_run())
    except Exception as e:
        logger.error(f"Visibility sweep failed: {e}")
        raise


@celery_app.task(bind=True)
def poll_webhook_processing_queue(self):
    """Poll webhook processing queue for payment webhooks to process."""
    try:
        async def run_webhook_processing():
            if not redis_client.client:
                await redis_client.connect()
            
            # Check webhook processing queue
            queue_name = "q:pay:subscription_update"
            
            # Poll for webhook messages (timeout=1 second)
            message_data = await redis_client.client.brpop(queue_name, timeout=1)
            if message_data:
                queue_name_returned, message_json = message_data
                message = json.loads(message_json)
                logger.info(f"Processing webhook from queue: {message}")
                
                # Import here to avoid circular dependencies
                from app.services.webhook_service import WebhookService
                from app.schemas.webhook import WebhookPayload
                
                async with AsyncSessionLocal() as session:
                    try:
                        webhook_service = WebhookService(session)
                        
                        # Convert message to webhook payload
                        webhook_payload = WebhookPayload(**message)
                        
                        # Process the webhook
                        result = await webhook_service.process_webhook_event(
                            webhook_payload.event_id, 
                            message
                        )
                        
                        logger.info(f"Webhook processing result: {result}")
                        
                    except Exception as e:
                        logger.error(f"Error processing webhook message: {e}")
                        # Re-queue for retry
                        await redis_client.queue_message(queue_name, message)
            else:
                logger.debug("No webhook messages to process")
        
        # Handle asyncio event loop properly in Celery worker
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(run_webhook_processing())
        
    except Exception as e:
        logger.error(f"Webhook processing polling failed: {e}")
        raise 