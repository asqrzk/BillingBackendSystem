# Comprehensive Test Scenario Plan for Billing Backend

## Overview
This document provides a detailed test plan covering all major functionalities of the billing backend system. The test plan includes scenarios for real-time testing with short renewal periods and **very small API limits** to validate usage tracking and limit enforcement.

## Test Environment Setup

### Quick Start
```bash
# 1. Start testing environment with short renewal periods
./scripts/env-manager.sh -e testing start

# 2. Verify all services are running
./scripts/env-manager.sh -e testing status

# 3. Initialize test database with test data
./scripts/env-manager.sh -e testing seed-data
```

### Available Test Plans with Small Limits
The system includes the following plans for testing **with very small API limits for quick testing**:

1. **Free Trial** - 1 AED, 2 minutes duration (normally 14 days)
   - **5 basic API calls** (was 100)
   - **0 premium/enterprise calls**
   - 1GB storage, community support
   - Auto-converts to Basic Plan

2. **Basic Plan** - 29 AED, 5 minutes billing cycle (normally monthly)
   - **10 basic API calls** (was 1,000)
   - **5 premium API calls** (new)
   - **0 enterprise calls**
   - 5GB storage, email support

3. **Pro Plan** - 99 AED, 5 minutes billing cycle (normally monthly)
   - **15 basic API calls** (was 10,000)
   - **10 premium API calls** (new)
   - **10 enterprise API calls** (new)
   - 50GB storage, priority support, analytics

4. **Enterprise Plan** - 299 AED, 5 minutes billing cycle (normally monthly)
   - **50 basic API calls** (was 100,000)
   - **25 premium API calls** (new)
   - **25 enterprise API calls** (new)
   - 500GB storage, dedicated support, analytics, custom features

5. **Annual Pro** - 999 AED, 10 minutes billing cycle (normally yearly)
   - Same features as Pro Plan with yearly billing

### Test Cards
- **Success Card**: `4242424242424242` (Always succeeds)
- **Failure Card**: `4000000000000002` (Always fails)
- **Random Card**: Any other number (80% success rate)

### API Service Types for Testing
- **Basic Service**: `useService()` - Available on all plans
- **Premium Service**: `usePremiumService()` - Available on Basic+ plans
- **Enterprise Service**: `useEnterpriseService()` - Available on Pro+ plans

---

## Test Scenarios

### Phase 1: User Management and Authentication

#### TC01: User Registration and Login
**Objective**: Verify user can register and authenticate successfully

**Steps**:
1. Register new user via API
   ```bash
   curl -X POST http://localhost:8001/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "testuser1@example.com",
       "password": "SecurePass123!",
       "first_name": "Test",
       "last_name": "User1"
     }'
   ```

2. Login with credentials
   ```bash
   curl -X POST http://localhost:8001/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{
       "email": "testuser1@example.com",
       "password": "SecurePass123!"
     }'
   ```

**Expected Results**:
- Registration returns 201 Created with user details
- Login returns 200 OK with JWT token
- Token can be used for authenticated requests

---

### Phase 2: Trial Subscription Management

#### TC02: First User Subscribes to Trial
**Objective**: Verify trial subscription creation and activation

**Prerequisites**: 
- User registered (TC01)
- Get trial plan ID from available plans

**Steps**:
1. Get available plans
   ```bash
   curl -X GET http://localhost:8001/v1/plans \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

2. Subscribe to Free Trial
   ```bash
   curl -X POST http://localhost:8001/v1/subscriptions/trial \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "trial_plan_id": "{TRIAL_PLAN_ID}"
     }'
   ```

3. Verify subscription status
   ```bash
   curl -X GET http://localhost:8001/v1/subscriptions/active \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

**Expected Results**:
- Trial subscription created with status "trial"
- End date set to 2 minutes from creation
- User can access trial features
- Usage limits initialized (**5 basic API calls**, 1GB storage)

#### TC03: Trial User Attempts Second Trial (Should Fail)
**Objective**: Verify trial restriction - one trial per user

**Prerequisites**: User already has active trial subscription (TC02)

