# Billing Backend System

A comprehensive billing backend system with subscription management, payment processing, and feature usage tracking. Built with FastAPI, PostgreSQL, Redis, and Celery with **JWT Authentication** and **HMAC-secured webhooks**.

## 🏗️ Architecture

- **Subscription Service** (Port 8001): Manages subscriptions, usage tracking, webhooks, and **user authentication**
- **Payment Service** (Port 8002): Handles payments with mock gateway simulation
- **PostgreSQL**: Database for persistent data
- **Redis**: Message queues and atomic operations
- **Celery**: Async task processing with **automated queue polling**
- **Docker**: Containerized deployment

## 🔐 Authentication & Security

The system uses **JWT-based authentication** and **HMAC-secured webhooks** with the following design:

### Centralized Authentication Architecture
- **Token Creation**: Only Subscription Service creates JWT tokens
- **Token Validation**: Both services validate tokens using shared secret
- **User Isolation**: Users can only access/modify their own data
- **Service-to-Service**: Internal APIs protected by service tokens

### 🔒 Webhook Security (NEW!)
- **HMAC-SHA256 Signatures**: All webhooks are cryptographically signed
- **Timestamp Verification**: Prevents replay attacks (5-minute tolerance)
- **Industry Standard**: Compatible with Stripe, GitHub, and other webhook providers
- **Required Headers**:
  - `X-Webhook-Signature`: `sha256=<hmac_signature>`
  - `X-Webhook-Timestamp`: `<unix_timestamp>`

### Getting Started with Authentication

1. **Register a new user** or **login with existing credentials**:
```bash
# Register
curl -X POST "http://localhost:8001/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "first_name": "Test",
    "last_name": "User"
  }'

# Login (seeded users password: "password123")
curl -X POST "http://localhost:8001/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "password123"}'
```

2. **Use the JWT token** in subsequent requests:
```bash
# Set token (replace with actual token from login response)
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

# Access authenticated endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/v1/auth/me"
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)

### 1. Clone and Start Services

```bash
git clone <repository-url>
cd billing-backend

# Start all services
docker-compose up --build

# Or start in background
docker-compose up -d --build
```

### 2. Verify Services are Running

```bash
# Check subscription service
curl "http://localhost:8001/v1/health"

# Check payment service  
curl "http://localhost:8002/v1/health"

# Check detailed health (database, Redis, queues)
curl "http://localhost:8001/v1/health/detailed"
```

### 3. Test Authentication Flow

```bash
# Register a new user
curl -X POST "http://localhost:8001/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "securepass123",
    "first_name": "New",
    "last_name": "User"
  }'

# Login and get token
curl -X POST "http://localhost:8001/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com", 
    "password": "securepass123"
  }'
```

## 📋 API Endpoints

### Authentication Endpoints
- `POST /v1/auth/register` - Register new user
- `POST /v1/auth/login` - Login user and get JWT token
- `GET /v1/auth/me` - Get current user info (authenticated)
- `POST /v1/auth/change-password` - Change user password (authenticated)
- `POST /v1/auth/refresh` - Refresh JWT token (authenticated)

### Subscription Endpoints (Authenticated)
- `POST /v1/subscriptions` - Create new subscription
- `POST /v1/subscriptions/trial` - Create trial subscription
- `GET /v1/subscriptions/{id}` - Get subscription details
- `GET /v1/subscriptions/active` - Get user's active subscription
- `PUT /v1/subscriptions/{id}/plan` - Change subscription plan
- `DELETE /v1/subscriptions/{id}` - Cancel subscription

### Usage Tracking Endpoints (Authenticated)
- `POST /v1/usage/features/{feature_name}/use` - Use a feature (atomic)
- `GET /v1/usage` - Get user's current usage
- `GET /v1/usage/{feature_name}` - Get specific feature usage
- `POST /v1/usage/reset` - Reset usage counters
- `GET /v1/usage/stats` - Get usage statistics

### Payment Endpoints (Authenticated)
- `POST /v1/payments/process` - Process payment
- `GET /v1/payments/transactions/{id}` - Get transaction details
- `GET /v1/payments/transactions` - Get user transactions
- `POST /v1/payments/refund/{transaction_id}` - Initiate refund

### Health & Monitoring
- `GET /v1/health` - Basic health check
- `GET /v1/health/detailed` - Detailed health with dependencies
- `GET /v1/health/queues` - Queue status and depths

## 🧪 Testing

The system includes a comprehensive test suite with **60+ unit tests** covering all critical business logic.

### Test Categories

#### 🔐 Security Tests (~15 tests)
- **HMAC-SHA256 signature generation and verification**
- **Timestamp tolerance and replay attack prevention**
- **Constant-time comparison (timing attack protection)**
- **Input validation and malformed data handling**

#### 🧪 Subscription Service Tests (~25 tests)
- **Subscription lifecycle**: creation, cancellation, plan changes
- **Usage tracking**: Redis atomic operations, limit enforcement
- **Webhook processing**: idempotency, status handling
- **Trial subscriptions**: date calculations, special handling

#### 💳 Payment Service Tests (~20 tests)
- **Payment processing**: card validation, gateway integration
- **Transaction management**: creation, updates, refunds
- **Card validation**: Luhn algorithm, expiry, CVV checks
- **Error handling**: gateway failures, invalid inputs

### Running Tests

Use the included test runner script:

```bash
# Run all tests
python scripts/run_tests.py --all

