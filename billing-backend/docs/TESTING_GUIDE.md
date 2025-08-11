# Testing Guide - Billing Backend

This guide provides instructions for running comprehensive tests of the billing backend with short renewal periods and **very small API limits** for real-time validation of usage tracking and service limits.

## Quick Start (5 minutes)

```bash
# 1. Start the test environment
docker-compose -f docker-compose.testing.yml up -d

# 2. Wait for services to start (about 2 minutes)
# Watch the logs to see when services are ready:
docker-compose -f docker-compose.testing.yml logs -f

# 3. Run the automated test suite
./scripts/test-runner.sh

# 4. Clean up after testing
docker-compose -f docker-compose.testing.yml down -v
```

## Test Environment Features

### ⚡ Fast Renewal Periods
- **Trial Period**: 2 minutes (instead of 14 days)
- **Monthly Billing**: 5 minutes (instead of 30 days)  
- **Yearly Billing**: 10 minutes (instead of 365 days)
- **Renewal Checks**: Every 30 seconds
- **Usage Reset**: Every 3 minutes

### 🔥 **Small API Limits for Fast Testing**
- **Free Trial**: 5 basic API calls (was 100)
- **Basic Plan**: 10 basic + 5 premium API calls (was 1,000)
- **Pro Plan**: 15 basic + 10 premium + 10 enterprise API calls (was 10,000)
- **Enterprise Plan**: 50 basic + 25 premium + 25 enterprise API calls (was 100,000)

### 🧪 Test Data
- **Success Card**: `4242424242424242` (Always succeeds)
- **Failure Card**: `4000000000000002` (Always fails)
- **Test Users**: Auto-created during testing
- **Test Plans**: All plans available with fast renewal periods and small limits

### 📊 Available Plans with Service Types
1. **Free Trial** - 1 AED, 2 min duration
   - **5 basic API calls only**
   - Premium/Enterprise services blocked
   - 1GB storage

2. **Basic Plan** - 29 AED, 5 min billing cycle
   - **10 basic + 5 premium API calls**
   - Enterprise services blocked
   - 5GB storage

3. **Pro Plan** - 99 AED, 5 min billing cycle
   - **15 basic + 10 premium + 10 enterprise API calls**
   - All services available, analytics
   - 50GB storage

4. **Enterprise Plan** - 299 AED, 5 min billing cycle
   - **50 basic + 25 premium + 25 enterprise API calls**
   - All services, dedicated support
   - 500GB storage

### 🎯 Service Types for Testing
- **Basic Service**: `useService()` - Available on all plans
- **Premium Service**: `usePremiumService()` - Available on Basic+ plans  
- **Enterprise Service**: `useEnterpriseService()` - Available on Pro+ plans

## Test Runner Options

```bash
# Setup test environment only
./scripts/test-runner.sh setup

# Run quick test suite (core scenarios, ~10 minutes)
./scripts/test-runner.sh quick

# Run comprehensive test suite (all scenarios, ~30 minutes)  
./scripts/test-runner.sh all

# Run usage limit focused tests (~8 minutes)
./scripts/test-runner.sh usage

# Teardown test environment
./scripts/test-runner.sh teardown
```

## Manual Testing

### Service URLs
- **Subscription Service**: http://localhost:8001
- **Payment Service**: http://localhost:8002
- **Database**: localhost:5433 (PostgreSQL)
- **Redis**: localhost:6380

### Test User Credentials
```json
{
  "email": "testuser1@example.com",
  "password": "SecurePass123!"
}
```

### Example API Calls for Usage Testing

1. **Register User**:
```bash
curl -X POST http://localhost:8001/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser1@example.com",
    "password": "SecurePass123!",
    "first_name": "Test",
    "last_name": "User"
  }'
```

2. **Login**:
```bash
curl -X POST http://localhost:8001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser1@example.com",
    "password": "SecurePass123!"
  }'
```

