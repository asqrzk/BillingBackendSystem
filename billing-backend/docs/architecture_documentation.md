# Billing Backend System - Architecture Documentation

This document provides a comprehensive overview of the billing backend system architecture, including system components, data flow, deployment structure, and security models.

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Service Architecture](#service-architecture)
4. [Data Architecture](#data-architecture)
5. [Infrastructure Architecture](#infrastructure-architecture)
6. [Security Architecture](#security-architecture)
7. [Queue & Message Architecture](#queue--message-architecture)
8. [API Architecture](#api-architecture)
9. [Deployment Architecture](#deployment-architecture)

---

## System Overview

The billing backend system is a **microservices-based architecture** designed for scalable subscription and payment management. It provides comprehensive billing capabilities including user authentication, subscription management, payment processing, usage tracking, and webhook integrations.

### Key Design Principles

- **Microservices Architecture**: Loosely coupled services with clear boundaries
- **Event-Driven Design**: Asynchronous processing using message queues
- **Security-First**: JWT authentication and HMAC-secured webhooks
- **Scalability**: Horizontal scaling with Redis caching and queue processing
- **Reliability**: Retry mechanisms, error handling, and transaction management
- **Observability**: Comprehensive logging and health monitoring

---

## High-Level Architecture

```mermaid
flowchart TB
 subgraph External["External"]
        Client["Client Applications"]
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
 subgraph Integration["External Integration"]
        MockGW["Mock Payment Gateway"]
  end
    Integration <--> CoreServices
    External <--> CoreServices
    Background <--> DataLayer & CoreServices

     Client:::external
     SubService:::service
     PayService:::service
     SubWorker:::worker
     PayWorker:::worker
     Beat:::worker
     PostgreSQL:::data
     Redis:::data
     MockGW:::external
    classDef service fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef data fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef worker fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef external fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
```

---

## Service Architecture

### Subscription Service Architecture

```mermaid
graph TB
    subgraph "Subscription Service (Port 8001)"
        subgraph "API Layer"
            AuthAPI[Auth Endpoints<br/>/v1/auth/*]
            SubAPI[Subscription Endpoints<br/>/v1/subscriptions/*]
            UsageAPI[Usage Endpoints<br/>/v1/usage/*]
            WebhookAPI[Webhook Endpoints<br/>/v1/webhooks/*]
            HealthAPI[Health Endpoints<br/>/v1/health/*]
        end
        
        subgraph "Middleware"
            AuthMW[JWT Authentication]
            CORS[CORS Middleware]
            ErrorMW[Error Handler]
            LogMW[Request Logging]
        end
        
        subgraph "Service Layer"
            AuthSvc[AuthService]
            SubSvc[SubscriptionService]
            UsageSvc[UsageService]
            WebhookSvc[WebhookService]
            HealthSvc[HealthService]
        end
        
        subgraph "Repository Layer"
            UserRepo[UserRepository]
            PlanRepo[PlanRepository]
            SubRepo[SubscriptionRepository]
            UsageRepo[UsageRepository]
            WebhookRepo[WebhookRepository]
        end
        
        subgraph "Core Infrastructure"
            DB[Database Client]
            RedisClient[Redis Client]
            Logger[Logging System]
            Config[Configuration]
        end
    end
    
    %% API to Middleware
    AuthAPI --> AuthMW
    SubAPI --> AuthMW
    UsageAPI --> AuthMW
    WebhookAPI --> ErrorMW
    HealthAPI --> LogMW
    
    %% Middleware to Services
    AuthMW --> AuthSvc
    AuthMW --> SubSvc
    AuthMW --> UsageSvc
    ErrorMW --> WebhookSvc
    LogMW --> HealthSvc
    
    %% Services to Repositories
    AuthSvc --> UserRepo
    SubSvc --> SubRepo
    SubSvc --> PlanRepo
    UsageSvc --> UsageRepo
    WebhookSvc --> WebhookRepo
    
    %% Repositories to Infrastructure
    UserRepo --> DB
    SubRepo --> DB
    PlanRepo --> DB
    UsageRepo --> DB
    WebhookRepo --> DB
    UsageSvc --> RedisClient
    WebhookSvc --> RedisClient
    
    %% Infrastructure
    Logger --> Config
    
    classDef api fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef middleware fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef service fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef repo fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    classDef infra fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class AuthAPI,SubAPI,UsageAPI,WebhookAPI,HealthAPI api
    class AuthMW,CORS,ErrorMW,LogMW middleware
    class AuthSvc,SubSvc,UsageSvc,WebhookSvc,HealthSvc service
    class UserRepo,PlanRepo,SubRepo,UsageRepo,WebhookRepo repo
    class DB,RedisClient,Logger,Config infra
```

### Payment Service Architecture

```mermaid
graph TB
    subgraph "Payment Service (Port 8002)"
        subgraph "API Layer"
            PayAPI[Payment Endpoints<br/>/v1/payments/*]
            GatewayAPI[Webhook Endpoints<br/>/v1/webhooks/*]
            PayHealthAPI[Health Endpoints<br/>/v1/health/*]
        end
        
        subgraph "Middleware"
            PayAuthMW[JWT Authentication]
            PayCORS[CORS Middleware]
            PayErrorMW[Error Handler]
            WebhookSec[Webhook Security]
        end
        
        subgraph "Service Layer"
            PaySvc[PaymentService]
            GatewaySvc[GatewayService]
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
            GatewayRepo[GatewayWebhookRepository]
            OutboundRepo[WebhookOutboundRepository]
        end
        
        subgraph "Core Infrastructure"
            PayDB[Database Client]
            PayRedis[Redis Client]
            PayLogger[Logging System]
            PayConfig[Configuration]
        end
    end
    
    %% API to Middleware
    PayAPI --> PayAuthMW
    GatewayAPI --> WebhookSec
    PayHealthAPI --> PayErrorMW
    
    %% Middleware to Services
    PayAuthMW --> PaySvc
    WebhookSec --> PayWebhookSvc
    PayErrorMW --> PayHealthSvc
    
    %% Services to Integration
    PaySvc --> MockGateway
    PaySvc --> WebhookClient
    PayWebhookSvc --> SubServiceClient
    
    %% Services to Repositories
    PaySvc --> TransRepo
    PayWebhookSvc --> GatewayRepo
    PayWebhookSvc --> OutboundRepo
    
    %% Repositories to Infrastructure
    TransRepo --> PayDB
    GatewayRepo --> PayDB
    OutboundRepo --> PayDB
    PaySvc --> PayRedis
    PayWebhookSvc --> PayRedis
    
    classDef api fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef middleware fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef service fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef integration fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    classDef repo fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    classDef infra fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class PayAPI,GatewayAPI,PayHealthAPI api
    class PayAuthMW,PayCORS,PayErrorMW,WebhookSec middleware
    class PaySvc,GatewaySvc,PayWebhookSvc,PayHealthSvc service
    class MockGateway,WebhookClient,SubServiceClient integration
    class TransRepo,GatewayRepo,OutboundRepo repo
    class PayDB,PayRedis,PayLogger,PayConfig infra
```

---

## Data Architecture

### Database Schema Overview

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

### Data Flow Architecture

```mermaid
graph TD
    subgraph "Data Sources"
        ClientReq[Client Requests]
        WebhookReq[Webhook Requests]
        ScheduledTasks[Scheduled Tasks]
    end
    
    subgraph "Application Layer"
        API[API Endpoints]
        Services[Service Layer]
        Workers[Background Workers]
    end
    
    subgraph "Caching Layer"
        RedisCache[Redis Cache]
        RedisQueues[Redis Queues]
        RedisSession[Redis Sessions]
    end
    
    subgraph "Primary Storage"
        PostgresMain[(PostgreSQL<br/>Primary Database)]
    end
    
    subgraph "Data Processing"
        ETL[Data Sync Jobs]
        Analytics[Usage Analytics]
        Reporting[Report Generation]
    end
    
    %% Data Flow
    ClientReq --> API
    WebhookReq --> API
    ScheduledTasks --> Workers
    
    API --> Services
    Services --> RedisCache
    Services --> PostgresMain
    
    Services --> RedisQueues
    RedisQueues --> Workers
    Workers --> PostgresMain
    
    Workers --> ETL
    PostgresMain --> Analytics
    Analytics --> Reporting
    
    %% Cache Interactions
    RedisCache -.->|Cache Hit| Services
    Services -.->|Cache Miss| PostgresMain
    PostgresMain -.->|Update Cache| RedisCache
    
    classDef source fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef app fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef cache fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef storage fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef processing fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    
    class ClientReq,WebhookReq,ScheduledTasks source
    class API,Services,Workers app
    class RedisCache,RedisQueues,RedisSession cache
    class PostgresMain storage
    class ETL,Analytics,Reporting processing
```

---

## Queue & Message Architecture

### Message Processing System

```mermaid
graph TB
    %% Layer 1 - Producers
    subgraph Producers["Message Producers"]
        API[API Endpoints]
        Webhooks[Webhook Handlers]
        Scheduler[Scheduled Tasks]
        Events[Event Triggers]
    end
    
    %% Layer 2 - Redis Queue System
    subgraph RedisQueue["Redis Queue System"]
        subgraph QueueTypes["Queue Types"]
            SubQueue[subscription_tasks]
            PayQueue[payment_tasks]
            UsageQueue[usage_tasks]
            WebhookQueue[webhook_tasks]
            QueueQueue[queue_tasks]
        end
        
        subgraph QueueMgmt["Queue Management"]
            DelayedQueue[Delayed Messages]
            RetryQueue[Retry Queue]
            FailedQueue[Failed Messages]
            DeadLetter[Dead Letter Queue]
        end
    end
    
    %% Layer 3 - Consumers
    subgraph Consumers["Message Consumers"]
        subgraph Workers["Workers"]
            SubWorker[Subscription Worker]
            PayWorker[Payment Worker]
            UsageWorker[Usage Consumer]
            WebhookWorker[Webhook Consumer]
        end
        
        subgraph Schedulers["Scheduler"]
            CeleryBeat[Celery Beat<br/>Queue Polling Every 10s]
        end
        
        subgraph Monitoring["Monitoring"]
            Flower[Flower Dashboard]
            HealthCheck[Health Monitoring]
        end
    end
    
    %% Layer 4 - Processing Logic
    subgraph Processing["Processing Logic"]
        BusinessLogic[Business Logic Processing]
        DatabaseOps[Database Operations]
        ExternalCalls[External API Calls]
        ErrorHandling[Error Handling & Retry]
    end
    
    %% Outer Layer Connections Only
    Producers --> RedisQueue
    RedisQueue --> Consumers
    Consumers --> Processing
    
    %% Styling
    classDef producer fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef queue fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef management fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef consumer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef processing fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    
    class API,Webhooks,Scheduler,Events producer
    class SubQueue,PayQueue,UsageQueue,WebhookQueue,QueueQueue queue
    class DelayedQueue,RetryQueue,FailedQueue,DeadLetter management
    class SubWorker,PayWorker,UsageWorker,WebhookWorker,CeleryBeat,Flower,HealthCheck consumer
    class BusinessLogic,DatabaseOps,ExternalCalls,ErrorHandling processing
```

### Message Flow & Retry Logic

```mermaid
stateDiagram-v2
    [*] --> Queued: Message Published
    
    Queued --> Processing: Worker Picks Up
    Processing --> Success: Processing Completed
    Processing --> Failed: Processing Error
    
    Failed --> RetryCheck: Check Retry Count
    RetryCheck --> DelayedRetry: Retries < Max (3)
    RetryCheck --> DeadLetter: Retries >= Max
    
    DelayedRetry --> Queued: After Exponential Backoff
    
    Success --> [*]: Message Acknowledged
    DeadLetter --> [*]: Manual Intervention Required
    
    note right of DelayedRetry
        Exponential Backoff:
        Retry 1: 5 minutes
        Retry 2: 15 minutes  
        Retry 3: 30 minutes
    end note
    
    note right of DeadLetter
        Failed messages logged
        for manual review and
        potential reprocessing
    end note
```

---

## API Architecture


### Request/Response Flow

```mermaid
sequenceDiagram
    participant Client as Client
    participant Gateway as API Gateway
    participant Auth as Auth Middleware
    participant Service as Service Layer
    participant Validation as Input Validation
    participant Business as Business Logic
    participant Repository as Repository Layer
    participant Database as Database
    participant Response as Response Builder
    
    Client->>Gateway: HTTP Request
    Gateway->>Auth: Authenticate Request
    
    alt Authentication Failed
        Auth-->>Client: 401 Unauthorized
    else Authentication Success
        Auth->>Service: Authenticated Request
        Service->>Validation: Validate Input
        
        alt Validation Failed
            Validation-->>Client: 422 Validation Error
        else Validation Success
            Validation->>Business: Process Business Logic
            Business->>Repository: Data Operations
            Repository->>Database: Execute Query
            Database-->>Repository: Query Result
            Repository-->>Business: Data Response
            Business->>Response: Build Response
            Response-->>Client: HTTP Response
        end
    end
```

---

## Summary

This billing backend system represents a **modern, scalable microservices architecture** with the following key characteristics:

### **Architectural Strengths:**
- **Microservices Design**: Clear service boundaries with domain-driven design
- **Event-Driven Architecture**: Asynchronous processing with reliable message queues
- **Security-First Approach**: Comprehensive authentication, authorization, and webhook security
- **Scalability**: Horizontal scaling capabilities with caching and queue distribution
- **Observability**: Comprehensive monitoring, logging, and health checking
- **Development-Friendly**: Docker-based development with hot reloading and easy setup

### **Technology Stack:**
- **Backend**: FastAPI (Python) with async/await support
- **Database**: PostgreSQL with async SQLAlchemy ORM
- **Caching/Queues**: Redis for both caching and message queuing
- **Task Processing**: Celery with Redis broker
- **Containerization**: Docker with docker-compose orchestration
- **API Documentation**: OpenAPI/Swagger with interactive documentation
- **Security**: JWT authentication, HMAC webhook signatures, bcrypt password hashing

### **Operational Excellence:**
- **Health Monitoring**: Comprehensive health checks across all system components
- **Error Handling**: Structured error handling with retry mechanisms and dead letter queues
- **Data Integrity**: Transaction management with rollback capabilities
- **Performance**: Redis caching for high-frequency operations
- **Reliability**: Idempotency handling and duplicate detection for critical operations

This architecture provides a solid foundation for a production-ready billing system that can handle enterprise-scale workloads while maintaining developer productivity and operational excellence. 