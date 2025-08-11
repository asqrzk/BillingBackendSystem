# Async Messaging & Queue Architecture

## 1. Purpose and Goals

This document describes the asynchronous messaging refactor for the billing system, focusing on subscription lifecycle events and payment integrations. The goals are:

- Robust, observable, and scalable processing of background work
- Clear ownership and standardized queue naming across domains
- Consistency via message envelopes, idempotency, and policies (retries/backoff/locks)
- Fault-tolerance with atomic claims (BRPOPLPUSH), per-message locks, delayed retries, and visibility guarantees
- Practical observability using Redis job logs and Flower, with an eventual DB-backed JobLog

## 2. Scope (Current vs Planned)

- Implemented now
  - Standard queue names per domain (q:sub:* and q:pay:*)
  - Message envelope (shared schema) and envelope-compatible workers
  - Payment worker: BRPOPLPUSH claim, locks, delayed retries, failed DLQ, backoff via policies
  - Subscription worker pollers: refactored to use the same BRPOPLPUSH+lock wrappers
  - Lightweight job logging to Redis (q:log:jobs) on payment side; wrappers ready for extension
  - HMAC-signed webhooks (payment → subscription) with immediate best-effort send + queued delivery
  - `PaymentWebhookRequest` model aligned with DB schema

- Planned next
  - DB-backed JobLog models and migrations (both services)
  - Visibility sweeper (return orphaned processing items when lock/TTL expires)
  - Policy-driven wrappers for all subscription workers; structured job logging
  - Admin/ops endpoints for JobLog slices and queue health

## 3. Standardized Queues

- Subscription service (consumes)
  - `q:sub:payment_initiation` (initial/renewal/upgrade/downgrade orchestration)
  - `q:sub:trial_payment`
  - `q:sub:plan_change`
  - `q:sub:usage_sync`

- Payment service (consumes)
  - `q:pay:subscription_update` (payment → subscription updates; worker posts HTTP webhook)
  - `q:pay:refund_initiation`

Queue variants (per-queue):
- Main: `q:<domain>:<name>`
- Processing: `q:<domain>:<name>:processing`
- Delayed: `q:<domain>:<name>:delayed` (ZSET scored by retry_at)
- Failed: `q:<domain>:<name>:failed`

Locks:
- `lock:<queue_main>:<message_id>` with TTL from policy

Job logs (Redis, payment side now):
- `q:log:jobs` (LPUSH structured JSON entries)

## 4. Message Envelope

A shared envelope that standardizes metadata and idempotency.

- Fields
  - `id`: UUID (auto)
  - `action`: string (e.g., initial|trial|renewal|upgrade|downgrade|refund)
  - `correlation_id`: optional (e.g., subscription_id)
  - `idempotency_key`: optional (e.g., payment event_id)
  - `created_at`: ISO timestamp (auto)
  - `attempts`: integer (defaults 0)
  - `max_attempts`: optional per message
  - `payload`: dict with message-specific data

- Compatibility
  - Workers accept both envelope and raw dicts (for progressive rollout). When raw, wrappers synthesize required fields.

## 5. Queue Policies

Defined in `app/core/queue_policies.py` per service, keyed by queue name. Used by wrappers to control retries.

- Parameters
  - `max_retries`: default cap (e.g., 5)
  - `base_delay_seconds`: initial backoff (e.g., 60s)
  - `backoff_multiplier`: e.g., 2.0
  - `max_delay_seconds`: cap (e.g., 3600s)
  - `jitter_seconds`: randomized jitter in seconds
  - `lock_ttl_seconds`: lock lifetime (e.g., 120s)
  - `visibility_timeout_seconds`: processing TTL for sweeper (planned)

## 6. Processing Pattern

Per queue, each worker tick follows this pattern:

1) Claim atomically via `BRPOPLPUSH q:main → q:processing`
2) Acquire lock `SETNX lock:{queue}:{id}` with TTL
3) Invoke handler
4) On success: `LREM q:processing message` (ack) and log success
5) On retryable error: increment `attempts`, compute delay from policy, enqueue to `q:main:delayed` (ZADD score=retry_at), log retry
6) On failure (exceeded attempts): LPUSH to `q:main:failed`, log failed
7) Always release lock