**Steps**:
1. Attempt to create another trial subscription
   ```bash
   curl -X POST http://localhost:8001/v1/subscriptions/trial \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "trial_plan_id": "{TRIAL_PLAN_ID}"
     }'
   ```

**Expected Results**:
- Request returns 400 Bad Request
- Error message: "User already has an active subscription"
- Original trial subscription remains unchanged

#### TC04: Different User Successfully Gets Trial
**Objective**: Verify trial is available for new users

**Prerequisites**: 
- Register second user (repeat TC01 with different email)

**Steps**:
1. Register testuser2@example.com
2. Login and get JWT token
3. Subscribe to trial (same as TC02)

**Expected Results**:
- Second user successfully gets trial subscription
- Both users can have concurrent trials
- Each user has separate usage tracking

---

### Phase 3: Usage Tracking and Service Limits

#### TC05: Trial User Basic Service Usage (5 calls limit)
**Objective**: Verify basic service usage tracking and limits

**Prerequisites**: User with trial subscription (5 basic API calls limit)

**Steps**:
1. Check current usage
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

2. Use basic service 3 times (within limit)
   ```bash
   for i in {1..3}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "api_calls",
         "delta": 1
       }'
   done
   ```

3. Check updated usage
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

4. Use remaining 2 calls to reach limit
   ```bash
   for i in {1..2}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "api_calls",
         "delta": 1
       }'
   done
   ```

5. Attempt to exceed limit (should fail)
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "api_calls",
       "delta": 1
     }'
   ```

**Expected Results**:
- First 5 API calls succeed
- Usage count increments correctly (1→3→5)
- 6th API call is rejected with limit exceeded error
- Error message suggests upgrading plan

#### TC06: Trial User Premium Service Access (Should Fail)
**Objective**: Verify premium service is blocked on trial plan

**Prerequisites**: User with trial subscription

**Steps**:
1. Attempt to use premium service
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "premium_api_calls",
       "delta": 1
     }'
   ```

**Expected Results**:
- Request returns 403 Forbidden or 400 Bad Request
- Error message: "Premium service not available in current plan"
- Usage count remains 0 for premium calls

#### TC07: Trial User Enterprise Service Access (Should Fail)
**Objective**: Verify enterprise service is blocked on trial plan

**Prerequisites**: User with trial subscription

**Steps**:
1. Attempt to use enterprise service
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "enterprise_api_calls",
       "delta": 1
     }'
   ```

**Expected Results**:
- Request returns 403 Forbidden or 400 Bad Request
- Error message: "Enterprise service not available in current plan"
- Usage count remains 0 for enterprise calls

---

### Phase 4: Payment Processing and Plan Upgrades

#### TC08: Payment with Success Card and Basic Plan Upgrade
**Objective**: Verify successful payment processing and plan upgrade

**Prerequisites**: User with trial subscription (limits exhausted)

**Steps**:
1. Process payment for Basic Plan upgrade
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
       "cardholder_name": "Test User",
       "trial": false,
       "renewal": false
     }'
   ```

2. Check subscription status after payment
   ```bash
   curl -X GET http://localhost:8001/v1/subscriptions/active \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

3. Verify new usage limits
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

**Expected Results**:
- Payment processed successfully (status: "success")
- Subscription status updated to "active"
- Subscription plan changed to Basic Plan
- **New limits**: 10 basic + 5 premium API calls
- Previous usage may be reset or carried over

#### TC09: Basic Plan User Service Usage Testing
**Objective**: Test all available services on Basic Plan

**Prerequisites**: User with Basic Plan (10 basic + 5 premium API calls)

**Steps**:
1. Use basic service (8 calls - within limit)
   ```bash
   for i in {1..8}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "api_calls",
         "delta": 1
       }'
   done
   ```

2. Use premium service (4 calls - within limit)
   ```bash
   for i in {1..4}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "premium_api_calls",
         "delta": 1
       }'
   done
   ```

3. Check usage status
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

4. Attempt to use remaining premium calls
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "premium_api_calls",
       "delta": 1
     }'
   ```

5. Attempt to exceed premium limit (should fail)
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "premium_api_calls",
       "delta": 1
     }'
   ```

6. Attempt enterprise service (should fail)
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "enterprise_api_calls",
       "delta": 1
     }'
   ```