3. **Subscribe to Trial (5 API calls limit)**:
```bash
curl -X POST http://localhost:8001/v1/subscriptions/trial \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"trial_plan_id": "{TRIAL_PLAN_ID}"}'
```

4. **Use Basic Service (should work 5 times, fail on 6th)**:
```bash
# First 5 calls should succeed
for i in {1..5}; do
  curl -X POST http://localhost:8001/v1/usage/use \
    -H "Authorization: Bearer {JWT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"feature_name": "api_calls", "delta": 1}'
done

# 6th call should fail with limit exceeded
curl -X POST http://localhost:8001/v1/usage/use \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "api_calls", "delta": 1}'
```

5. **Attempt Premium Service on Trial (should fail)**:
```bash
curl -X POST http://localhost:8001/v1/usage/use \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "premium_api_calls", "delta": 1}'
```

6. **Check Usage Status**:
```bash
curl -X GET http://localhost:8001/v1/usage \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

7. **Upgrade to Basic Plan**:
```bash
curl -X POST http://localhost:8002/v1/payments/process \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 29.00,
    "currency": "AED", 
    "card_number": "4242424242424242",
    "card_expiry": "12/25",
    "card_cvv": "123",
    "cardholder_name": "Test User"
  }'
```

8. **Test Premium Service on Basic Plan (should work 5 times)**:
```bash
for i in {1..5}; do
  curl -X POST http://localhost:8001/v1/usage/use \
    -H "Authorization: Bearer {JWT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"feature_name": "premium_api_calls", "delta": 1}'
done
```

## Real-Time Testing Scenarios

### Scenario 1: Complete Usage Limit Testing (8 minutes)
1. **0:00** - Register user, start trial (5 basic API calls)
2. **1:00** - Use all 5 basic calls, test limit enforcement
3. **2:00** - Try premium/enterprise services (should fail)
4. **3:00** - Upgrade to Basic Plan (10 basic + 5 premium)
5. **4:00** - Test basic and premium services
6. **6:00** - Upgrade to Pro Plan (15+10+10 limits)
7. **7:00** - Test enterprise services now available
8. **8:00** - Verify all service types work with proper limits

### Scenario 2: Service Type Availability Testing (5 minutes)
1. **0:00** - Trial user: Only basic service (5 calls)
2. **2:00** - Basic Plan: Basic + premium services
3. **3:00** - Pro Plan: All service types available
4. **4:00** - Test enterprise service blocking/enabling
5. **5:00** - Verify independent limit tracking

### Scenario 3: Race Condition Testing (3 minutes)
1. **0:00** - User with 2 remaining API calls
2. **1:00** - Send 3 concurrent usage requests
3. **2:00** - Verify only 2 succeed, proper atomic handling
4. **3:00** - Confirm final usage count is correct

### Scenario 4: Plan Downgrade Impact (4 minutes)
1. **0:00** - User with Pro Plan (all services available)
2. **1:00** - Use some enterprise service calls
3. **2:00** - Downgrade to Basic Plan
4. **3:00** - Verify enterprise service immediately blocked
5. **4:00** - Confirm basic/premium services still work

## Monitoring During Tests

### View Logs
```bash
# All services
docker-compose -f docker-compose.testing.yml logs -f

# Specific service
docker-compose -f docker-compose.testing.yml logs -f subscription-service-test

# Usage tracking and Redis operations
docker-compose -f docker-compose.testing.yml logs -f subscription-worker-test
```

### Database Access for Usage Monitoring
```bash
# Connect to test database
docker exec -it billing-postgres-test psql -U billing_user -d billing_test_db

# View plan limits
SELECT 
    name,
    price,
    (features->'limits'->>'api_calls')::int as basic_calls,
    (features->'limits'->>'premium_api_calls')::int as premium_calls,
    (features->'limits'->>'enterprise_api_calls')::int as enterprise_calls
FROM plans ORDER BY price;

# View user usage
SELECT 
    u.email,
    uu.feature_name,
    uu.usage_count,
    uu.reset_at