Beat/maintenance:
- Pump delayed: move ready messages `q:main:delayed(score ≤ now)` back to `q:main`
- Visibility sweeper: scan `q:processing`, if lock is missing/expired, remove item from processing and move to delayed (updating attempts) or to failed when attempts exceed policy
- Cleanup: trim old failed items, monitor queue depth, and alert

## 7. Service Behaviors

### 7.1 Payment Service

- Producers
  - `PaymentService._queue_subscription_notification` constructs webhook payload, wraps into envelope (action = trial|renewal|initial) and enqueues to `q:pay:subscription_update`. Also sends immediate best-effort HTTP webhook to subscription for low-latency updates.
  - Trial success also enqueues `q:pay:refund_initiation` (envelope compat supported by worker).

- Consumers (Workers)
  - `process_webhook_processing` (q:pay:subscription_update)
    - BRPOPLPUSH claim; lock
    - POST signed webhook to subscription `/v1/webhooks/payment`
    - Retry with policy, delayed zset; failed DLQ
    - Redis job logs at start/success/retry/failed; DB JobLogs persisted
  - `process_refund_initiation` (q:pay:refund_initiation)
    - Same wrapper pattern; calls `MockGatewayService.initiate_refund`

- Beat
  - `pump_delayed_queues` (moves delayed → main)
  - `sweep_processing_queues` (returns orphans → delayed/failed per policy)

### 7.2 Subscription Service

- Producers
  - Subscription producers enqueue envelopes (where implemented) to `q:sub:payment_initiation` and `q:sub:trial_payment`.

- Consumers (Workers)
  - Queue pollers refactored to wrappers using BRPOPLPUSH + lock + delayed requeue for:
    - `q:sub:payment_initiation` → `process_payment_initiation`
    - `q:sub:trial_payment` → `process_trial_payment`
    - `q:sub:plan_change` → `process_plan_change`
    - `q:sub:usage_sync` → `process_usage_sync`
  - Existing task handlers remain unchanged and continue to be called via Celery `apply_async` from wrappers (separation between queue runtime and business handlers).

- Webhook Handling
  - `/v1/webhooks/payment` verifies HMAC signature and processes synchronously in `WebhookService`. No queue on subscription side for webhooks (by design), because payment worker already retries delivery.

- Beat
  - `process_delayed_queues` (moves delayed → main)
  - `sweep_processing_queues` (returns orphans → delayed/failed per policy)

## 8. Security (Webhooks)

- HMAC-SHA256 verification in subscription service
  - Headers: `X-Webhook-Timestamp` and `X-Webhook-Signature`
  - Signed payload: `timestamp.payload_json` with shared secret
  - Tolerance window via `WEBHOOK_TOLERANCE_SECONDS`
- Payment worker uses the same scheme when delivering webhooks

## 9. Configuration

- Redis URL (broker and backend for workers): `REDIS_URL`
- Queue policies via `app/core/queue_policies.py` (can be parameterized via env if needed)
- HMAC config: `WEBHOOK_SIGNING_SECRET`, `WEBHOOK_TOLERANCE_SECONDS`
- Payment → Subscription URLs: `SUBSCRIPTION_SERVICE_URL`

## 10. Observability

- Flower for Celery worker/task visibility
- Redis job logs (payment side now) in `q:log:jobs`
  - Entries include: timestamp, queue, action, status, message_id, attempts, info
- DB JobLog (payment side) persists processing lifecycle to `job_logs` table (queue, action, status, attempts, correlation/idempotency)
- Planned: DB-backed `JobLog` for subscription service and dashboards with filters

## 11. Failure Handling & Idempotency

- Idempotency
  - Envelopes can carry `idempotency_key` (e.g., payment event_id); handlers should be idempotent on that key where possible.
