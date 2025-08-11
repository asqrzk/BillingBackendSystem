# Billing Backend System - Technical Documentation

## Introduction

The **Billing Backend System** is a microservices-based platform designed for scalable subscription and payment management. Built with modern technologies and following industry best practices, this system provides comprehensive billing capabilities including user authentication, subscription management, payment processing, usage tracking, and webhook integrations.

This system demonstrates enterprise-grade architecture with **event-driven design**, **security-first approach**, and **horizontal scalability**. It's designed to handle high-volume transactions while maintaining data consistency and providing robust error handling.

---

## Table of Contents

- [ Quick Start Guide](#-quick-start-guide)
- [ Technology Stack](#-technology-stack)
- [ System Architecture](#️-system-architecture)
- [ Microservices Design](#-microservices-design)
- [ Database Design](#️-database-design)
- [ API Design & Endpoints](#-api-design--endpoints)
- [ Message Queue Architecture](#-message-queue-architecture)
- [ Security & Authentication](#-security--authentication)
- [ Configuration Management](#️-configuration-management)
- [ Testing Strategy](#-testing-strategy)
- [ Containerization & Deployment](#-containerization--deployment)
- [ Monitoring & Health Checks](#-monitoring--health-checks)
- [ API Flow Examples](#-api-flow-examples)
- [ Submission Requirements](#-submission-requirements)

---

## Quick Start Guide


### Local Development Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd billing-backend

# 2. Using Docker Compose
docker compose -f docker-compose.testing.yml up --build 

# 3. Verify services are running
docker-compose ps

# 4. Access the services
# Subscription Service: http://localhost:8001/docs
# Payment Service: http://localhost:8002/docs
# Flower (Queue Monitor): http://localhost:5555
```

Please note that the seed data for this env is placed at [scripts/init-db-testing.sql](billing-backend/scripts/init-db-testing.sql)

### Service Endpoints
- **Subscription Service**: `http://localhost:8001` (Swagger: `/docs`)
- **Payment Service**: `http://localhost:8002` (Swagger: `/docs`)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **Flower Dashboard**: `http://localhost:5555`

![swagger](billing-backend/docs/images/swagger.png)

---

##  Technology Stack

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

---

##  System Architecture

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
6. **Observability**: Comprehensive logging and health monitoring. Uses Flower Dashboard & Sweeping Monitoring to handle Celery load

---

##  Microservices Design

### Service Overview

```mermaid
classDiagram
    class SubscriptionService {
        Port: 8001
        Responsibilities:
        - User auth
        - Subscription management
        - Usage tracking
    }

    class PaymentService {
        Port: 8002
        Responsibilities:
        - Payment processing
        - Transaction management
        - Refunds
    }
```

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

```mermaid
graph TB
    subgraph "Payment Service (Port 8002)"
        subgraph "API Layer"
            PayAPI[Payment Endpoints<br/>/v1/payments/*]
            PayHealthAPI[Health Endpoints<br/>/v1/health/*]
        end
        
        subgraph "Middleware"
            PayAuthMW[JWT Authentication]
            PayCORS[CORS Middleware]
            PayErrorMW[Error Handler]
        end
        
        subgraph "Service Layer"
            PaySvc[PaymentService]
            PayWebhookSvc[WebhookService]
            PayHealthSvc[HealthService]
        end
        
        subgraph "Integration Layer"
            MockGateway[Mock Gateway Client]
            WebhookClient[Webhook Delivery Client]
            SubServiceClient[Subscription Service Client]
        end
        
        subgraph "Repository Layer"
            TransRepo[TransactionRepository]
            OutboundRepo[WebhookOutboundRepository]
        end
        
        subgraph "Core Infrastructure"
            PayDB[Database Client]
            PayRedis[Redis Client]
            PayLogger[Logging System]
        end
    end
    
    %% API to Middleware
    PayAPI --> PayAuthMW
    PayHealthAPI --> PayErrorMW
    
    %% Middleware to Services
    PayAuthMW --> PaySvc
    PayErrorMW --> PayHealthSvc
    
    %% Services to Integration
    PaySvc --> MockGateway
    PaySvc --> WebhookClient
    PayWebhookSvc --> SubServiceClient
    
    %% Services to Repositories
    PaySvc --> TransRepo
    PayWebhookSvc --> OutboundRepo
    
    %% Repositories to Infrastructure
    TransRepo --> PayDB
    OutboundRepo --> PayDB
    PaySvc --> PayRedis
    PayWebhookSvc --> PayRedis
    
    %% Grey-only class styling with white text
    classDef api fill:#5f6368,stroke:#37393b,stroke-width:2px,color:#ffffff;
    classDef middleware fill:#6f7377,stroke:#404244,stroke-width:2px,color:#ffffff;
    classDef service fill:#808486,stroke:#4a4c4e,stroke-width:2px,color:#ffffff;
    classDef integration fill:#919599,stroke:#585a5c,stroke-width:2px,color:#ffffff;
    classDef repo fill:#a2a5a8,stroke:#6a6c6e,stroke-width:2px,color:#ffffff;
    classDef infra fill:#b3b6b9,stroke:#7b7d7f,stroke-width:2px,color:#ffffff;
    
    class PayAPI,PayHealthAPI api
    class PayAuthMW,PayCORS,PayErrorMW middleware
    class PaySvc,PayWebhookSvc,PayHealthSvc service
    class MockGateway,WebhookClient,SubServiceClient integration
    class TransRepo,OutboundRepo repo
    class PayDB,PayRedis,PayLogger infra
```

---

## Database Design

### Schema Overview

The system uses a normalized PostgreSQL schema with proper foreign key relationships, indexes, and constraints.

```mermaid
erDiagram
    Users ||--o{ Subscriptions : has
    Users ||--o{ UserUsage : tracks
    Plans ||--o{ Subscriptions : defines
    Subscriptions ||--o{ SubscriptionEvents : logs
    Subscriptions ||--o{ Transactions : pays_for
    Transactions ||--o{ GatewayWebhookRequests : triggers
    Transactions ||--o{ WebhookOutboundRequests : notifies
    PaymentWebhookRequests ||--o{ Subscriptions : updates

    Users {
        int id PK
        string email UK
        string password_hash
        string first_name
        string last_name
        timestamp created_at
        timestamp updated_at
    }
    
    Plans {
        uuid id PK
        string name
        string billing_cycle
        decimal price
        string currency
        jsonb features
        boolean is_active
        boolean is_trial_plan
        int trial_period_days
        timestamp created_at
        timestamp updated_at
    }
    
    Subscriptions {
        uuid id PK
        int user_id FK
        uuid plan_id FK
        string status
        timestamp start_date
        timestamp end_date
        timestamp canceled_at
        timestamp created_at
        timestamp updated_at
    }
    
    SubscriptionEvents {
        int id PK
        uuid subscription_id FK
        string event_type
        jsonb event_metadata
        timestamp created_at
    }
    
    UserUsage {
        int id PK
        int user_id FK
        string feature_name
        int usage_count
        timestamp reset_at
        timestamp created_at
        timestamp updated_at
    }
    
    Transactions {
        uuid id PK
        uuid subscription_id FK
        decimal amount
        string currency
        string status
        string gateway_reference
        string error_message
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }
    
    PaymentWebhookRequests {
        int id PK
        string event_id UK
        jsonb payload
        boolean processed
        timestamp processed_at
        timestamp created_at
        timestamp updated_at
    }
    
    GatewayWebhookRequests {
        int id PK
        uuid transaction_id UK
        jsonb payload
        boolean processed
        timestamp processed_at
        timestamp created_at
        timestamp updated_at
    }
    
    WebhookOutboundRequests {
        int id PK
        string target_url
        jsonb payload
        string status
        int retry_count
        timestamp last_attempt_at
        timestamp created_at
        timestamp updated_at
    }
```
---

## API Design & Endpoints

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

## API Flow Examples

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

---

## Message Queue Architecture

### Queue System Overview

The system uses **Redis-based message queues** with **Celery** for robust asynchronous processing, featuring retry logic, dead letter queues (Separate JobLog table), and comprehensive monitoring.

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

## Security & Authentication

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

---

## Testing Strategy

### Testing Pyramid

**Unit Tests**:
- Service layer business logic
- Repository layer data access
- Utility functions and helpers
- Message processing logic

---

## Containerization & Deployment

### Docker Architecture

The system uses **multi-stage Docker builds** for optimized container images with separate environment configurations.

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

| Service                | Description                   | Health Check           |
|------------------------|--------------------------------|------------------------|
| subscription-service   | Main subscription API          | HTTP `/v1/health/`     |
| payment-service        | Payment processing API         | HTTP `/v1/health/`     |
| subscription-worker    | Background task processor      | Celery status          |
| payment-worker         | Payment queue processor        | Celery status          |
| celery-beat            | Task scheduler                 | Process health         |
| postgres               | Primary database               | Database connection    |
| redis                  | Cache and message broker       | Redis ping             |
| flower                 | Queue monitoring dashboard     | HTTP interface         |


---

## Monitoring & Health Checks

![flower](billing-backend/docs/images/flower.png)

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

---