FROM user_usage uu
JOIN users u ON u.id = uu.user_id
ORDER BY u.email, uu.feature_name;

# View subscription status
SELECT 
    u.email,
    s.status,
    p.name as plan_name,
    s.start_date,
    s.end_date
FROM subscriptions s
JOIN users u ON u.id = s.user_id
JOIN plans p ON p.id = s.plan_id
WHERE s.status IN ('active', 'trial')
ORDER BY s.created_at DESC;
```

### Redis Monitoring for Usage Tracking
```bash
# Connect to Redis
docker exec -it billing-redis-test redis-cli

# Check usage tracking keys
KEYS usage:*

# View specific user usage
HGETALL usage:1:api_calls
HGETALL usage:1:premium_api_calls  
HGETALL usage:1:enterprise_api_calls

# Check queue sizes
LLEN queue:payment_initiation
LLEN queue:trial_payment
```

## Expected Results

After running the complete test suite, you should see:
- ✅ **Trial Plan**: 5 basic API calls limit enforced
- ✅ **Basic Plan**: 10 basic + 5 premium calls, enterprise blocked
- ✅ **Pro Plan**: All service types available with correct limits
- ✅ **Usage Tracking**: Independent tracking per service type
- ✅ **Limit Enforcement**: Services blocked when limits exceeded
- ✅ **Plan Upgrades**: Immediate availability of new services
- ✅ **Plan Downgrades**: Immediate blocking of unavailable services
- ✅ **Race Conditions**: Atomic usage tracking without double-counting
- ✅ **Error Messages**: Clear errors for each limit type

## Troubleshooting

### Common Issues

**Usage tracking not working:**
```bash
# Check Redis connection
docker exec billing-redis-test redis-cli ping

# Verify usage service endpoints
curl http://localhost:8001/v1/usage -H "Authorization: Bearer {TOKEN}"

# Check plan features
docker exec billing-postgres-test psql -U billing_user -d billing_test_db -c "SELECT name, features FROM plans;"
```

**Limits not enforced:**
```bash
# Check plan configuration
curl http://localhost:8001/v1/plans

# Verify subscription status
curl http://localhost:8001/v1/subscriptions/active -H "Authorization: Bearer {TOKEN}"

# Check usage service logs
docker-compose -f docker-compose.testing.yml logs subscription-service-test | grep usage
```

**Services not blocked properly:**
```bash
# Verify plan features
SELECT name, features->'features' as available_features FROM plans;

# Check subscription plan
SELECT p.name, p.features FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.user_id = {USER_ID};
```

## Success Metrics

The usage tracking system is working correctly if:
- **Limit Enforcement**: ✅ All service types properly blocked when limits exceeded
- **Service Availability**: ✅ Service access matches plan features exactly
- **Independent Tracking**: ✅ Basic/premium/enterprise usage tracked separately
- **Atomic Operations**: ✅ No race conditions in concurrent requests
- **Real-time Updates**: ✅ Plan changes immediately affect service availability
- **Error Handling**: ✅ Clear, specific error messages for each limit scenario
- **Performance**: ✅ < 100ms response time for usage tracking operations

## Usage Testing Commands Reference

### Quick Limit Testing
```bash
# Set JWT_TOKEN from login response
export JWT_TOKEN="your_jwt_token_here"

# Test trial limits (should work 5 times)
for i in {1..6}; do 
  echo "Call $i:"; 
  curl -s -w " [%{http_code}]\n" -X POST http://localhost:8001/v1/usage/use \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"feature_name": "api_calls", "delta": 1}' | jq -r '.success // "FAILED"'
done

# Check current usage
curl -s http://localhost:8001/v1/usage -H "Authorization: Bearer $JWT_TOKEN" | jq .
```

This enhanced testing setup allows you to validate all usage tracking, service limits, and plan-based feature access in just **5-15 minutes** instead of waiting for real usage patterns! 🚀 