# Run specific service tests
python scripts/run_tests.py --subscription
python scripts/run_tests.py --payment

# Run security tests only
python scripts/run_tests.py --security

# Run with coverage report
python scripts/run_tests.py --all --coverage

# Run specific test patterns
python scripts/run_tests.py --pattern "test_webhook"

# Show test summary
python scripts/run_tests.py --summary
```

### Test Coverage Focus

The tests focus on **critical business logic** that could break with code changes:

- ✅ **Authentication flows** (login, registration, token validation)
- ✅ **Payment processing** (card validation, gateway communication)
- ✅ **Subscription lifecycle** (creation, cancellation, renewals)
- ✅ **Usage tracking** (atomic operations, limit checking)
- ✅ **Webhook security** (HMAC verification, replay protection)
- ✅ **Input validation** (malformed data, edge cases)
- ✅ **Error handling** (database failures, external service errors)

### Running Tests Manually

If you prefer to run tests directly:

```bash
# Subscription service tests
cd subscription-service
python -m pytest --cov=app --cov-report=html

# Payment service tests  
cd payment-service
python -m pytest --cov=app --cov-report=html
```

## 📊 Test Results Example

```bash
$ python scripts/run_tests.py --all --coverage

🚀 Billing Backend Test Runner
============================================================
Running all tests...

🧪 Running Subscription Service Tests
==================================================
======================== test session starts ========================
subscription-service/tests/test_subscription_service.py::TestSubscriptionService::test_create_subscription_success PASSED
subscription-service/tests/test_usage_service.py::TestUsageService::test_use_feature_success PASSED
subscription-service/tests/test_webhook_security.py::TestWebhookSignatureVerifier::test_verify_signature_success PASSED
...
======================== 25 passed in 2.45s ========================

💳 Running Payment Service Tests
==================================================
======================== test session starts ========================
payment-service/tests/test_payment_service.py::TestPaymentService::test_process_payment_success PASSED
...
======================== 20 passed in 1.83s ========================

============================================================
✅ All tests PASSED!
📊 Coverage reports generated in service directories

💡 Tips:
• Run with --coverage to see test coverage
• Use --pattern to run specific tests
• Check htmlcov/index.html for detailed coverage report
• Run --security to focus on security-critical tests
```

## 💳 Payment Processing

### Supported Test Cards
- **Success**: `4242424242424242` (default success card)
- **Failure**: Any other card number will simulate failure
- **Success Rate**: 80% configurable via `GATEWAY_SUCCESS_RATE`

### Payment Flow
1. **Validate card details** (Luhn algorithm, expiry, CVV)
2. **Create transaction record** in database
3. **Process through mock gateway** (1-3 second delay)
4. **Update transaction status** based on gateway response
5. **Queue webhook notification** to subscription service
6. **Handle trial refunds** automatically for $0 payments

## 🔄 Feature Usage Tracking

### Redis-First Architecture
The system uses **Redis for atomic operations** to prevent race conditions:

```bash
# Use API calls feature
curl -X POST "http://localhost:8001/v1/usage/features/api_calls/use" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"delta": 1}'

# Check current usage
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/v1/usage"
```

### Atomic Usage Checking
- **Redis Lua Scripts**: Ensure atomic read-increment-check operations
- **Race Condition Prevention**: Multiple concurrent requests handled safely
- **Real-time Limits**: Instant feedback on usage limits
- **Background Sync**: Usage data synced to PostgreSQL periodically

## 🔄 Subscription Management

### Create Subscription
```bash
curl -X POST "http://localhost:8001/v1/subscriptions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

### Trial Subscriptions
```bash
curl -X POST "http://localhost:8001/v1/subscriptions/trial" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trial_plan_id": "550e8400-e29b-41d4-a716-446655440001"
  }'
```

## 🔗 Webhook Integration

