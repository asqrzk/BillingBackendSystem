## Database Schema (Billing System)

This document describes the relational schema used by the billing system. The database is PostgreSQL and is used by two services: `subscription-service` and `payment-service`.

- Engine: PostgreSQL (tested with 15)
- ORM: SQLAlchemy (async) with a shared `Base` and `BaseModel` that adds timestamp columns
- Extension: `uuid-ossp` (for UUID generation)
- Schema sources: SQL initialization scripts and SQLAlchemy models

### Conventions
- Unless specified, timestamps are timezone-aware (`TIMESTAMPTZ`).
- `BaseModel` rows include auditing columns: `created_at` (default now) and `updated_at` (default now, updated via ORM and triggers).
- Some tables intentionally omit `updated_at` (e.g., `payment_webhook_requests`).

### ER Diagram
```mermaid
erDiagram
    USERS ||--o{ SUBSCRIPTIONS : has
    PLANS ||--o{ SUBSCRIPTIONS : has
    SUBSCRIPTIONS ||--o{ SUBSCRIPTION_EVENTS : has
    SUBSCRIPTIONS ||--o{ TRANSACTIONS : has
    TRANSACTIONS ||--|| GATEWAY_WEBHOOK_REQUESTS : receives
    TRANSACTIONS ||--o{ WEBHOOK_OUTBOUND_REQUESTS : emits
    USERS ||--o{ USER_USAGE : has

    USERS {
        int id PK
        varchar email UNIQUE
        varchar password_hash
        varchar first_name
        varchar last_name
        timestamptz created_at
        timestamptz updated_at
    }

    PLANS {
        int id PK
        varchar name
        text description
        decimal price
        varchar currency
        varchar billing_cycle
        int trial_period_days
        boolean is_active
        jsonb features
        timestamptz created_at
        timestamptz updated_at
    }

    SUBSCRIPTIONS {
        uuid id PK
        int user_id FK
        int plan_id FK
        varchar status
        timestamptz start_date
        timestamptz end_date
        timestamptz canceled_at
        timestamptz created_at
        timestamptz updated_at
    }

    SUBSCRIPTION_EVENTS {
        int id PK
        uuid subscription_id FK
        varchar event_type
        uuid transaction_id
        int old_plan_id FK
        int new_plan_id FK
        timestamptz effective_at
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    PAYMENT_WEBHOOK_REQUESTS {
        int id PK
        varchar event_id UNIQUE
        jsonb payload
        boolean processed
        timestamptz processed_at
        text error_message
        int retry_count
        timestamptz created_at
    }

    TRANSACTIONS {
        uuid id PK
        uuid subscription_id
        decimal amount
        varchar currency
        varchar status
        varchar gateway_reference
        text error_message
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    GATEWAY_WEBHOOK_REQUESTS {
        int id PK
        uuid transaction_id UNIQUE
        jsonb payload
        boolean processed
        timestamptz processed_at
        timestamptz created_at
        timestamptz updated_at
    }

    WEBHOOK_OUTBOUND_REQUESTS {
        int id PK
        uuid transaction_id
        varchar url
        jsonb payload
        int response_code
        text response_body
        int retry_count
        timestamptz completed_at
        timestamptz created_at
        timestamptz updated_at
    }

    USER_USAGE {
        int id PK
        int user_id FK
        varchar feature_name
        int usage_count
        timestamptz reset_at
        timestamptz created_at
        timestamptz updated_at
    }

    JOB_LOGS {
        int id PK
        varchar service
        varchar queue
        varchar message_id
        varchar correlation_id
        varchar idempotency_key
        varchar action
        varchar status
        int attempts
        text last_error
        timestamp next_retry_at
        timestamp created_at
        timestamp updated_at
    }
```

---

## Tables

### users
Represents application users. Used by subscription service.

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `email` VARCHAR(255) NOT NULL UNIQUE
- `password_hash` VARCHAR(255) NULL
- `first_name` VARCHAR(100) NULL
- `last_name` VARCHAR(100) NULL
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- `idx_users_email` on (`email`)

---

### plans
Catalog of subscription plans.

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `name` VARCHAR(100) NOT NULL
- `description` TEXT NULL
- `price` DECIMAL(10,2) NOT NULL DEFAULT 0.00
- `currency` VARCHAR(3) NOT NULL DEFAULT 'AED'
- `billing_cycle` VARCHAR(20) NOT NULL DEFAULT 'monthly'  // monthly, yearly
- `trial_period_days` INTEGER NOT NULL DEFAULT 0
- `is_active` BOOLEAN NOT NULL DEFAULT true
- `features` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- (testing script) `idx_plans_name` on (`name`)
- (testing script) GIN index on `(features->'limits')`
- (testing script) GIN index on `(features->'features')`

---

### subscriptions
User subscriptions to plans.

