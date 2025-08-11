# Billing Backend System - Technical Documentation

## Introduction

The **Billing Backend System** is a production-ready, microservices-based platform designed for scalable subscription and payment management. Built with modern technologies and following industry best practices, this system provides comprehensive billing capabilities including user authentication, subscription management, payment processing, usage tracking, and webhook integrations.

This system demonstrates enterprise-grade architecture with **event-driven design**, **security-first approach**, and **horizontal scalability**. It's designed to handle high-volume transactions while maintaining data consistency and providing robust error handling.

---

## 📋 Table of Contents

- [🚀 Quick Start Guide](#-quick-start-guide)
- [💻 Technology Stack](#-technology-stack)
- [🏗️ System Architecture](#️-system-architecture)
- [🔧 Microservices Design](#-microservices-design)
- [🗄️ Database Design](#️-database-design)
- [🌐 API Design & Endpoints](#-api-design--endpoints)
- [📨 Message Queue Architecture](#-message-queue-architecture)
- [🔐 Security & Authentication](#-security--authentication)
- [⚙️ Configuration Management](#️-configuration-management)
- [🧪 Testing Strategy](#-testing-strategy)
- [🐳 Containerization & Deployment](#-containerization--deployment)
- [📊 Monitoring & Health Checks](#-monitoring--health-checks)
- [🔄 API Flow Examples](#-api-flow-examples)
- [📝 Submission Requirements](#-submission-requirements)

---

## 🚀 Quick Start Guide

### Prerequisites
- Docker and Docker Compose
- Git

### Local Development Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd billing-backend

# 2. Start the entire system (one command!)
./scripts/env-manager.sh -e development start

# 3. Verify services are running
docker-compose ps

# 4. Access the services
# Subscription Service: http://localhost:8001/docs
# Payment Service: http://localhost:8002/docs
# Flower (Queue Monitor): http://localhost:5555
```

### Service Endpoints
- **Subscription Service**: `http://localhost:8001` (Swagger: `/docs`)
- **Payment Service**: `http://localhost:8002` (Swagger: `/docs`)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **Flower Dashboard**: `http://localhost:5555`

### Environment Management
```bash
# Development environment
./scripts/env-manager.sh -e development start

# Staging environment
./scripts/env-manager.sh -e staging deploy

# Production environment
./scripts/env-manager.sh -e production deploy

# View logs
./scripts/env-manager.sh -e development logs

# Stop services
./scripts/env-manager.sh -e development stop
```

---

## 💻 Technology Stack

### Core Technologies
- **Backend Framework**: FastAPI (Python) with async/await support
- **Database**: PostgreSQL 15 with async SQLAlchemy ORM
- **Caching/Message Broker**: Redis 7
- **Task Queue**: Celery with Redis broker
- **Containerization**: Docker with Docker Compose orchestration

### Development & DevOps
- **API Documentation**: OpenAPI/Swagger with interactive documentation
- **Configuration Management**: Environment-specific configuration with validation
- **Monitoring**: Flower dashboard for queue monitoring
- **Testing**: Pytest with async support and comprehensive test coverage

### Security
- **Authentication**: JWT tokens with configurable expiration
- **Password Security**: bcrypt hashing with salt
- **Webhook Security**: HMAC-SHA256 signatures with timestamp validation
- **Input Validation**: Pydantic models with comprehensive validation

### Architecture Patterns
- **Microservices Architecture**: Domain-driven service separation
- **Event-Driven Design**: Asynchronous message processing
- **Repository Pattern**: Clean separation of data access
- **CQRS**: Command Query Responsibility Segregation
- **12-Factor App**: Configuration, logging, and deployment best practices

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
flowchart TB
    subgraph External["External"]
        Client["Client Applications"]
        Gateway["Payment Gateway"]
    end
    subgraph CoreServices["Core Services"]
        SubService["Subscription Service<br><small>(Port 8001)</small>"]
        PayService["Payment Service<br><small>(Port 8002)</small>"]
    end
    subgraph Background["Background Processing"]
        SubWorker["Subscription Worker"]
        PayWorker["Payment Worker"]
        Beat["Celery Beat Scheduler"]
    end
    subgraph DataLayer["Data Layer"]
        PostgreSQL[("PostgreSQL<br><small>(Port 5432)</small>")]
        Redis[("Redis<br><small>(Port 6379)</small>")]
    end
    
    Client <--> CoreServices
    Gateway <--> CoreServices
    Background <--> DataLayer
    CoreServices <--> DataLayer
```

### Key Design Principles

1. **Microservices Architecture**: Loosely coupled services with clear boundaries
2. **Event-Driven Design**: Asynchronous processing using message queues
3. **Security-First**: JWT authentication and HMAC-secured webhooks
4. **Scalability**: Horizontal scaling with Redis caching and queue processing
5. **Reliability**: Retry mechanisms, error handling, and transaction management
6. **Observability**: Comprehensive logging and health monitoring

---

## 🔧 Microservices Design

### Service Overview

| Service | Port | Responsibilities |
|---------|------|------------------|
| **Subscription Service** | 8001 | User auth, subscription management, usage tracking |
| **Payment Service** | 8002 | Payment processing, transaction management, refunds |

### Subscription Service Architecture

**API Layer**:
- Authentication endpoints (`/v1/auth/*`)
- Subscription management (`/v1/subscriptions/*`)
- Usage tracking (`/v1/usage/*`)
- Webhook handlers (`/v1/webhooks/*`)
- Health monitoring (`/v1/health/*`)

**Service Layer**:
- `AuthService`: User registration, login, JWT management
- `SubscriptionService`: Subscription lifecycle management
- `UsageService`: Feature usage tracking and limits
- `WebhookService`: Webhook processing and validation

**Repository Layer**:
- `UserRepository`: User data management
- `SubscriptionRepository`: Subscription data access
- `UsageRepository`: Usage statistics and tracking

### Payment Service Architecture

**API Layer**:
- Payment processing endpoints (`/v1/payments/*`)
- Gateway webhooks (`/v1/webhooks/*`)
- Health monitoring (`/v1/health/*`)

**Service Layer**:
- `PaymentService`: Transaction processing and management
- `GatewayService`: External payment gateway integration
- `WebhookService`: Webhook delivery and retry logic

**Integration Layer**:
- Mock Gateway Client (simulates real payment gateways)
- Webhook Delivery Client (HMAC-secured notifications)
- Subscription Service Client (inter-service communication)

---

## 🗄️ Database Design

### Schema Overview

The system uses a normalized PostgreSQL schema with proper foreign key relationships, indexes, and constraints.

```mermaid
erDiagram
    USERS ||--o{ SUBSCRIPTIONS : has
    PLANS ||--o{ SUBSCRIPTIONS : defines
    SUBSCRIPTIONS ||--o{ SUBSCRIPTION_EVENTS : logs
    SUBSCRIPTIONS ||--o{ TRANSACTIONS : pays_for
    TRANSACTIONS ||--|| GATEWAY_WEBHOOK_REQUESTS : receives
    TRANSACTIONS ||--o{ WEBHOOK_OUTBOUND_REQUESTS : emits
    USERS ||--o{ USER_USAGE : tracks

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
        decimal price
        varchar currency
        varchar billing_cycle
        jsonb features
        boolean is_active
        int trial_period_days
    }

    SUBSCRIPTIONS {
        uuid id PK
        int user_id FK
        int plan_id FK
        varchar status
        timestamptz start_date
        timestamptz end_date
        timestamptz canceled_at
    }

    TRANSACTIONS {
        uuid id PK
        uuid subscription_id FK
        decimal amount
        varchar currency
        varchar status
        varchar gateway_reference
        jsonb metadata
    }
```

### Key Database Features

1. **UUID Primary Keys**: For distributed system compatibility
2. **JSONB Fields**: Flexible metadata and feature storage
3. **Comprehensive Indexing**: Optimized query performance
4. **Audit Trails**: `created_at` and `updated_at` on all entities
5. **Foreign Key Constraints**: Data integrity enforcement
6. **Triggers**: Automatic timestamp updates

### Database Extensions
- **uuid-ossp**: UUID generation
- **Indexes**: Strategic indexing for performance
- **Constraints**: Data integrity and business rules

---

## 🌐 API Design & Endpoints

### RESTful Design Principles

- **Resource-oriented URLs**: Clear, intuitive endpoint structure
- **HTTP Verbs**: Proper use of GET, POST, PUT, DELETE
- **Status Codes**: Meaningful HTTP status codes
- **Error Handling**: Consistent error response format
- **Versioning**: API versioning with `/v1/` prefix

### Key Endpoints

#### Authentication
```
POST /v1/auth/register    # User registration
POST /v1/auth/login       # User authentication
GET  /v1/auth/me          # Current user info
```

#### Subscription Management
```
POST /v1/subscriptions/           # Create paid subscription
POST /v1/subscriptions/trial     # Create trial subscription
GET  /v1/subscriptions/me        # User subscriptions
PUT  /v1/subscriptions/{id}      # Update subscription
DELETE /v1/subscriptions/{id}    # Cancel subscription
```

#### Payment Processing
```
POST /v1/payments/process         # Process payment
POST /v1/payments/{id}/refund    # Initiate refund
GET  /v1/payments/history        # Payment history
```

#### Usage Tracking
```
POST /v1/usage/use               # Track feature usage
GET  /v1/usage/me                # Usage statistics
GET  /v1/usage/limits            # Usage limits
```

#### Health & Monitoring
```
GET  /v1/health/                 # Basic health check
GET  /v1/health/detailed         # Comprehensive health check
```

### Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": { /* response data */ },
  "message": "Operation completed successfully",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

Error responses:
```json
{
  "success": false,
  "error": "Error description",
  "details": { /* error details */ },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 📨 Message Queue Architecture

### Queue System Overview

The system uses **Redis-based message queues** with **Celery** for robust asynchronous processing, featuring retry logic, dead letter queues, and comprehensive monitoring.

### Standardized Queue Naming

**Subscription Service Queues**:
- `q:sub:payment_initiation` - Payment orchestration
- `q:sub:trial_payment` - Trial payment processing
- `q:sub:plan_change` - Plan upgrades/downgrades
- `q:sub:usage_sync` - Usage data synchronization

**Payment Service Queues**:
- `q:pay:subscription_update` - Subscription status updates
- `q:pay:refund_initiation` - Refund processing

### Queue Management Structure

For each queue, the system maintains:
- **Main Queue**: `q:<domain>:<name>`
- **Processing Queue**: `q:<domain>:<name>:processing`
- **Delayed Queue**: `q:<domain>:<name>:delayed`
- **Failed Queue**: `q:<domain>:<name>:failed`

### Message Envelope Standard

All messages use a standardized envelope:

```json
{
  "id": "uuid",
  "action": "initial|trial|renewal|upgrade|downgrade|refund",
  "correlation_id": "subscription_id",
  "idempotency_key": "unique_key",
  "created_at": "ISO timestamp",
  "attempts": 0,
  "max_attempts": 3,
  "payload": { /* message-specific data */ }
}
```

### Processing Pattern

1. **Atomic Claim**: `BRPOPLPUSH` for guaranteed message delivery
2. **Lock Acquisition**: `SETNX` with TTL for processing locks
3. **Handler Execution**: Business logic processing
4. **Retry Logic**: Exponential backoff for failed messages
5. **Dead Letter**: Failed messages after max retries

### Queue Policies

```python
{
  "max_retries": 3,
  "base_delay_seconds": 60,
  "backoff_multiplier": 2.0,
  "max_delay_seconds": 3600,
  "jitter_seconds": 10,
  "lock_ttl_seconds": 120
}
```

---

## 🔐 Security & Authentication

### Authentication System

**JWT-Based Authentication**:
- Secure token generation with configurable expiration
- Token validation middleware on protected endpoints
- User session management

**Password Security**:
- bcrypt hashing with salt rounds
- Strong password requirements
- Secure password reset flows

### Webhook Security

**HMAC-SHA256 Signatures**:
- All webhooks signed with shared secrets
- Timestamp validation to prevent replay attacks
- Signature verification on receiving services

```python
# Webhook signature verification
def verify_webhook_signature(request):
    signature = request.headers.get("X-Webhook-Signature")
    timestamp = request.headers.get("X-Webhook-Timestamp")
    payload = f"{timestamp}.{request.body}"
    expected = hmac_sha256(payload, secret)
    return hmac.compare_digest(signature, expected)
```

### Input Validation

**Pydantic Models**: Comprehensive input validation and sanitization
- Type checking and conversion
- Length and format validation
- Business rule validation

### Security Headers

- CORS configuration for cross-origin requests
- Security headers for XSS and CSRF protection
- Rate limiting on sensitive endpoints

---

## ⚙️ Configuration Management

### Modern Configuration System

The system implements **12-Factor App principles** with environment-specific configuration management.

### Configuration Structure

```
config/
├── environments/
│   ├── base.env              # Shared configuration
│   ├── development.env       # Development settings
│   ├── staging.env          # Staging settings
│   └── production.env       # Production settings
├── config_loader.py         # Centralized loader
└── README.md               # Documentation
```

### Environment Separation

**Development**:
- Local services (localhost URLs)
- Included secrets for convenience
- Debug mode enabled
- Hot reloading

**Staging**:
- Internal service URLs
- Environment variable substitution
- Production-like settings
- Limited debug information

**Production**:
- Secure secret management
- Resource limits and health checks
- Performance optimizations
- Comprehensive monitoring

### Configuration Features

1. **Hierarchical Loading**: Base + environment-specific overrides
2. **Type Validation**: Pydantic-based configuration validation
3. **Secret Management**: Environment variable substitution for secrets
4. **Environment Verification**: Prevents configuration mixing

---

## 🧪 Testing Strategy

### Testing Pyramid

**Unit Tests**:
- Service layer business logic
- Repository layer data access
- Utility functions and helpers
- Message processing logic

**Integration Tests**:
- API endpoint testing
- Database integration
- Redis queue operations
- Webhook processing flows

**End-to-End Tests**:
- Complete user journeys
- Cross-service communication
- Payment processing flows
- Error handling scenarios

### Testing Infrastructure

**Test Database**: Isolated test database with cleanup
**Mock Services**: Payment gateway mocking
**Fixtures**: Reusable test data and scenarios
**Async Testing**: Proper async/await test support

### Test Coverage Areas

1. **Authentication Flows**: Registration, login, token validation
2. **Subscription Lifecycle**: Creation, activation, cancellation
3. **Payment Processing**: Success/failure scenarios, refunds
4. **Usage Tracking**: Limits, overages, resets
5. **Webhook Processing**: Signature verification, retry logic
6. **Error Handling**: Edge cases and error scenarios

---

## 🐳 Containerization & Deployment

### Docker Architecture

The system uses **multi-stage Docker builds** for optimized container images with separate development and production configurations.

### Docker Compose Environments

**Development** (`docker-compose.development.yml`):
- Volume mounts for hot reloading
- Development-friendly settings
- Local service networking
- Debug capabilities

**Production** (`docker-compose.production.yml`):
- Optimized images without development dependencies
- Resource limits and health checks
- External network configuration
- Multi-replica deployment

### Container Services

| Service | Description | Health Check |
|---------|-------------|-------------|
| `subscription-service` | Main subscription API | HTTP `/v1/health/` |
| `payment-service` | Payment processing API | HTTP `/v1/health/` |
| `subscription-worker` | Background task processor | Celery status |
| `payment-worker` | Payment queue processor | Celery status |
| `celery-beat` | Task scheduler | Process health |
| `postgres` | Primary database | Database connection |
| `redis` | Cache and message broker | Redis ping |
| `flower` | Queue monitoring dashboard | HTTP interface |

### Environment Management Script

```bash
# Single script for all environment operations
./scripts/env-manager.sh -e [environment] [action]

# Examples:
./scripts/env-manager.sh -e development start
./scripts/env-manager.sh -e staging deploy
./scripts/env-manager.sh -e production validate
```

---

## 📊 Monitoring & Health Checks

### Health Check System

**Multi-Level Health Checks**:
- Basic: Service availability (`/v1/health/`)
- Detailed: Component health (`/v1/health/detailed`)
- Deep: End-to-end functionality

### Component Monitoring

```json
{
  "status": "healthy",
  "service": "subscription-service",
  "timestamp": "2024-01-01T00:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5,
      "details": "Connection successful"
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2,
      "details": "Cache operational"
    },
    "queues": {
      "status": "healthy",
      "details": {
        "subscription_tasks": {"pending": 0, "processing": 1},
        "payment_tasks": {"pending": 2, "processing": 0}
      }
    }
  }
}
```

### Queue Monitoring

**Flower Dashboard**: Real-time queue and worker monitoring
- Task status and history
- Worker performance metrics
- Queue depth monitoring
- Failed task analysis

### Logging Strategy

**Structured Logging**: JSON-formatted logs with correlation IDs
**Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
**Audit Trails**: Comprehensive business event logging

---

## 🔄 API Flow Examples

### Complete User Journey: Trial to Paid Subscription

#### 1. User Registration
```bash
POST /v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user_id": 1,
    "email": "user@example.com"
  }
}
```

#### 2. Create Trial Subscription
```bash
POST /v1/subscriptions/trial
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "trial_plan_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1,
    "plan_id": 1,
    "status": "trial",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T00:00:00Z",
    "plan": {
      "name": "Basic Trial",
      "features": {
        "api_calls": {"limit": 1000},
        "storage": {"limit": "1GB"}
      }
    }
  }
}
```

#### 3. Track Feature Usage
```bash
POST /v1/usage/use
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "feature_name": "api_calls",
  "delta": 1
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "feature_name": "api_calls",
    "current_usage": 1,
    "limit": 1000,
    "remaining": 999,
    "reset_at": "2024-02-01T00:00:00Z"
  }
}
```

#### 4. Upgrade to Paid Plan
```bash
POST /v1/subscriptions/
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "plan_id": 2
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "pending",
    "payment_required": true,
    "amount": 29.99,
    "currency": "USD"
  }
}
```

#### 5. Process Payment
```bash
POST /v1/payments/process
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "subscription_id": "550e8400-e29b-41d4-a716-446655440001",
  "amount": 29.99,
  "currency": "USD",
  "card_number": "4111111111111111",
  "card_expiry": "12/25",
  "card_cvv": "123",
  "cardholder_name": "John Doe"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "transaction_id": "550e8400-e29b-41d4-a716-446655440002",
    "status": "success",
    "amount": 29.99,
    "currency": "USD",
    "gateway_reference": "tx_1234567890"
  }
}
```

### Webhook Flow: Payment → Subscription Update

#### Payment Service to Subscription Service Webhook
```bash
POST /v1/webhooks/payment
X-Webhook-Signature: sha256=abcdef123456...
X-Webhook-Timestamp: 1640995200
Content-Type: application/json

{
  "event_id": "evt_1234567890",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440002",
  "subscription_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "success",
  "amount": 29.99,
  "currency": "USD"
}
```

**Subscription Service Response:**
```json
{
  "success": true,
  "message": "Webhook processed successfully"
}
```

This billing backend system represents a **production-ready, enterprise-grade solution** that demonstrates modern software architecture patterns, security best practices, and operational excellence. The system is designed for scalability, maintainability, and developer productivity while ensuring robust transaction processing and data integrity. 