**Expected Results**:
- Basic API calls work (8/10 used)
- Premium API calls work (5/5 used)
- 6th premium call rejected with limit exceeded
- Enterprise calls rejected with feature not available
- Usage tracking accurate for all service types

#### TC10: Payment with Failure Card
**Objective**: Verify payment failure handling

**Prerequisites**: User with trial subscription

**Steps**:
1. Attempt payment with failure card
   ```bash
   curl -X POST http://localhost:8002/v1/payments/process \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 99.00,
       "currency": "AED",
       "card_number": "4000000000000002",
       "card_expiry": "12/25",
       "card_cvv": "123",
       "cardholder_name": "Test User",
       "trial": false,
       "renewal": false
     }'
   ```

2. Verify subscription remains unchanged
   ```bash
   curl -X GET http://localhost:8001/v1/subscriptions/active \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

**Expected Results**:
- Payment fails (status: "failed")
- Transaction record shows failure
- Subscription status unchanged (still "trial")
- Original usage limits remain
- Error message provided to user

---

### Phase 5: Plan Changes and Usage Limit Updates

#### TC11: Upgrade from Basic to Pro Plan
**Objective**: Verify plan upgrade and new usage limits

**Prerequisites**: User with Basic Plan

**Steps**:
1. Get Pro Plan ID
2. Initiate plan change
   ```bash
   curl -X POST http://localhost:8001/v1/subscriptions/{SUBSCRIPTION_ID}/change-plan \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "new_plan_id": "{PRO_PLAN_ID}"
     }'
   ```

3. Process payment for upgrade
   ```bash
   curl -X POST http://localhost:8002/v1/payments/process \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 70.00,
       "currency": "AED",
       "card_number": "4242424242424242",
       "card_expiry": "12/25",
       "card_cvv": "123",
       "cardholder_name": "Test User",
       "trial": false,
       "renewal": false
     }'
   ```

4. Verify plan change and new limits
   ```bash
   curl -X GET http://localhost:8001/v1/subscriptions/active \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

5. Test enterprise service (now available)
   ```bash
   for i in {1..5}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "enterprise_api_calls",
         "delta": 1
       }'
   done
   ```

**Expected Results**:
- Prorated amount calculated correctly
- Plan upgraded to Pro Plan
- **New limits**: 15 basic + 10 premium + 10 enterprise API calls
- Enterprise service now available
- Analytics feature enabled
- Previous usage preserved or reset based on business rules

#### TC12: Pro Plan Comprehensive Usage Testing
**Objective**: Test all service types with Pro Plan limits

**Prerequisites**: User with Pro Plan (15+10+10 limits)

**Steps**:
1. Use all basic API calls to near limit (13/15)
   ```bash
   for i in {1..13}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "api_calls",
         "delta": 1
       }'
   done
   ```

2. Use all premium API calls to limit (10/10)
   ```bash
   for i in {1..10}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "premium_api_calls",
         "delta": 1
       }'
   done
   ```

3. Use enterprise calls to near limit (8/10)
   ```bash
   for i in {1..8}; do
     curl -X POST http://localhost:8001/v1/usage/use \
       -H "Authorization: Bearer {JWT_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{
         "feature_name": "enterprise_api_calls",
         "delta": 1
       }'
   done
   ```

4. Check comprehensive usage status
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

5. Test remaining limits
   - 2 basic calls remaining
   - 0 premium calls remaining
   - 2 enterprise calls remaining

6. Attempt to exceed each limit
   ```bash
   # Try 3 more basic calls (should succeed for 2, fail on 3rd)
   # Try 1 more premium call (should fail)
   # Try 3 more enterprise calls (should succeed for 2, fail on 3rd)
   ```

**Expected Results**:
- Usage tracking accurate across all service types
- Limits enforced independently for each service type
- Appropriate error messages when limits exceeded
- Different error messages for different service types

---

### Phase 6: Usage Reset and Renewal Testing

#### TC13: Usage Reset After Billing Cycle
**Objective**: Verify usage limits reset after billing period

**Prerequisites**: User with Pro Plan with some usage