Both services support **industry-standard HMAC-signed webhooks**:

- ✅ **Subscription Service**: `POST /v1/webhooks/payment`
- ✅ **Payment Service**: `POST /v1/webhooks/gateway`

#### Testing Webhooks

```bash
# Use the provided testing script
python scripts/test_webhook.py subscription --event-id test123
python scripts/test_webhook.py gateway --transaction-id test-txn
python scripts/test_webhook.py invalid  # Test signature validation

# Manual testing with proper signature
TIMESTAMP=$(date +%s)
PAYLOAD='{"event_id":"test123","status":"success"}'
SIGNATURE=$(echo -n "${TIMESTAMP}.${PAYLOAD}" | openssl dgst -sha256 -hmac "dev-webhook-secret-change-in-production-32-chars-minimum" | sed 's/^.* //')

curl -X POST "http://localhost:8001/v1/webhooks/payment" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=${SIGNATURE}" \
  -H "X-Webhook-Timestamp: ${TIMESTAMP}" \
  -d "${PAYLOAD}"
```

## 🔄 Queue Processing System (Fixed)

The system now includes a **fully automated queue processing system**:

### Architecture
```
📋 Redis Queues ← 🔄 Beat Scheduler (10s) → 👷 Celery Workers
    ↓ 
🎯 Messages Auto-Processed
```

### Services
- **subscription-worker**: Processes subscription, usage, and webhook tasks
- **subscription-beat**: Celery Beat scheduler for periodic queue polling
- **payment-worker**: Processes payment-related tasks
- **flower**: Celery monitoring dashboard

### Queue Health Monitoring

```bash
# Check queue status
curl "http://localhost:8001/v1/health/queues"

# Detailed health check
curl "http://localhost:8001/v1/health/detailed"

# Monitor via Flower dashboard
open http://localhost:5555
```

## 🏥 Health Checks (Fixed)

All health check endpoints are now working correctly:

```bash
# Basic health check
curl "http://localhost:8001/v1/health"

# Detailed health check (Database, Redis, Queues)
curl "http://localhost:8001/v1/health/detailed"

# Queue-specific status
curl "http://localhost:8001/v1/health/queues"
```

Expected healthy response:
```json
{
  "status": "healthy",
  "service": "subscription-service",
  "checks": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "queues": {"status": "healthy"}
  }
}
```

## 💳 Mock Payment Gateway

The payment gateway simulates real-world scenarios:

### Test Cards
- **Success**: `4242424242424242` (configurable via `PAYMENT_GATEWAY_SUCCESS_CARD`)
- **Failure**: Any other card number
- **Success Rate**: 80% (configurable via `GATEWAY_SUCCESS_RATE`)
- **Processing Delay**: 1-3 seconds (configurable)

### Environment Variables
```env
PAYMENT_GATEWAY_SUCCESS_CARD=4242424242424242
GATEWAY_SUCCESS_RATE=0.8
GATEWAY_MIN_DELAY_MS=1000
GATEWAY_MAX_DELAY_MS=3000
```

## 🔒 Security Features

### JWT Authentication
- **HS256 Algorithm**: Industry standard
- **Token Expiration**: 1 hour (configurable)
- **Password Hashing**: bcrypt with salt rounds
- **User Isolation**: Users can only access their own data

### Webhook Security (NEW!)
- **HMAC-SHA256**: Industry-standard cryptographic signatures
- **Timestamp Verification**: 5-minute tolerance window prevents replay attacks
- **Constant-time Comparison**: Prevents timing attacks
- **Comprehensive Logging**: Security events are logged for monitoring

### Service-to-Service Communication
- **Internal APIs**: Protected by dedicated service tokens
- **Cross-Service Calls**: Subscription ↔ Payment service communication secured

### Security Headers
- **Bearer Token**: Standard Authorization header format
- **Input Validation**: Pydantic schemas for all requests
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

## 🔧 Advanced Configuration

### Environment Variables

#### Subscription Service
```env
DATABASE_URL=postgresql://billing_user:billing_pass@postgres:5432/billing_db
REDIS_URL=redis://redis:6379/0
PAYMENT_SERVICE_URL=http://payment-service:8000

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Webhook Security
WEBHOOK_SIGNING_SECRET=webhook-signing-secret-change-in-production
WEBHOOK_TOLERANCE_SECONDS=300

# Service-to-Service Communication
SERVICE_TO_SERVICE_SECRET=service-secret-change-in-production
```