- Retries
  - Backoff computed from queue policy; jitter added to avoid thundering herds
  - Max attempts from message or policy
- Dead-letter
  - Messages exceeding attempts go to `q:<queue>:failed`
- Visibility
  - Implemented visibility sweeper: `:processing` list + lock TTL + sweeper requeues orphans to delayed/failed, preventing starvation and ensuring urgent work progresses

## 12. Backward Compatibility

- Workers accept both raw dict messages and envelopes
- Some legacy queue names are not dual-consumed to reduce complexity (explicitly decided); producers have been updated to new names

## 13. Data Model Notes

- `payment_webhook_requests`
  - Model realigned to DB: integer PK, `event_id` unique, `payload` JSONB, `processed`, `processed_at`, `error_message` (text), `retry_count`, `created_at`, `updated_at` (trigger)
  - Extensible to include `action` or attempts tracking in future migration if needed
- Planned: `job_logs` table per service
  - Columns: id, queue, message_id, correlation_id, idempotency_key, status, attempts, last_error, next_retry_at, action, created_at, updated_at
  - Indexes: (queue, status), (correlation_id), (idempotency_key)

## 14. Operational Playbook

- Start/Restart
  - `docker compose up -d` (ensure Redis/DB healthy)
  - Workers require event emission (`-E`) for Flower visibility
  - Payment beat schedules webhook processing + delayed pump
  - Subscription beat schedules delayed processing and cleanup

- Inspect Queues
  - `LLEN q:pay:subscription_update`, `LLEN q:pay:subscription_update:processing`, `ZCARD q:pay:subscription_update:delayed`
  - Same for `q:sub:*` queues

- Inspect Job Logs (Redis)
  - `LRANGE q:log:jobs 0 50`

- Failure Drill
  - Trigger a retryable failure; confirm message moves: main → processing → delayed → main, with attempts incrementing
  - Confirm DLQ path after max attempts

## 15. Testing Strategy

- Unit-test wrappers (claim, lock, retry decision, delayed enqueue)
- Integration tests across services for:
  - Trial creation → payment → webhook delivery → status update
  - Renewal path via `q:sub:payment_initiation`
  - Refund initiation path
- Signature verification tests for webhooks (valid/invalid, stale/future timestamps)

## 16. Future Work

- Extend visibility sweeper with processing TTL checks in addition to lock presence
- Formalize JobLog DB for subscription service; add dashboards and correlation filters
- Metrics/alerts for queue depths, failure rates, retry latencies, webhook latencies
- Standardize envelope across all producers in both services

## 17. Appendix: Wrapper Pseudocode

```text
loop tick:
  msg = BRPOPLPUSH(q:main → q:processing)
  if !msg: return no_message
  id = envelope.id || hash(msg)
  lock = SETNX(lock:{queue}:{id}, TTL)
  if !lock:
    LREM(q:processing, msg)
    LPUSH(q:main, msg)
    return retry
  try:
    handle(msg)
    LREM(q:processing, msg)
    return success
  except:
    attempts++
    if attempts <= max:
      ZADD(q:delayed, retry_at, msg_with_attempts)
      LREM(q:processing, msg)
      return retry
    else:
      LPUSH(q:failed, msg)
      LREM(q:processing, msg)
      return failed
  finally:
    DEL lock
```

---

This architecture establishes clear domain ownership of queues, robust processing semantics, and a consistent envelope/policy approach. It is deliberately incremental: wrappers and policies are in place; deeper observability (DB JobLog) and visibility management can be added without disrupting current flows. 

## 18. Recent Updates

- Added BRPOPLPUSH + lock + delayed requeue wrappers to both payment and subscription workers.
- Implemented visibility sweepers and scheduled them (payment and subscription) to reclaim orphaned processing items.
- Enveloped payment webhook notifications and added immediate HTTP delivery for low latency.
- Persist DB JobLogs on the payment side; Redis job logs retained for fast inspection.
- Subscription webhook handling remains synchronous by design; payment worker handles delivery retries. 