Columns:
- `id` UUID PRIMARY KEY DEFAULT uuid_generate_v4()
- `user_id` INTEGER NOT NULL REFERENCES `users(id)` ON DELETE CASCADE
- `plan_id` INTEGER NOT NULL REFERENCES `plans(id)` ON DELETE RESTRICT
- `status` VARCHAR(20) NOT NULL DEFAULT 'pending'  // pending, active, trial, past_due, cancelled, revoked
- `start_date` TIMESTAMPTZ NOT NULL
- `end_date` TIMESTAMPTZ NOT NULL
- `canceled_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- `idx_subscriptions_user_id` on (`user_id`)
- `idx_subscriptions_status` on (`status`)
- `idx_subscriptions_end_date` on (`end_date`)

Relationships:
- Many subscriptions per `users(id)`
- Many subscriptions per `plans(id)`

---

### subscription_events
Audit trail for subscription lifecycle and plan changes.

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `subscription_id` UUID NOT NULL REFERENCES `subscriptions(id)` ON DELETE CASCADE
- `event_type` VARCHAR(50) NOT NULL
- `transaction_id` UUID NULL
- `old_plan_id` INTEGER NULL REFERENCES `plans(id)`
- `new_plan_id` INTEGER NULL REFERENCES `plans(id)`
- `effective_at` TIMESTAMPTZ NULL
- `metadata` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- `idx_subscription_events_subscription_id` on (`subscription_id`)
- `idx_subscription_events_event_type` on (`event_type`)

Relationships:
- Many events per `subscriptions(id)`
- Optional links to old/new `plans(id)`

---

### payment_webhook_requests
Inbound webhook requests from the payment service (subscription service side). This table intentionally omits `updated_at`.

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `event_id` VARCHAR(255) NOT NULL UNIQUE
- `payload` JSONB NOT NULL
- `processed` BOOLEAN NOT NULL DEFAULT FALSE
- `processed_at` TIMESTAMPTZ NULL
- `error_message` TEXT NULL
- `retry_count` INTEGER NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ DEFAULT now() NULL

Indexes:
- `idx_webhook_requests_event_id` on (`event_id`)
- `idx_webhook_requests_processed` on (`processed`)

---

### transactions
Payment transactions (payment service).

Columns:
- `id` UUID PRIMARY KEY DEFAULT uuid_generate_v4()
- `subscription_id` UUID NULL  // optionally links to `subscriptions(id)`
- `amount` DECIMAL(10,2) NOT NULL
- `currency` VARCHAR(3) NOT NULL DEFAULT 'AED'
- `status` VARCHAR(20) NOT NULL  // e.g., pending, processing, success, failed, refund_*
- `gateway_reference` VARCHAR(100) NULL
- `error_message` TEXT NULL
- `metadata` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- `idx_transactions_subscription_id` on (`subscription_id`)
- `idx_transactions_status` on (`status`)
- `idx_transactions_gateway_reference` on (`gateway_reference`)

---

### gateway_webhook_requests
Inbound webhooks from the external payment gateway (payment service).

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `transaction_id` UUID NOT NULL UNIQUE  // one webhook per transaction
- `payload` JSONB NOT NULL
- `processed` BOOLEAN NOT NULL DEFAULT FALSE
- `processed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Constraints:
- Unique constraint `_gateway_webhook_transaction_uc` on (`transaction_id`) (implies unique index)

---

### webhook_outbound_requests
Outbound webhooks sent from payment service to subscription service.

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `transaction_id` UUID NOT NULL
- `url` VARCHAR(500) NOT NULL
- `payload` JSONB NOT NULL
- `response_code` INTEGER NULL
- `response_body` TEXT NULL
- `retry_count` INTEGER NOT NULL DEFAULT 0
- `completed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Indexes:
- (ORM) index hints exist on `transaction_id`

---

### user_usage
Feature usage counters per user and feature (subscription service).

Columns:
- `id` INTEGER PRIMARY KEY (SERIAL)
- `user_id` INTEGER NOT NULL REFERENCES `users(id)` ON DELETE CASCADE
- `feature_name` VARCHAR(50) NOT NULL
- `usage_count` INTEGER NOT NULL DEFAULT 0
- `reset_at` TIMESTAMPTZ NOT NULL
- `created_at` TIMESTAMPTZ DEFAULT now() NOT NULL
- `updated_at` TIMESTAMPTZ DEFAULT now() NOT NULL

Constraints:
- Unique constraint `unique_user_feature` on (`user_id`, `feature_name`)

Indexes:
- `idx_user_usage_user_id` on (`user_id`)
- `idx_user_usage_feature_name` on (`feature_name`)
- `idx_user_usage_reset_at` on (`reset_at`)

---

### job_logs
Shared table for async job processing logs. Created by both services' models.

Columns:
- `id` INTEGER PRIMARY KEY
- `service` VARCHAR(50) NOT NULL  // e.g., payment, subscription
- `queue` VARCHAR(100) NOT NULL
- `message_id` VARCHAR(100) NULL
- `correlation_id` VARCHAR(100) NULL
- `idempotency_key` VARCHAR(100) NULL
- `action` VARCHAR(50) NULL
- `status` VARCHAR(20) NOT NULL  // e.g., received, processing, success, retry, failed, dead
- `attempts` INTEGER NOT NULL DEFAULT 0
- `last_error` TEXT NULL
- `next_retry_at` TIMESTAMP NULL
- `created_at` TIMESTAMP NOT NULL DEFAULT now()
- `updated_at` TIMESTAMP NOT NULL DEFAULT now()

Indexes:
- (ORM) indexes on `queue`, `message_id`, `correlation_id`, `idempotency_key`, `status`

---

## Triggers
`update_updated_at_column` trigger keeps `updated_at` synchronized on updates. Applied to:
- users
- plans
- subscriptions
- subscription_events
- payment_webhook_requests
- transactions
- gateway_webhook_requests
- webhook_outbound_requests
- user_usage

## Extensions
- `uuid-ossp`: required for `uuid_generate_v4()` defaults

## Views (testing only)
- `plan_limits_summary`: convenience view for verifying plan limits; defined in the testing init script.

## Notes
- Production DDL is primarily sourced from `scripts/init-db.sql`. The testing script `scripts/init-db-testing.sql` contains slight variations (e.g., additional indexes, different defaults) for fast test cycles.
- SQLAlchemy models in `subscription-service/app/models` and `payment-service/app/models` reflect and enforce many of these schema rules at the application layer. 