#### Payment Service
```env
DATABASE_URL=postgresql://billing_user:billing_pass@postgres:5432/billing_db
REDIS_URL=redis://redis:6379/0
SUBSCRIPTION_SERVICE_URL=http://subscription-service:8000

# Mock Gateway Configuration
PAYMENT_GATEWAY_SUCCESS_CARD=4242424242424242
GATEWAY_SUCCESS_RATE=0.8
GATEWAY_MIN_DELAY_MS=1000
GATEWAY_MAX_DELAY_MS=3000

# Webhook Security
WEBHOOK_SIGNING_SECRET=webhook-signing-secret-change-in-production
```

## 🐛 Troubleshooting

### Authentication Issues

1. **Invalid JWT token errors**:
```bash
# Check if token is expired or malformed
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/v1/auth/me"

# Re-login to get fresh token
curl -X POST "http://localhost:8001/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "password123"}'
```

2. **Permission denied for internal endpoints**:
```bash
# Check internal endpoints (should be protected)
curl "http://localhost:8001/v1/subscriptions/internal/user/1"
# Should return 403 without proper service token
```

### Webhook Security Issues

1. **Invalid signature errors**:
```bash
# Test webhook signature validation
python scripts/test_webhook.py invalid

# Check webhook logs
docker-compose logs subscription-service | grep -i webhook
```

2. **Timestamp too old errors**:
```bash
# Ensure system clocks are synchronized
# Webhook tolerance is 5 minutes by default
```

3. **Missing headers**:
```bash
# Webhooks require both headers:
# X-Webhook-Signature: sha256=<signature>
# X-Webhook-Timestamp: <unix_timestamp>
```

### Queue Processing Issues

1. **Messages not processing**: Check if Celery Beat is running
```bash
docker-compose logs subscription-beat
```

2. **Worker errors**: Check worker logs
```bash
docker-compose logs subscription-worker
```

3. **Queue depths**: Monitor via health checks
```bash
curl "http://localhost:8001/v1/health/queues"
```

### Service Issues

1. **Health check failures**:
```bash
# Check detailed health status
curl "http://localhost:8001/v1/health/detailed"
```

2. **Database connection issues**: Ensure PostgreSQL is ready
```bash
docker-compose logs postgres
```

3. **Redis connection issues**: Check Redis container
```bash
docker-compose logs redis
```

### Reset Everything

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Rebuild and restart
docker-compose up --build
```

## 📊 Performance Metrics

Expected performance characteristics:

- **API Response Time**: < 100ms for synchronous operations
- **Authentication**: < 50ms for JWT verification
- **Webhook Verification**: < 10ms for HMAC validation
- **Payment Processing**: 3-5 seconds (due to mock gateway delay)
- **Usage Tracking**: < 50ms (Redis-first approach)
- **Queue Processing**: 100+ messages/second per worker
- **Database**: Handles 1000+ concurrent connections

## 🔄 Development Workflow

### Testing Authentication
```bash
# 1. Register a test user
curl -X POST "http://localhost:8001/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@test.com", "password": "test123"}'

# 2. Login and get token
TOKEN=$(curl -s -X POST "http://localhost:8001/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@test.com", "password": "test123"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 3. Test authenticated endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/v1/auth/me"
```

### Testing Webhooks
```bash
# 1. Test valid webhook
python scripts/test_webhook.py subscription --event-id test123

# 2. Test invalid signature (should fail)
python scripts/test_webhook.py invalid

# 3. Test gateway webhook
python scripts/test_webhook.py gateway --transaction-id test-txn

# 4. Check webhook processing logs
docker-compose logs subscription-service | grep -i webhook
```

### Monitoring Queues
```bash
# Real-time queue monitoring
watch -n 2 'curl -s "http://localhost:8001/v1/health/queues" | python3 -m json.tool'

# Flower dashboard
open http://localhost:5555
```

## 🛡️ Security Best Practices

### Webhook Security
1. **Always verify signatures** before processing webhook data
2. **Check timestamp tolerance** to prevent replay attacks
3. **Use constant-time comparison** for signature verification
4. **Log security events** for monitoring and debugging
5. **Rotate webhook secrets** regularly in production

### JWT Security
1. **Use strong secrets** (minimum 32 characters)
2. **Set appropriate expiration** times
3. **Validate tokens** on every request
4. **Log authentication events**
5. **Implement refresh token** mechanism for production

### Production Deployment
1. **Use HTTPS** for all communications
2. **Configure firewalls** and network security
3. **Enable rate limiting** on public endpoints
4. **Monitor security logs** and set up alerts
5. **Regular security audits** and penetration testing

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite: `python scripts/run_tests.py --all`
5. Ensure authentication is properly implemented
6. Test webhook security implementation
7. Test with both services
8. Submit a pull request

## 📄 License

This project is licensed under the MIT License. 