**Steps**:
1. Check current usage (should have some usage from previous tests)
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

2. Wait for billing cycle renewal (5 minutes in testing)
   ```bash
   # Monitor subscription for renewal
   # Or manually trigger usage reset if available
   ```

3. Check usage after reset
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

4. Test that services work again
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "api_calls",
       "delta": 1
     }'
   ```

**Expected Results**:
- Usage counts reset to 0 after billing cycle
- All service limits restored to plan maximums
- Services that were blocked become available again
- Subscription renewed successfully

#### TC14: Mixed Service Usage Patterns
**Objective**: Test realistic usage patterns with multiple service types

**Prerequisites**: User with Pro Plan (fresh limits)

**Steps**:
1. Simulate realistic API usage pattern:
   ```bash
   # Mixed usage: basic, premium, enterprise, basic, premium, basic...
   curl -X POST http://localhost:8001/v1/usage/use -H "Authorization: Bearer {JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 3}'
   
   curl -X POST http://localhost:8001/v1/usage/use -H "Authorization: Bearer {JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "premium_api_calls", "delta": 2}'
   
   curl -X POST http://localhost:8001/v1/usage/use -H "Authorization: Bearer {JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "enterprise_api_calls", "delta": 1}'
   
   curl -X POST http://localhost:8001/v1/usage/use -H "Authorization: Bearer {JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 5}'
   
   curl -X POST http://localhost:8001/v1/usage/use -H "Authorization: Bearer {JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "premium_api_calls", "delta": 3}'
   ```

2. Check intermediate usage
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

3. Continue until one service type reaches limit
4. Verify other services still work
5. Push second service type to limit
6. Verify third service type still works

**Expected Results**:
- Independent tracking for each service type
- When one service type hits limit, others remain available
- Accurate usage reporting across all service types
- Proper limit enforcement per service type

---

### Phase 7: Downgrade Scenarios and Limit Reduction

#### TC15: Downgrade from Pro to Basic Plan
**Objective**: Verify plan downgrade and limit reduction handling

**Prerequisites**: User with Pro Plan

**Steps**:
1. Initiate downgrade to Basic Plan
   ```bash
   curl -X POST http://localhost:8001/v1/subscriptions/{SUBSCRIPTION_ID}/change-plan \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "new_plan_id": "{BASIC_PLAN_ID}"
     }'
   ```

2. Process any refund if applicable
3. Verify new limits applied immediately
   ```bash
   curl -X GET http://localhost:8001/v1/subscriptions/active \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

4. Test enterprise service (should now be blocked)
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "enterprise_api_calls",
       "delta": 1
     }'
   ```

5. Verify reduced limits
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

**Expected Results**:
- Plan downgraded successfully
- **New limits**: 10 basic + 5 premium (enterprise removed)
- Enterprise service immediately blocked
- Previous enterprise usage preserved but not usable
- Analytics feature disabled
- Other services work within new limits

---

### Phase 8: Edge Cases and Error Handling

#### TC16: Concurrent Usage Requests
**Objective**: Verify race condition handling for usage tracking

**Prerequisites**: User with few remaining API calls (e.g., 2 remaining)

**Steps**:
1. Send multiple usage requests simultaneously
   ```bash
   # Terminal 1
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"feature_name": "api_calls", "delta": 1}' &

   # Terminal 2 (immediately)
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"feature_name": "api_calls", "delta": 1}' &

   # Terminal 3 (immediately)
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"feature_name": "api_calls", "delta": 1}' &
   ```

2. Check final usage count
   ```bash
   curl -X GET http://localhost:8001/v1/usage \
     -H "Authorization: Bearer {JWT_TOKEN}"
   ```

**Expected Results**:
- No race conditions in usage tracking
- Usage count accurate (only successful requests counted)
- Excess requests properly rejected
- Redis atomic operations prevent double-counting

#### TC17: Large Delta Usage Requests
**Objective**: Verify handling of large usage increments

**Prerequisites**: User with available limits

**Steps**:
1. Attempt to use large delta that exceeds remaining limit
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "api_calls",
       "delta": 100
     }'
   ```

