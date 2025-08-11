from .celery_app import celery_app
from app.core.redis_client import redis_client
from app.services.gateway_service import MockGatewayService
from app.core.webhook_client import WebhookClient
from app.core.config import settings
from app.core.logging import get_logger
from app.core.job_logger import log_job_event
from app.core.queue_policies import QUEUE_POLICIES
from app.core.database import AsyncSessionLocal
from app.models.job_log import JobLog
from uuid import UUID
import asyncio
import json
import hashlib
import random

logger = get_logger(__name__)

gateway = MockGatewayService()


async def _db_log(queue: str, action: str, status: str, message_id: str = None, attempts: int = 0, info: dict = None, correlation_id: str = None, idempotency_key: str = None):
    try:
        async with AsyncSessionLocal() as session:
            entry = JobLog(
                service="payment",
                queue=queue,
                message_id=message_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                action=action,
                status=status,
                attempts=attempts,
                last_error=(info or {}).get("error") if info else None,
                next_retry_at=None,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        # best-effort
        return


def _hash_message(message_json: str) -> str:
    return hashlib.sha256(message_json.encode("utf-8")).hexdigest()


def _parse_message(message_json: str):
    raw = json.loads(message_json)
    # Backward-compatible unwrapping
    if isinstance(raw, dict) and "payload" in raw and "action" in raw:
        envelope = raw
        payload = envelope.get("payload", {})
        action = envelope.get("action")
        message_id = envelope.get("id") or _hash_message(message_json)
        attempts = int(envelope.get("attempts", 0) or 0)
        max_attempts = envelope.get("max_attempts")
        correlation_id = envelope.get("correlation_id")
        idempotency_key = envelope.get("idempotency_key")
        return envelope, payload, action, message_id, attempts, max_attempts, correlation_id, idempotency_key
    else:
        payload = raw
        action = raw.get("action") or "webhook"
        message_id = raw.get("event_id") or _hash_message(message_json)
        attempts = int(raw.get("attempts", 0) or 0)
        max_attempts = raw.get("max_attempts")
        correlation_id = raw.get("subscription_id")
        idempotency_key = raw.get("event_id")
        return raw, payload, action, message_id, attempts, max_attempts, correlation_id, idempotency_key


def _compute_backoff(queue_name: str, attempts: int) -> int:
    policy = QUEUE_POLICIES.get(queue_name)
    if not policy:
        base, mult, cap, jit = 60, 2.0, 3600, 10
    else:
        base = policy.base_delay_seconds
        mult = policy.backoff_multiplier
        cap = policy.max_delay_seconds
        jit = policy.jitter_seconds
    delay = min(int(base * (mult ** max(0, attempts))), cap)
    return max(0, delay + random.randint(0, jit))


async def _process_subscription_update_once():
    queue_main = "q:pay:subscription_update"
    queue_processing = f"{queue_main}:processing"

    message_json = await redis_client.claim_message(queue_main, queue_processing, timeout=1)
    if not message_json:
        await log_job_event(queue_main, action="webhook", status="no_message")
        return "no_message"

    envelope_or_raw, payload, action, message_id, attempts, max_attempts, correlation_id, idempotency_key = _parse_message(message_json)
    lock_key = f"lock:{queue_main}:{message_id}"

    lock_ttl = getattr(QUEUE_POLICIES.get(queue_main, object()), 'lock_ttl_seconds', 120) or 120
    got_lock = await redis_client.set_lock(lock_key, ttl_seconds=lock_ttl)
    if not got_lock:
        await redis_client.remove_from_processing(queue_processing, message_json)
        await redis_client.queue_message(queue_main, json.loads(message_json))
        await log_job_event(queue_main, action=action or "webhook", status="retry", message_id=message_id, attempts=attempts, info={"reason": "lock_unavailable"})
        await _db_log(queue_main, action or "webhook", "retry", message_id, attempts, {"reason": "lock_unavailable"}, correlation_id, idempotency_key)
        return "retry"

    await log_job_event(queue_main, action=action or "webhook", status="start", message_id=message_id, attempts=attempts)
    await _db_log(queue_main, action or "webhook", "processing", message_id, attempts, None, correlation_id, idempotency_key)

    webhook_client = WebhookClient(
        base_url=settings.SUBSCRIPTION_SERVICE_URL,
        signing_secret=settings.WEBHOOK_SIGNING_SECRET
    )

    event_id = payload.get("event_id")
    try:
        await webhook_client.send_webhook(
            endpoint="/v1/webhooks/payment",
            payload=payload,
            event_id=event_id
        )
        logger.info("Subscription update webhook sent", event_id=event_id, action=action)
        await redis_client.remove_from_processing(queue_processing, message_json)
        await log_job_event(queue_main, action=action or "webhook", status="success", message_id=message_id, attempts=attempts)
        await _db_log(queue_main, action or "webhook", "success", message_id, attempts, None, correlation_id, idempotency_key)
        return "success"
    except Exception as e:
        attempts_next = attempts + 1
        policy = QUEUE_POLICIES.get(queue_main)
        max_try = (policy.max_retries if policy else 5)
        await redis_client.remove_from_processing(queue_processing, message_json)
        if max_attempts is not None:
            try:
                max_try = int(max_attempts)
            except Exception:
                pass
        if attempts_next <= max_try:
            if isinstance(envelope_or_raw, dict) and "payload" in envelope_or_raw:
                envelope_or_raw["attempts"] = attempts_next
                msg_for_delay = envelope_or_raw
            else:
                d = payload.copy()
                d["attempts"] = attempts_next
                msg_for_delay = d
            delay = _compute_backoff(queue_main, attempts_next)
            await redis_client.queue_delayed_message(queue_main, msg_for_delay, delay_seconds=delay)
            await log_job_event(queue_main, action=action or "webhook", status="retry", message_id=message_id, attempts=attempts_next, info={"error": str(e), "delay": delay})
            await _db_log(queue_main, action or "webhook", "retry", message_id, attempts_next, {"error": str(e), "delay": delay}, correlation_id, idempotency_key)
            return "retry"
        else:
            if not redis_client.client:
                await redis_client.connect()
            await redis_client.client.lpush(f"{queue_main}:failed", message_json)
            await log_job_event(queue_main, action=action or "webhook", status="failed", message_id=message_id, attempts=attempts_next, info={"error": str(e)})
            await _db_log(queue_main, action or "webhook", "failed", message_id, attempts_next, {"error": str(e)}, correlation_id, idempotency_key)
            return "failed"
    finally:
        await redis_client.release_lock(lock_key)


async def _process_refund_initiation_once():
    queue_main = "q:pay:refund_initiation"
    queue_processing = f"{queue_main}:processing"

    message_json = await redis_client.claim_message(queue_main, queue_processing, timeout=1)
    if not message_json:
        await log_job_event(queue_main, action="refund", status="no_message")
        return "no_message"

    envelope_or_raw, payload, action, message_id, attempts, max_attempts, correlation_id, idempotency_key = _parse_message(message_json)
    lock_key = f"lock:{queue_main}:{message_id}"

    lock_ttl = getattr(QUEUE_POLICIES.get(queue_main, object()), 'lock_ttl_seconds', 120) or 120
    got_lock = await redis_client.set_lock(lock_key, ttl_seconds=lock_ttl)
    if not got_lock:
        await redis_client.remove_from_processing(queue_processing, message_json)
        await redis_client.queue_message(queue_main, json.loads(message_json))
        await log_job_event(queue_main, action=action or "refund", status="retry", message_id=message_id, attempts=attempts, info={"reason": "lock_unavailable"})
        await _db_log(queue_main, action or "refund", "retry", message_id, attempts, {"reason": "lock_unavailable"}, correlation_id, idempotency_key)
        return "retry"

    await log_job_event(queue_main, action=action or "refund", status="start", message_id=message_id, attempts=attempts)
    await _db_log(queue_main, action or "refund", "processing", message_id, attempts, None, correlation_id, idempotency_key)

    try:
        transaction_id = UUID(payload["transaction_id"]) if isinstance(payload.get("transaction_id"), str) else payload.get("transaction_id")
        amount = float(payload.get("amount", 0))
        await gateway.initiate_refund(transaction_id, amount, "trial_refund")
        logger.info("Processed refund initiation", transaction_id=str(transaction_id), amount=amount)
        await redis_client.remove_from_processing(queue_processing, message_json)
        await log_job_event(queue_main, action=action or "refund", status="success", message_id=message_id, attempts=attempts)
        await _db_log(queue_main, action or "refund", "success", message_id, attempts, None, correlation_id, idempotency_key)
        return "success"
    except Exception as e:
        attempts_next = attempts + 1
        policy = QUEUE_POLICIES.get(queue_main)
        max_try = (policy.max_retries if policy else 3)
        await redis_client.remove_from_processing(queue_processing, message_json)
        if max_attempts is not None:
            try:
                max_try = int(max_attempts)
            except Exception:
                pass
        if attempts_next <= max_try:
            if isinstance(envelope_or_raw, dict) and "payload" in envelope_or_raw:
                envelope_or_raw["attempts"] = attempts_next
                msg_for_delay = envelope_or_raw
            else:
                d = payload.copy()
                d["attempts"] = attempts_next
                msg_for_delay = d
            delay = _compute_backoff(queue_main, attempts_next)
            await redis_client.queue_delayed_message(queue_main, msg_for_delay, delay_seconds=delay)
            await log_job_event(queue_main, action=action or "refund", status="retry", message_id=message_id, attempts=attempts_next, info={"error": str(e), "delay": delay})
            await _db_log(queue_main, action or "refund", "retry", message_id, attempts_next, {"error": str(e), "delay": delay}, correlation_id, idempotency_key)
            return "retry"
        else:
            if not redis_client.client:
                await redis_client.connect()
            await redis_client.client.lpush(f"{queue_main}:failed", message_json)
            await log_job_event(queue_main, action=action or "refund", status="failed", message_id=message_id, attempts=attempts_next, info={"error": str(e)})
            await _db_log(queue_main, action or "refund", "failed", message_id, attempts_next, {"error": str(e)}, correlation_id, idempotency_key)
            return "failed"
    finally:
        await redis_client.release_lock(lock_key)


@celery_app.task(name="app.workers.tasks.process_webhook_processing", ignore_result=True)
def process_webhook_processing():
    """Process subscription update webhook queue messages (BRPOPLPUSH/lock/retry wrapper)."""
    try:
        return asyncio.run(_process_subscription_update_once())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_process_subscription_update_once())
        finally:
            loop.close()