2. Attempt to use exact remaining amount
   ```bash
   curl -X POST http://localhost:8001/v1/usage/use \
     -H "Authorization: Bearer {JWT_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "feature_name": "api_calls",
       "delta": 5
     }'
   ```

**Expected Results**:
- Large delta exceeding limit is rejected
- Exact remaining amount works correctly
- Usage tracking handles variable deltas properly

---

### Phase 9: Cross-Service Integration

#### TC18: Trial Expiration with Usage Tracking
**Objective**: Verify trial expiration behavior with usage limits

**Prerequisites**: 
- User with trial subscription (2 minutes to expire)
- Some usage recorded

**Steps**:
1. Monitor subscription and usage during trial period
2. Wait for trial expiration
3. Check usage status after expiration
4. Verify service availability after expiration

**Expected Results**:
- Usage tracking preserved during trial
- Service access blocked after trial expiration
- Renewal resets usage limits
- Proper error messages for expired subscriptions

#### TC19: Webhook Processing and Usage Updates
**Objective**: Verify webhook processing updates usage limits correctly

**Prerequisites**: Payment service and subscription service running

**Steps**:
1. Process payment that changes plan (triggers webhook)
2. Monitor webhook delivery logs
3. Verify usage limits updated based on new plan
4. Test service availability with new limits

**Expected Results**:
- Webhook delivered successfully
- Usage limits updated to reflect new plan
- Service availability matches new plan features
- No usage data lost during plan transition

---

## Test Execution Timeline

### Quick Test Run (20 minutes)
Execute core scenarios with small limits:
1. **Minutes 0-3**: User registration and trial subscription (TC01-TC04)
2. **Minutes 3-8**: Usage limit testing on trial (TC05-TC07)
3. **Minutes 8-12**: Payment and plan upgrade (TC08-TC09)
4. **Minutes 12-16**: Service usage testing on upgraded plan (TC11-TC12)
5. **Minutes 16-20**: Edge cases and limit enforcement (TC16-TC17)

### Comprehensive Test Run (45 minutes)
Execute all test scenarios including renewals:
- **Phase 1 (5 min)**: User management and authentication
- **Phase 2 (5 min)**: Trial subscription scenarios
- **Phase 3 (10 min)**: Usage limit testing on trial plan
- **Phase 4 (10 min)**: Payment processing and upgrades
- **Phase 5 (10 min)**: Plan changes and usage limit updates
- **Phase 6 (5 min)**: Usage reset and renewal testing

### Usage Limit Focus Test (15 minutes)
Dedicated testing of usage limits:
1. **Minutes 0-3**: Set up user with trial (5 API calls)
2. **Minutes 3-6**: Exhaust trial limits and test blocking
3. **Minutes 6-9**: Upgrade to Basic Plan (10+5 limits)
4. **Minutes 9-12**: Test all service types on Basic Plan
5. **Minutes 12-15**: Upgrade to Pro and test enterprise services

## Expected Results

After running the complete test suite, you should see:
- ✅ **Usage tracking accurate** across all service types
- ✅ **Limits enforced correctly** for basic/premium/enterprise services
- ✅ **Service blocking** when limits exceeded
- ✅ **Plan upgrades** immediately update available services
- ✅ **Plan downgrades** immediately restrict services
- ✅ **Usage resets** work correctly with billing cycles
- ✅ **Concurrent requests** handled without race conditions
- ✅ **Error messages** clear and actionable for each limit type

## Success Criteria for Usage Limits

The usage tracking system passes testing if:
- **Limit Enforcement**: ✅ All service types properly blocked when limits exceeded
- **Independent Tracking**: ✅ Basic/premium/enterprise usage tracked separately
- **Plan Compatibility**: ✅ Service availability matches plan features
- **Real-time Updates**: ✅ Plan changes immediately affect service availability
- **Usage Reset**: ✅ Limits reset correctly after billing cycles
- **Atomicity**: ✅ No race conditions in concurrent usage requests
- **Error Handling**: ✅ Clear error messages for different limit scenarios

This comprehensive test plan ensures that the usage tracking and limit enforcement works correctly with the small API limits for rapid testing! 🎯 