@celery_app.task(name="app.workers.tasks.process_refund_initiation", ignore_result=True)
def process_refund_initiation():
    """Process refund initiation queue messages (BRPOPLPUSH/lock/retry wrapper)."""
    try:
        return asyncio.run(_process_refund_initiation_once())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_process_refund_initiation_once())
        finally:
            loop.close()


@celery_app.task(name="app.workers.tasks.pump_delayed_queues", ignore_result=True)
def pump_delayed_queues():
    """Move ready delayed messages back to main queues."""
    async def _run():
        moved1 = await redis_client.move_ready_delayed_to_main("q:pay:subscription_update")
        moved2 = await redis_client.move_ready_delayed_to_main("q:pay:refund_initiation")
        logger.info("Moved delayed messages", subscription_update=moved1, refund_initiation=moved2)
        return {"subscription_update": moved1, "refund_initiation": moved2}

    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_run())
        finally:
            loop.close()


@celery_app.task(name="app.workers.tasks.sweep_processing_queues", ignore_result=True)
def sweep_processing_queues():
    """Visibility sweeper: return orphaned items from :processing back to delayed or failed."""
    async def _run():
        if not redis_client.client:
            await redis_client.connect()
        queues = [
            "q:pay:subscription_update",
            "q:pay:refund_initiation",
        ]
        results = {}
        for main in queues:
            processing = f"{main}:processing"
            try:
                items = await redis_client.client.lrange(processing, 0, -1)
                swept = 0
                for msg in items:
                    # Determine lock key
                    try:
                        raw = json.loads(msg)
                    except Exception:
                        raw = {}
                    # Use message id if present, else hash
                    mid = (raw.get("id") if isinstance(raw, dict) else None) or _hash_message(msg)
                    lock_key = f"lock:{main}:{mid}"
                    exists = await redis_client.client.exists(lock_key)
                    if not exists:
                        # No lock -> consider orphaned; increment attempts and move to delayed or failed
                        try:
                            env, payload, action, message_id, attempts, max_attempts, corr, idem = _parse_message(msg)
                        except Exception:
                            env, payload, action, message_id, attempts, max_attempts, corr, idem = ({}, {}, None, mid, 0, None, None, None)
                        attempts_next = (attempts or 0) + 1
                        # Remove from processing
                        await redis_client.remove_from_processing(processing, msg)
                        policy = QUEUE_POLICIES.get(main)
                        max_try = (policy.max_retries if policy else 5)
                        if max_attempts is not None:
                            try:
                                max_try = int(max_attempts)
                            except Exception:
                                pass
                        if attempts_next <= max_try:
                            if isinstance(env, dict) and env.get("payload") is not None:
                                env["attempts"] = attempts_next
                                msg_for_delay = env
                            else:
                                d = (payload or {}).copy()
                                d["attempts"] = attempts_next
                                msg_for_delay = d
                            delay = _compute_backoff(main, attempts_next)
                            await redis_client.queue_delayed_message(main, msg_for_delay, delay_seconds=delay)
                        else:
                            await redis_client.client.lpush(f"{main}:failed", msg)
                        swept += 1
                results[main] = swept
            except Exception as e:
                logger.error(f"Sweeper error for {main}: {e}")
                results[main] = "error"
        logger.info("Processing sweeper results", results=json.dumps(results))
        return results

    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_run())
        finally:
            loop.close()