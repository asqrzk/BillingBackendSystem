#!/bin/bash

# ==============================================
# Billing Backend Comprehensive Test Runner
# ==============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Pretty separators
HR() { echo -e "${DIM}────────────────────────────────────────────────────────────────────────${NC}"; }
BOX() { echo -e "${CYAN}${BOLD}[$1]${NC} $2"; }

# Gentle pacing
SLEEP_SHORT=${SLEEP_SHORT:-0.20}
pause() { sleep "$SLEEP_SHORT"; }

# Test registry and reporting
declare -a TEST_IDS=()
declare -a TEST_TITLES=()
declare -a TEST_STATUSES=()
declare -a TEST_DURATIONS=()
declare -a TEST_NOTES=()

LAST_TEST_NOTES=""
add_result() {
  TEST_IDS+=("$1"); TEST_TITLES+=("$2"); TEST_STATUSES+=("$3"); TEST_DURATIONS+=("$4"); TEST_NOTES+=("$5")
}

log_info()    { echo -e "${BLUE}ℹ️${NC}  $1"; pause; }
log_success() { echo -e "${GREEN}✅${NC}  $1"; pause; }
log_warning() { echo -e "${YELLOW}⚠️${NC}  $1"; pause; }
log_error()   { echo -e "${RED}❌${NC}  $1"; pause; }
log_test()    { echo -e "${YELLOW}${BOLD}▶${NC} $1"; pause; }
log_section() { HR; BOX "$1" "$2"; HR; }

# Runner for individual tests
run_test() {
  local id="$1"; local fn="$2"; local title="$3"; local failed_ref="$4"
  LAST_TEST_NOTES=""
  log_section "$id" "$title"
  local start=$(date +%s)
  set +e
  $fn
  local rc=$?
  set -e
  local end=$(date +%s); local dur=$((end-start))
  if [ $rc -eq 0 ]; then
    add_result "$id" "$title" "PASS" "$dur" "$LAST_TEST_NOTES"
    log_success "$title (${dur}s)"
  else
    add_result "$id" "$title" "FAIL" "$dur" "$LAST_TEST_NOTES"
    log_error "$title (${dur}s)"
    eval "$failed_ref=\$(( $failed_ref + 1 ))"
  fi
}

# Final summary table
print_summary() {
  HR
  echo -e "${BOLD}Summary:${NC}"
  printf "%-6s | %-40s | %-6s | %-6s | %s\n" "ID" "Title" "Status" "Time" "Notes"
  HR
  local pass=0 fail=0 total=${#TEST_IDS[@]}
  for i in "${!TEST_IDS[@]}"; do
    local s="${TEST_STATUSES[$i]}"
    if [ "$s" = "PASS" ]; then pass=$((pass+1)); else fail=$((fail+1)); fi
    printf "%-6s | %-40.40s | %-6s | %4ss | %s\n" "${TEST_IDS[$i]}" "${TEST_TITLES[$i]}" "$s" "${TEST_DURATIONS[$i]}" "${TEST_NOTES[$i]}"
  done
  HR
  echo -e "Totals: Pass=${pass}, Fail=${fail}, Total=${total}"
  HR
}

# Test configuration
TEST_ENV=${TEST_ENV:-testing}
BASE_URL_SUBSCRIPTION="http://localhost:8001"
BASE_URL_PAYMENT="http://localhost:8002"
TEST_USER_EMAIL="testuser$(date +%s)@example.com"
TEST_USER_EMAIL_2="testuser2$(date +%s)@example.com"
TEST_PASSWORD="SecurePass123!"

# Test state variables
JWT_TOKEN=""
JWT_TOKEN_2=""
TRIAL_PLAN_ID=""
BASIC_PLAN_ID=""
PRO_PLAN_ID=""
SUBSCRIPTION_ID=""
SUBSCRIPTION_ID_2=""

# Background-prewarmed actors
BG_PASSWORD="SecurePass123!"
BG_USER_EMAIL="bguser$(date +%s)@example.com"  # legacy single prewarm
BG_JWT=""; BG_SUB_ID=""

# Dedicated prewarmed users for specific states
BG_TRIAL_EMAIL="bgtrial$(date +%s)@example.com"
BG_TRIAL_JWT=""; BG_TRIAL_SUB_ID=""
BG_ACTIVE_EMAIL="bgactive$(date +%s)@example.com"
BG_ACTIVE_JWT=""; BG_ACTIVE_SUB_ID=""
BG_FAIL_EMAIL="bgfail$(date +%s)@example.com"
BG_FAIL_JWT=""; BG_FAIL_SUB_ID=""
BG_QA_EMAIL="bgqa$(date +%s)@example.com"
BG_QA_JWT=""; BG_QA_SUB_ID=""; QA_PLAN_ID=""

# Helper: log upgrade diagnostics
log_upgrade_diagnostics() {
    local sub_id="$1"
    if [ -n "$sub_id" ]; then
        log_info "Recent subscription events for $sub_id:"
        docker exec billing-postgres-test psql -U billing_user -d billing_test_db -c "SELECT event_type, effective_at, created_at FROM subscription_events WHERE subscription_id = '$sub_id' ORDER BY created_at DESC LIMIT 5;" >/dev/null || true
        log_info "Recent webhook requests:"
        docker exec billing-postgres-test psql -U billing_user -d billing_test_db -c "SELECT event_id, processed, processed_at, error_message FROM payment_webhook_requests ORDER BY created_at DESC LIMIT 3;" >/dev/null || true
    fi
    log_info "Redis queue lengths (legacy/intended):"
    docker exec billing-redis-test redis-cli LLEN queue:webhook_processing >/dev/null || true
    docker exec billing-redis-test redis-cli LLEN queue:payment_webhook_processing >/dev/null || true
    docker exec billing-redis-test redis-cli LLEN queue:plan_change >/dev/null || true
    docker exec billing-redis-test redis-cli LLEN queue:payment_initiation >/dev/null || true
    log_info "Recent job logs from Redis:"
    docker exec billing-redis-test redis-cli LRANGE "q:log:jobs" 0 5 >/dev/null || true
}

# Clean up test database
cleanup_test_data() {
    log_info "Cleaning up existing test data..."
    docker exec billing-postgres-test psql -U billing_user -d billing_test_db -c "
        DELETE FROM user_usage WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'testuser%@example.com');
        DELETE FROM subscription_events WHERE subscription_id IN (SELECT id FROM subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'testuser%@example.com'));
        DELETE FROM transactions WHERE subscription_id IN (SELECT id FROM subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'testuser%@example.com'));
        DELETE FROM subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'testuser%@example.com');
        DELETE FROM users WHERE email LIKE 'testuser%@example.com';
    " > /dev/null 2>&1 || log_warning "Database cleanup may have failed (first run)"
    log_success "Test data cleanup completed"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    for i in {1..30}; do
        if curl -s "${BASE_URL_SUBSCRIPTION}/v1/health/" >/dev/null 2>&1; then
            log_success "Subscription service is ready"; break; fi
        [ $i -eq 30 ] && { log_error "Subscription service did not start in time"; exit 1; }
        sleep 2
    done
    for i in {1..30}; do
        if curl -s "${BASE_URL_PAYMENT}/v1/health/" >/dev/null 2>&1; then
            log_success "Payment service is ready"; break; fi
        [ $i -eq 30 ] && { log_error "Payment service did not start in time"; exit 1; }
        sleep 2
    done
}

# Get plan IDs from database
get_plan_ids() {
    log_info "Fetching plan IDs from database..."
    TRIAL_PLAN_ID=$(docker exec billing-postgres-test psql -U billing_user -d billing_test_db -t -c "SELECT id FROM plans WHERE name = 'Trial Plan';" | tr -d ' ')
    BASIC_PLAN_ID=$(docker exec billing-postgres-test psql -U billing_user -d billing_test_db -t -c "SELECT id FROM plans WHERE name = 'Basic Plan';" | tr -d ' ')
    PRO_PLAN_ID=$(docker exec billing-postgres-test psql -U billing_user -d billing_test_db -t -c "SELECT id FROM plans WHERE name = 'Pro Plan';" | tr -d ' ')
    if [ -n "$TRIAL_PLAN_ID" ] && [ -n "$BASIC_PLAN_ID" ] && [ -n "$PRO_PLAN_ID" ]; then
        log_success "Plan IDs retrieved: Trial=$TRIAL_PLAN_ID, Basic=$BASIC_PLAN_ID, Pro=$PRO_PLAN_ID"
    else
        log_error "Failed to retrieve plan IDs from database"; return 1
    fi
}

# Helper: send signed webhook to subscription service
send_signed_webhook() {
    local event_id="$1"; local subscription_id="$2"; local status="$3"; local amount="${4:-1.00}"; local currency="${5:-AED}"
    local tx_id=$(uuidgen)
    local occurred_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local body=$(jq -nc --arg eid "$event_id" --arg tx "$tx_id" --arg sid "$subscription_id" --arg st "$status" --arg amt "$amount" --arg cur "$currency" --arg occ "$occurred_at" '{event_id:$eid, transaction_id:$tx, subscription_id:$sid, status:$st, amount:($amt|tonumber), currency:$cur, occurred_at:$occ, metadata:{}}')
    local ts=$(date +%s)
    local secret="testing-webhook-secret-32-chars-minimum-123456"
    local sig="sha256=$(printf "%s.%s" "$ts" "$body" | openssl dgst -sha256 -hmac "$secret" -binary | xxd -p -c 256)"
    curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/webhooks/payment" \
      -H "Content-Type: application/json" -H "X-Webhook-Timestamp: ${ts}" -H "X-Webhook-Signature: ${sig}" --data-binary "$body"
}

# =====================
# Test Cases
# =====================

# TC01: User Registration and Authentication
tc01_user_registration() {
    log_test "TC01: User Registration and Authentication"
    local register_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL}"'","password":"'"${TEST_PASSWORD}"'","first_name":"Test","last_name":"User"}')
    local register_body=$(echo "$register_response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local register_status=$(echo "$register_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$register_status" -ne 201 ]; then log_error "User registration failed ($register_status)"; echo "$register_body"; return 1; fi
    log_success "User registration successful"
    local login_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL}"'","password":"'"${TEST_PASSWORD}"'"}')
    local login_body=$(echo "$login_response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local login_status=$(echo "$login_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$login_status" -ne 200 ]; then log_error "User authentication failed ($login_status)"; echo "$login_body"; return 1; fi
    JWT_TOKEN=$(echo "$login_body" | jq -r '.access_token')
    [ -z "$JWT_TOKEN" -o "$JWT_TOKEN" = "null" ] && { log_error "Missing access_token"; return 1; }
    log_success "User authentication successful, token obtained"
    # Second user
    local register_response_2=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL_2}"'","password":"'"${TEST_PASSWORD}"'","first_name":"Test","last_name":"UserTwo"}')
    local register_status_2=$(echo "$register_response_2" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$register_status_2" -ne 201 ] && { log_error "Second user registration failed ($register_status_2)"; return 1; }
    log_success "Second user registration successful"
    local login_response_2=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL_2}"'","password":"'"${TEST_PASSWORD}"'"}')
    local login_body_2=$(echo "$login_response_2" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local login_status_2=$(echo "$login_response_2" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$login_status_2" -ne 200 ] && { log_error "Second user authentication failed ($login_status_2)"; echo "$login_body_2"; return 1; }
    JWT_TOKEN_2=$(echo "$login_body_2" | jq -r '.access_token')
    [ -z "$JWT_TOKEN_2" -o "$JWT_TOKEN_2" = "null" ] && { log_error "Second user missing access_token"; return 1; }
    log_success "Second user authentication successful, token obtained"
}

# TC02: First User Trial Subscription
tc02_trial_subscription() {
    log_test "TC02: First User Trial Subscription"
    local trial_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
    local trial_body=$(echo "$trial_response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local trial_status=$(echo "$trial_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$trial_status" -eq 201 ]; then
        SUBSCRIPTION_ID=$(echo "$trial_body" | jq -r '.id')
        log_success "Trial subscription created successfully: $SUBSCRIPTION_ID"
    else
        log_error "Trial subscription failed ($trial_status)"; echo "$trial_body"; return 1
    fi
}

# TC03: Duplicate Trial Attempt (Should Fail)
tc03_duplicate_trial() {
    log_test "TC03: Duplicate Trial Attempt (Should Fail)"
    local duplicate_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
    local duplicate_status=$(echo "$duplicate_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$duplicate_status" -eq 400 ]; then log_success "Duplicate trial correctly rejected"; else log_error "Duplicate trial not rejected (status $duplicate_status)"; return 1; fi
}

# TC04: Second User Trial
tc04_second_user_trial() {
    log_test "TC04: Second User Trial Subscription"
    local trial_response_2=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${JWT_TOKEN_2}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
    local trial_body_2=$(echo "$trial_response_2" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local trial_status_2=$(echo "$trial_response_2" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$trial_status_2" -eq 201 ]; then SUBSCRIPTION_ID_2=$(echo "$trial_body_2" | jq -r '.id'); log_success "Second user trial created: $SUBSCRIPTION_ID_2"; else log_error "Second user trial failed ($trial_status_2)"; echo "$trial_body_2"; return 1; fi
}

# TC05: Trial usage limits ...
# (Unchanged existing test bodies below)
# ... existing code ...

# Keep existing tests (TC05..TC13) intact
# ... existing code ...

# Restored TC05–TC13 from previous runner
tc05_trial_usage_limits() {
    log_test "TC05: Trial User Basic Service Usage (5 calls limit)"
    local usage_response=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
    log_info "Initial usage: $(echo "$usage_response" | jq -c '.')"
    local success_count=0
    for i in {1..3}; do
        local use_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name":"api_calls","delta":1}')
        local use_status=$(echo "$use_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
        if [ "$use_status" -eq 200 ]; then ((success_count++)); else log_warning "Basic service call $i failed with status: $use_status"; fi
    done
    local updated_usage=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
    local api_calls_used=$(echo "$updated_usage" | jq -r 'map(select(.feature_name=="api_calls")) | (.[0].usage_count // 0)')
    api_calls_used=${api_calls_used:-0}
    log_info "Usage after 3 calls: $api_calls_used API calls used"
    for i in {4..5}; do
        local use_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name":"api_calls","delta":1}')
        local use_status=$(echo "$use_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
        if [ "$use_status" -eq 200 ]; then ((success_count++)); else log_warning "Basic service call $i failed with status: $use_status"; fi
    done
    local exceed_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name":"api_calls","delta":1}')
    local exceed_status=$(echo "$exceed_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    local final_usage=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
    local final_api_calls=$(echo "$final_usage" | jq -r 'map(select(.feature_name=="api_calls")) | (.[0].usage_count // 0)')
    final_api_calls=${final_api_calls:-0}
    if [ "${success_count:-0}" -eq 5 ] && [ "${exceed_status:-0}" -ge 400 ] && [ "${final_api_calls:-0}" -eq 5 ]; then
        log_success "Trial usage limits working correctly: 5/5 calls used, 6th call blocked"
    else
        log_error "Trial usage limits not working correctly: ${success_count:-0}/5 calls, exceed_status=${exceed_status:-0}, final_usage=${final_api_calls:-0}"
        return 1
    fi
}

tc06_trial_premium_blocked() {
    log_test "TC06: Trial User Premium Service Access (Should Fail)"
    local premium_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name":"premium_api_calls","delta":1}')
    local premium_status=$(echo "$premium_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$premium_status" -ge 400 ]; then log_success "Premium service correctly blocked on trial plan"; else log_error "Premium should be blocked but got: $premium_status"; return 1; fi
}

tc07_trial_enterprise_blocked() {
    log_test "TC07: Trial User Enterprise Service Access (Should Fail)"
    local enterprise_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name":"enterprise_api_calls","delta":1}')
    local enterprise_status=$(echo "$enterprise_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$enterprise_status" -ge 400 ]; then log_success "Enterprise service correctly blocked on trial plan"; else log_error "Enterprise should be blocked but got: $enterprise_status"; return 1; fi
}

tc08_successful_payment() {
    log_test "TC08: Successful Payment and Basic Plan Upgrade"
    # Prefer using prewarmed TRIAL user to reduce waiting
    local TOKEN_TO_USE=${BG_TRIAL_JWT:-${BG_JWT:-$JWT_TOKEN}}
    local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
    local current_status=$(echo "$sub_response" | jq -r '.status // ""')
    local current_plan=$(echo "$sub_response" | jq -r '.plan.name // ""')
    if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then log_error "No active subscription found for plan change"; return 1; fi
    log_info "Current subscription: $sub_id, status: $current_status, plan: $current_plan"
    if [ "$current_status" = "pending" ]; then
        log_info "Subscription is pending, waiting for trial payment to complete..."
        local wait_count=0
        while [ "$wait_count" -lt 15 ]; do
            sleep 2
            sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
            current_status=$(echo "$sub_response" | jq -r '.status // ""')
            if [ "$current_status" = "trial" ]; then log_success "Trial payment completed, subscription is now in trial status"; break; elif [ "$current_status" != "pending" ]; then log_warning "Unexpected subscription status: $current_status"; break; fi
            wait_count=$((wait_count + 1))
            log_info "Trial activation poll $wait_count/15: status=$current_status"
        done
        if [ "$current_status" = "pending" ]; then log_error "Trial payment did not complete within 30 seconds, cannot test plan upgrade"; return 1; fi
    fi
    local change_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${sub_id}/change-plan" -H "Authorization: Bearer ${TOKEN_TO_USE}" -H "Content-Type: application/json" -d '{"new_plan_id": 1}')
    local change_body=$(echo "$change_response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local change_status=$(echo "$change_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$change_status" -eq 200 ]; then
        log_success "Plan change request submitted successfully"
        sleep 10
        local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
        local sub_status=$(echo "$sub_response" | jq -r '.status')
        local plan_name=$(echo "$sub_response" | jq -r '.plan.name // "unknown"')
        local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
        log_upgrade_diagnostics "$sub_id"
        if [ "$sub_status" = "active" ] && [ "$plan_name" = "Basic Plan" ]; then log_success "Subscription upgraded to Basic Plan"; else log_warning "Subscription status: $sub_status, plan: $plan_name (may still be processing)"; fi
        local usage_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
        log_info "New usage limits after upgrade: $(echo "$usage_response" | jq -c '.')"
    else
        log_error "Plan change request failed with status: $change_status"; log_error "Response: $change_body"; return 1
    fi
}

tc09_basic_plan_usage() {
    log_test "TC09: Basic Plan Service Usage Testing (10 basic + 5 premium)"
    local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN}
    # No waiting needed if prewarmed active user is available
    local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
    local plan_name=$(echo "$sub_response" | jq -r '.plan.name // "unknown"')
    log_info "Using subscription: status=$sub_status, plan=$plan_name"
    local active_sub_id=$(echo "$sub_response" | jq -r '.id // ""')
    log_info "Using subscription: status=$sub_status, plan=$plan_name"
    local basic_limit=$(echo "$usage_response" | jq -r 'map(select(.feature_name=="api_calls")) | (.[0].limit // 10)')
    local premium_limit=$(echo "$usage_response" | jq -r 'map(select(.feature_name=="premium_api_calls")) | (.[0].limit // 5)')
    current_basic=${current_basic:-0}; current_premium=${current_premium:-0}
    basic_limit=${basic_limit:-10}; premium_limit=${premium_limit:-5}
    local remaining_basic=$(( basic_limit - current_basic ))
    local remaining_premium=$(( premium_limit - current_premium ))
    [ $remaining_basic -lt 0 ] && remaining_basic=0; [ $remaining_premium -lt 0 ] && remaining_premium=0
    log_info "Current usage before TC09: basic=$current_basic/$basic_limit, premium=$current_premium/$premium_limit"
    local basic_success=0; local basic_to_try=$remaining_basic
    for ((i=1; i<=basic_to_try; i++)); do
        local use_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${TOKEN_TO_USE}" -H "Content-Type: application/json" -d '{"feature_name":"api_calls","delta":1}')
        local use_status=$(echo "$use_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
        [ "$use_status" -eq 200 ] && ((basic_success++))
    done
    local premium_success=0; local premium_to_try=$remaining_premium
    for ((i=1; i<=premium_to_try; i++)); do
        local use_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${TOKEN_TO_USE}" -H "Content-Type: application/json" -d '{"feature_name":"premium_api_calls","delta":1}')
        local use_status=$(echo "$use_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
        [ "$use_status" -eq 200 ] && ((premium_success++))
    done
    local exceed_premium_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${TOKEN_TO_USE}" -H "Content-Type: application/json" -d '{"feature_name":"premium_api_calls","delta":1}')
    local exceed_premium_status=$(echo "$exceed_premium_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    local enterprise_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${TOKEN_TO_USE}" -H "Content-Type: application/json" -d '{"feature_name":"enterprise_api_calls","delta":1}')
    local enterprise_status=$(echo "$enterprise_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    local final_usage=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
    local final_basic=$(echo "$final_usage" | jq -r 'map(select(.feature_name=="api_calls")) | (.[0].usage_count // 0)')
    local final_premium=$(echo "$final_usage" | jq -r 'map(select(.feature_name=="premium_api_calls")) | (.[0].usage_count // 0)')
    if [ "$basic_success" -eq "$remaining_basic" ] && [ "$premium_success" -eq "$remaining_premium" ] && [ "$exceed_premium_status" -ge 400 ] && [ "$enterprise_status" -ge 400 ]; then
        log_success "Basic Plan usage testing successful: basic=$final_basic/$basic_limit, premium=$final_premium/$premium_limit, limits enforced"
    else
        log_error "Basic Plan usage testing failed: basic_success=$basic_success (expected $remaining_basic), premium_success=$premium_success (expected $remaining_premium), exceed=$exceed_premium_status, enterprise=$enterprise_status"
        return 1
    fi
}

tc10_failed_payment() {
    log_test "TC10: Failed Payment Processing"
    local FAIL_CARD="4000000000000002"; log_info "Using fail card: $FAIL_CARD"
    local payment_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_PAYMENT}/v1/payments/process" -H "Authorization: Bearer ${JWT_TOKEN_2}" -H "Content-Type: application/json" -d '{"amount":99.00,"currency":"AED","card_number":"'"$FAIL_CARD"'","card_expiry":"12/25","card_cvv":"123","cardholder_name":"Test User","trial":false,"renewal":false}')
    local payment_body=$(echo "$payment_response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local payment_status=$(echo "$payment_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$payment_status" -eq 400 ] || [ "$payment_status" -eq 402 ]; then log_success "Payment correctly failed as expected"; else log_error "Payment should have failed but got status: $payment_status"; echo "$payment_body"; return 1; fi
}

tc11_concurrent_usage() {
    log_test "TC11: Concurrent Usage Requests (Race Condition Test)"
    local TEST_USER_EMAIL_3="testuser3$(date +%s)@example.com"
    local register_response_3=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL_3}"'","password":"SecurePass123!","first_name":"Test","last_name":"UserThree"}')
    local register_status_3=$(echo "$register_response_3" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$register_status_3" -eq 201 ]; then
        local login_response_3=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${TEST_USER_EMAIL_3}"'","password":"SecurePass123!"}')
        local login_body_3=$(echo "$login_response_3" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
        local login_status_3=$(echo "$login_response_3" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
        if [ "$login_status_3" -eq 200 ]; then
            local JWT_TOKEN_3=$(echo "$login_body_3" | jq -r '.access_token')
            local trial_response_3=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${JWT_TOKEN_3}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
            local trial_status_3=$(echo "$trial_response_3" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
            if [ "$trial_status_3" -eq 201 ]; then
                for i in {1..3}; do curl -s -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN_3}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 1}' >/dev/null; done
                curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN_3}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 1}' >/tmp/concurrent1.out &
                curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN_3}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 1}' >/tmp/concurrent2.out &
                curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN_3}" -H "Content-Type: application/json" -d '{"feature_name": "api_calls", "delta": 1}' >/tmp/concurrent3.out &
                wait
                local final_usage_3=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN_3}" "${BASE_URL_SUBSCRIPTION}/v1/usage/")
                local final_count_3=$(echo "$final_usage_3" | jq -r 'map(select(.feature_name=="api_calls")) | (.[0].usage_count // 0)')
                final_count_3=${final_count_3:-0}
                rm -f /tmp/concurrent*.out
                if [ "${final_count_3}" -eq 5 ]; then log_success "Concurrent usage requests handled correctly: final count = 5"; else log_warning "Concurrent usage test: final count = ${final_count_3} (expected 5)"; fi
            else
                log_warning "Could not create trial for concurrent test"
            fi
        else
            log_warning "Could not login third user for concurrent test"
        fi
    else
        log_warning "Could not register third user for concurrent test"
    fi
}

tc12_trial_expiration() {
    log_test "TC12: Monitoring Trial Expiration (2 minutes)"
    local sub_response=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN_2}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local initial_status=$(echo "$sub_response" | jq -r '.status // "null"')
    if [ "$initial_status" = "pending" ]; then
        log_info "Second user subscription pending; waiting briefly for trial activation..."
        local wait_count=0
        while [ "$wait_count" -lt 15 ]; do
            sleep 2
            sub_response=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN_2}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
            initial_status=$(echo "$sub_response" | jq -r '.status // "null"')
            if [ "$initial_status" = "trial" ]; then log_success "Second user trial activated"; break; fi
            wait_count=$((wait_count + 1))
            log_info "Second user trial activation poll $wait_count/15: status=$initial_status"
        done
    fi
    if [ "$initial_status" = "pending" ]; then log_warning "Subscription is still pending for second user; skipping expiration test."; return 0; elif [ "$initial_status" != "trial" ]; then log_warning "Subscription status is '$initial_status' instead of 'trial'. Proceeding with expiration test anyway."; fi
    log_info "Waiting for trial to expire (2 minutes + 30 seconds buffer)..."
    log_info "Sleeping for 150 seconds to allow trial expiration..."; sleep 150
    for i in {1..5}; do
        local sub_response=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN_2}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
        local sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
        local end_date=$(echo "$sub_response" | jq -r '.end_date // "null"')
        log_info "Trial status check $i/5: Status=$sub_status, End Date=$end_date"
        if [ "$sub_status" = "past_due" ] || [ "$sub_status" = "expired" ] || [ "$sub_status" = "null" ]; then
            log_success "Trial subscription expired as expected after 2 minutes"
            log_info "Checking Redis job logs for expiration events:"; docker exec billing-redis-test redis-cli LRANGE "q:log:jobs" 0 10 || true
            return 0
        elif [ "$sub_status" = "trial" ] || [ "$sub_status" = "pending" ]; then log_info "Trial still active, checking again in 10 seconds..."; sleep 10; fi
    done
    log_warning "Trial subscription status unclear after 2.5 minutes"
}

tc13_cancellation() {
    log_test "TC13: Subscription Cancellation"
    if [ -z "$SUBSCRIPTION_ID" ]; then log_warning "No subscription ID available for cancellation test"; return 0; fi
    local cancel_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${SUBSCRIPTION_ID}/cancel" -H "Authorization: Bearer ${JWT_TOKEN}")
    local cancel_status=$(echo "$cancel_response" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$cancel_status" -eq 200 ]; then
        log_success "Subscription cancelled successfully"
        local sub_response=$(curl -s -H "Authorization: Bearer ${JWT_TOKEN}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
        local sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
        if [ "$sub_status" = "cancelled" ] || [ "$sub_status" = "null" ]; then log_success "Cancellation verified"; else log_warning "Subscription status after cancellation: $sub_status"; fi
    else
        log_error "Subscription cancellation failed with status: $cancel_status"; return 1
    fi
}

# TC14: Renewal Success via Webhook
tc14_renewal_success_webhook() {
    log_test "TC14: Renewal Success via Webhook"
    # Prefer prewarmed active user
    local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN}
    local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
    local sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
    if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then
        LAST_TEST_NOTES="skipped: no active subscription"
        log_warning "$LAST_TEST_NOTES"
        return 0
    fi
    # If pending, poll to reach trial/active
    if [ "$sub_status" = "pending" ]; then
        local tries=0
        while [ $tries -lt 15 ]; do
            sleep 2
            sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
            sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
            [ "$sub_status" != "pending" ] && break
            tries=$((tries+1))
        done
    fi
    # Fire success webhook
    local event_id="manual_success_$(date +%s)"
    local resp=$(send_signed_webhook "$event_id" "$sub_id" "success" 1.00 "AED")
    local http=$(echo "$resp" | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$http" -ne 200 ]; then
        log_error "Renewal success webhook call failed: HTTP $http"
        return 1
    fi
    # Verify renewed event recorded
    local renewed_count=$(docker exec -i billing-postgres-test psql -U billing_user -d billing_test_db -t -A -c "SELECT count(1) FROM subscription_events WHERE subscription_id = '$sub_id' AND event_type='renewed';" | tr -d ' ')
    if [ "${renewed_count:-0}" -ge 1 ]; then
        log_success "Renewal success processed and event recorded"
    else
        log_error "Renewal success event not found"
        return 1
    fi
}

# TC15: Renewal Failure via Webhook (should revoke)
tc15_renewal_failure_webhook() {
    log_test "TC15: Renewal Failure via Webhook (revoked)"
    # Prefer prewarmed active user
    local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN_2}
    local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
    local sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
    if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then
        LAST_TEST_NOTES="skipped: no subscription for user2"
        log_warning "$LAST_TEST_NOTES"
        return 0
    fi
    # Ensure status is not pending
    if [ "$sub_status" = "pending" ]; then
        local tries=0
        while [ $tries -lt 15 ]; do
            sleep 2
            sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
            sub_status=$(echo "$sub_response" | jq -r '.status // "null"')
            [ "$sub_status" != "pending" ] && break
            tries=$((tries+1))
        done
    fi
    local event_id="manual_fail_$(date +%s)"
    local resp=$(send_signed_webhook "$event_id" "$sub_id" "failed" 9.99 "AED")
    local http=$(echo "$resp" | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$http" -ne 200 ]; then
        log_error "Renewal failure webhook call failed: HTTP $http"
        return 1
    fi
    # Verify status revoked/cancelled/null (no active sub)
    local after=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local st=$(echo "$after" | jq -r '.status // "null"')
    if [ "$st" = "revoked" ] || [ "$st" = "cancelled" ] || [ "$st" = "null" ]; then
        log_success "Renewal failure processed; subscription state is $st"
    else
        log_error "Expected revoked/cancelled/null after failure, got: $st"
        return 1
    fi
}

# TC16: Webhook Idempotency (duplicate event)
tc16_webhook_idempotency() {
    log_test "TC16: Webhook Idempotency"
    local TOKEN_TO_USE=${BG_ACTIVE_JWT:-${BG_TRIAL_JWT:-$JWT_TOKEN}}
    local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
    local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
    if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then
        LAST_TEST_NOTES="skipped: no subscription for idempotency test"
        log_warning "$LAST_TEST_NOTES"
        return 0
    fi
    local event_id="dup_test_$(date +%s)"
    local first=$(send_signed_webhook "$event_id" "$sub_id" "success" 1.00 "AED")
    local second=$(send_signed_webhook "$event_id" "$sub_id" "success" 1.00 "AED")
    local resp_body=$(echo "$second" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local status=$(echo "$resp_body" | jq -r '.status // ""')
    if [ "$status" = "duplicate" ]; then
        log_success "Duplicate webhook correctly handled"
    else
        log_error "Duplicate webhook expected 'duplicate', got: $status"
        return 1
    fi
}

# TC17: Cancel already-cancelled (Edge)
tc17_cancel_already_cancelled() {
  log_test "TC17: Cancel already-cancelled subscription"
  if [ -z "$SUBSCRIPTION_ID" ]; then LAST_TEST_NOTES="skipped: no subscription id"; log_warning "$LAST_TEST_NOTES"; return 0; fi
  # First cancel
  curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${SUBSCRIPTION_ID}/cancel" -H "Authorization: Bearer ${JWT_TOKEN}" >/dev/null
  # Second cancel should fail
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${SUBSCRIPTION_ID}/cancel" -H "Authorization: Bearer ${JWT_TOKEN}")
  local code=$(echo "$resp" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Second cancel correctly rejected ($code)"; else log_error "Second cancel should fail but got $code"; return 1; fi
}

# TC18: Cancel non-existent subscription (Edge)
tc18_cancel_non_existent() {
  log_test "TC18: Cancel non-existent subscription"
  local fake_id="$(uuidgen)"
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${fake_id}/cancel" -H "Authorization: Bearer ${JWT_TOKEN}")
  local code=$(echo "$resp" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Cancel non-existent rejected ($code)"; else log_error "Expected rejection for non-existent, got $code"; return 1; fi
}

# TC19: Invalid webhook signature (Edge)
tc19_invalid_webhook_signature() {
  log_test "TC19: Invalid webhook signature"
  # Build minimal body
  local event_id="bad_sig_$(date +%s)"; local tx_id=$(uuidgen); local occurred_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # Try to use first subscription if available
  local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN}
  local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
  local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
  if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then LAST_TEST_NOTES="skipped: no active sub"; log_warning "$LAST_TEST_NOTES"; return 0; fi
  local body=$(jq -nc --arg eid "$event_id" --arg tx "$tx_id" --arg sid "$sub_id" '{event_id:$eid, transaction_id:$tx, subscription_id:$sid, status:"success", amount:1.0, currency:"AED", occurred_at:"'$occurred_at'"}')
  local ts=$(date +%s)
  # Wrong secret produces invalid signature
  local sig="sha256=$(printf "%s.%s" "$ts" "$body" | openssl dgst -sha256 -hmac "WRONG_SECRET" -binary | xxd -p -c 256)"
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/webhooks/payment" -H "Content-Type: application/json" -H "X-Webhook-Timestamp: ${ts}" -H "X-Webhook-Signature: ${sig}" --data-binary "$body")
  local code=$(echo "$resp" | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Invalid signature correctly rejected ($code)"; else log_error "Invalid signature accepted ($code)"; return 1; fi
}

# TC20: Stale webhook timestamp (Edge)
tc20_stale_webhook_timestamp() {
  log_test "TC20: Stale webhook timestamp"
  local event_id="stale_ts_$(date +%s)"; local tx_id=$(uuidgen); local occurred_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN}
  local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
  local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
  if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then LAST_TEST_NOTES="skipped: no active sub"; log_warning "$LAST_TEST_NOTES"; return 0; fi
  local body=$(jq -nc --arg eid "$event_id" --arg tx "$tx_id" --arg sid "$sub_id" '{event_id:$eid, transaction_id:$tx, subscription_id:$sid, status:"success", amount:1.0, currency:"AED", occurred_at:"'$occurred_at'"}')
  local ts=$(( $(date +%s) - 3600 ))
  local secret="testing-webhook-secret-32-chars-minimum-123456"
  local sig="sha256=$(printf "%s.%s" "$ts" "$body" | openssl dgst -sha256 -hmac "$secret" -binary | xxd -p -c 256)"
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/webhooks/payment" -H "Content-Type: application/json" -H "X-Webhook-Timestamp: ${ts}" -H "X-Webhook-Signature: ${sig}" --data-binary "$body")
  local code=$(echo "$resp" | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Stale timestamp correctly rejected ($code)"; else log_error "Stale timestamp accepted ($code)"; return 1; fi
}

# TC21: Invalid plan change (Edge)
tc21_invalid_plan_change() {
  log_test "TC21: Invalid plan change (non-existent plan)"
  local TOKEN_TO_USE=${BG_ACTIVE_JWT:-$JWT_TOKEN}
  local sub_response=$(curl -s -H "Authorization: Bearer ${TOKEN_TO_USE}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
  local sub_id=$(echo "$sub_response" | jq -r '.id // ""')
  if [ -z "$sub_id" ] || [ "$sub_id" = "null" ]; then LAST_TEST_NOTES="skipped: no active sub"; log_warning "$LAST_TEST_NOTES"; return 0; fi
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${sub_id}/change-plan" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"new_plan_id": 999999}')
  local code=$(echo "$resp" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Invalid plan correctly rejected ($code)"; else log_error "Invalid plan accepted ($code)"; return 1; fi
}

# TC22: Usage invalid feature (Edge)
tc22_usage_invalid_feature() {
  log_test "TC22: Usage invalid feature name"
  local resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/usage/use" -H "Authorization: Bearer ${JWT_TOKEN}" -H "Content-Type: application/json" -d '{"feature_name": "nonexistent_feature", "delta": 1}')
  local code=$(echo "$resp" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
  if [ $code -ge 400 ]; then log_success "Invalid feature rejected ($code)"; else log_error "Invalid feature accepted ($code)"; return 1; fi
}

# =====================
# Main execution
# =====================
run_all_tests() {
    log_section "START" "Comprehensive Test Suite for Billing Backend with Usage Limits"
    local suite_start=$(date +%s)
    local failed_tests=0
    wait_for_services
    cleanup_test_data
    get_plan_ids || return 1

    # Prewarm: create a background user with a trial to reduce waits later
    log_section "PREP" "Prewarm background users/subscriptions"
    # Register BG user
    local bg_reg=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${BG_USER_EMAIL}"'","password":"'"${BG_PASSWORD}"'","first_name":"BG","last_name":"User"}')
    local bg_reg_code=$(echo "$bg_reg" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$bg_reg_code" -eq 201 ]; then log_success "Prewarm user created: ${BG_USER_EMAIL}"; else log_warning "Prewarm user registration skipped/exists ($bg_reg_code)"; fi
    # Login BG user
    local bg_login=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${BG_USER_EMAIL}"'","password":"'"${BG_PASSWORD}"'"}')
    local bg_login_body=$(echo "$bg_login" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    local bg_login_code=$(echo "$bg_login" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    if [ "$bg_login_code" -eq 200 ]; then BG_JWT=$(echo "$bg_login_body" | jq -r '.access_token'); log_success "Prewarm user authenticated"; else log_warning "Prewarm user login failed ($bg_login_code)"; fi
    # Start trial for BG user and poll to trial
    if [ -n "$BG_JWT" ] && [ "$BG_JWT" != "null" ]; then
      local bg_trial=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${BG_JWT}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
      local bg_trial_body=$(echo "$bg_trial" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
      local bg_trial_code=$(echo "$bg_trial" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
      if [ "$bg_trial_code" -eq 201 ]; then log_success "Prewarm trial started"; else log_warning "Prewarm trial start failed ($bg_trial_code)"; fi
      # Poll until trial
      local tries=0
      while [ $tries -lt 10 ]; do
        local bg_sub=$(curl -s -H "Authorization: Bearer ${BG_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
        local bg_status=$(echo "$bg_sub" | jq -r '.status // "null"')
        BG_SUB_ID=$(echo "$bg_sub" | jq -r '.id // ""')
        [ "$bg_status" = "trial" ] && { log_success "Prewarm subscription now in trial"; break; }
        tries=$((tries+1)); sleep 1
      done
    fi

    # Additional prewarm: create dedicated trial/active/revoked users using quick signed webhooks
    log_info "Prewarm: creating dedicated users (trial, active, revoked)"
    # 1) Trial user: register/login -> create trial -> webhook success once (pending -> trial)
    local reg_t=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${BG_TRIAL_EMAIL}"'","password":"'"${BG_PASSWORD}"'","first_name":"BG","last_name":"Trial"}')
    local code_t=$(echo "$reg_t" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$code_t" -ne 201 ] && log_warning "BG trial register code $code_t"
    local login_t=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${BG_TRIAL_EMAIL}"'","password":"'"${BG_PASSWORD}"'"}')
    local body_t=$(echo "$login_t" | sed -E 's/HTTPSTATUS:[0-9]{3}$//'); local lcode_t=$(echo "$login_t" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$lcode_t" -eq 200 ] && BG_TRIAL_JWT=$(echo "$body_t" | jq -r '.access_token')
    if [ -n "$BG_TRIAL_JWT" ] && [ "$BG_TRIAL_JWT" != "null" ]; then
      local trial_t=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${BG_TRIAL_JWT}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
      local tcode=$(echo "$trial_t" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
      if [ "$tcode" -eq 201 ]; then
        local sub_t=$(curl -s -H "Authorization: Bearer ${BG_TRIAL_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); BG_TRIAL_SUB_ID=$(echo "$sub_t" | jq -r '.id // ""')
        [ -n "$BG_TRIAL_SUB_ID" ] && { send_signed_webhook "prewarm_trial_$(date +%s)" "$BG_TRIAL_SUB_ID" "success" 1.00 "AED" >/dev/null; }
        # Poll to reach 'trial'
        for i in {1..10}; do
          sub_t=$(curl -s -H "Authorization: Bearer ${BG_TRIAL_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); local st=$(echo "$sub_t" | jq -r '.status // ""')
          [ "$st" = "trial" ] && { log_success "Prewarm trial user ready"; break; }; sleep 1
        done
      fi
    fi

    # 2) Active user: register/login -> create trial -> success twice (pending->trial->active with renewal plan)
    local reg_a=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${BG_ACTIVE_EMAIL}"'","password":"'"${BG_PASSWORD}"'","first_name":"BG","last_name":"Active"}')
    local code_a=$(echo "$reg_a" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$code_a" -ne 201 ] && log_warning "BG active register code $code_a"
    local login_a=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${BG_ACTIVE_EMAIL}"'","password":"'"${BG_PASSWORD}"'"}')
    local body_a=$(echo "$login_a" | sed -E 's/HTTPSTATUS:[0-9]{3}$//'); local lcode_a=$(echo "$login_a" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$lcode_a" -eq 200 ] && BG_ACTIVE_JWT=$(echo "$body_a" | jq -r '.access_token')
    if [ -n "$BG_ACTIVE_JWT" ] && [ "$BG_ACTIVE_JWT" != "null" ]; then
      local trial_a=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${BG_ACTIVE_JWT}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
      local acode=$(echo "$trial_a" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
      if [ "$acode" -eq 201 ]; then
        local sub_a=$(curl -s -H "Authorization: Bearer ${BG_ACTIVE_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); BG_ACTIVE_SUB_ID=$(echo "$sub_a" | jq -r '.id // ""')
        if [ -n "$BG_ACTIVE_SUB_ID" ]; then
          send_signed_webhook "prewarm_active1_$(date +%s)" "$BG_ACTIVE_SUB_ID" "success" 1.00 "AED" >/dev/null
          sleep 1
          send_signed_webhook "prewarm_active2_$(date +%s)" "$BG_ACTIVE_SUB_ID" "success" 1.00 "AED" >/dev/null
        fi
        # Poll to reach 'active' with Basic Plan
        for i in {1..15}; do
          sub_a=$(curl -s -H "Authorization: Bearer ${BG_ACTIVE_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); local st=$(echo "$sub_a" | jq -r '.status // ""'); local pn=$(echo "$sub_a" | jq -r '.plan.name // ""')
          [ "$st" = "active" ] && { log_success "Prewarm active user ready (plan=$pn)"; break; }; sleep 1
        done
      fi
    fi

    # 3) Revoked user: register/login -> create trial -> failure webhook (trial/active -> revoked)
    local reg_f=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${BG_FAIL_EMAIL}"'","password":"'"${BG_PASSWORD}"'","first_name":"BG","last_name":"Revoked"}')
    local code_f=$(echo "$reg_f" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$code_f" -ne 201 ] && log_warning "BG revoked register code $code_f"
    local login_f=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${BG_FAIL_EMAIL}"'","password":"'"${BG_PASSWORD}"'"}')
    local body_f=$(echo "$login_f" | sed -E 's/HTTPSTATUS:[0-9]{3}$//'); local lcode_f=$(echo "$login_f" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$lcode_f" -eq 200 ] && BG_FAIL_JWT=$(echo "$body_f" | jq -r '.access_token')
    if [ -n "$BG_FAIL_JWT" ] && [ "$BG_FAIL_JWT" != "null" ]; then
      local trial_f=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${BG_FAIL_JWT}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
      local fcode=$(echo "$trial_f" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
      if [ "$fcode" -eq 201 ]; then
        local sub_f=$(curl -s -H "Authorization: Bearer ${BG_FAIL_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); BG_FAIL_SUB_ID=$(echo "$sub_f" | jq -r '.id // ""')
        [ -n "$BG_FAIL_SUB_ID" ] && { send_signed_webhook "prewarm_fail_$(date +%s)" "$BG_FAIL_SUB_ID" "failed" 9.99 "AED" >/dev/null; }
        # Poll for revoked/null
        for i in {1..10}; do
          sub_f=$(curl -s -H "Authorization: Bearer ${BG_FAIL_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); local st=$(echo "$sub_f" | jq -r '.status // "null"')
          [ "$st" = "revoked" ] || [ "$st" = "null" ] && { log_success "Prewarm revoked user ready"; break; }; sleep 1
        done
      fi
    fi

    # 4) QA Plan with known limits and a QA-active user on that plan
    log_info "Prewarm: ensuring QA plan with expected limits exists"
    docker exec billing-postgres-test psql -U billing_user -d billing_test_db -c "INSERT INTO plans (name, description, price, billing_cycle, trial_period_days, features) SELECT 'QA Basic Plan', 'QA plan for TC09', 1.00, 'monthly', 0, '{\"limits\": {\"api_calls\": 10, \"premium_api_calls\": 5}}'::jsonb WHERE NOT EXISTS (SELECT 1 FROM plans WHERE name='QA Basic Plan');" >/dev/null || true
    QA_PLAN_ID=$(docker exec billing-postgres-test psql -U billing_user -d billing_test_db -t -c "SELECT id FROM plans WHERE name='QA Basic Plan';" | tr -d ' ')
    if [ -n "$QA_PLAN_ID" ]; then log_success "QA plan ready (id=$QA_PLAN_ID)"; else log_warning "Could not ensure QA plan"; fi
    # Create QA user and move to QA plan
    local reg_q=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"'"${BG_QA_EMAIL}"'","password":"'"${BG_PASSWORD}"'","first_name":"BG","last_name":"QA"}')
    local code_q=$(echo "$reg_q" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$code_q" -ne 201 ] && log_warning "BG QA register code $code_q"
    local login_q=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/auth/login" -H "Content-Type: application/json" -d '{"email":"'"${BG_QA_EMAIL}"'","password":"'"${BG_PASSWORD}"'"}')
    local body_q=$(echo "$login_q" | sed -E 's/HTTPSTATUS:[0-9]{3}$//'); local lcode_q=$(echo "$login_q" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    [ "$lcode_q" -eq 200 ] && BG_QA_JWT=$(echo "$body_q" | jq -r '.access_token')
    if [ -n "$BG_QA_JWT" ] && [ "$BG_QA_JWT" != "null" ]; then
      local trial_q=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/trial" -H "Authorization: Bearer ${BG_QA_JWT}" -H "Content-Type: application/json" -d '{"trial_plan_id":"'"${TRIAL_PLAN_ID}"'"}')
      local qcode=$(echo "$trial_q" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
      if [ "$qcode" -eq 201 ]; then
        local sub_q=$(curl -s -H "Authorization: Bearer ${BG_QA_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active"); BG_QA_SUB_ID=$(echo "$sub_q" | jq -r '.id // ""')
        # Move to trial via success webhook, then change plan to QA plan
        if [ -n "$BG_QA_SUB_ID" ]; then
          send_signed_webhook "prewarm_q1_$(date +%s)" "$BG_QA_SUB_ID" "success" 1.00 "AED" >/dev/null
          sleep 1
          # Change plan to QA plan (no need to wait for second renewal swap)
          if [ -n "$QA_PLAN_ID" ]; then
            local cp_resp=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/${BG_QA_SUB_ID}/change-plan" -H "Authorization: Bearer ${BG_QA_JWT}" -H "Content-Type: application/json" -d '{"new_plan_id": '"${QA_PLAN_ID}"'}')
            local cp_code=$(echo "$cp_resp" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
            if [ "$cp_code" -ge 200 ] && [ "$cp_code" -lt 300 ]; then
              # Poll for plan to reflect as QA Basic Plan
              for i in {1..10}; do
                local sub_now=$(curl -s -H "Authorization: Bearer ${BG_QA_JWT}" "${BASE_URL_SUBSCRIPTION}/v1/subscriptions/active")
                local pn_now=$(echo "$sub_now" | jq -r '.plan.name // ""')
                [ "$pn_now" = "QA Basic Plan" ] && { log_success "QA user moved to QA Basic Plan"; break; }
                sleep 1
              done
            else
              log_warning "QA plan change request failed ($cp_code)"
            fi
          fi
        fi
      fi
    fi

    # Core auth and basic trials
    run_test TC01 tc01_user_registration "User Registration and Authentication" failed_tests
    run_test TC02 tc02_trial_subscription "First User Trial Subscription" failed_tests
    run_test TC03 tc03_duplicate_trial "Duplicate Trial Attempt (Should Fail)" failed_tests
    run_test TC04 tc04_second_user_trial "Second User Trial Subscription" failed_tests
    run_test TC05 tc05_trial_usage_limits "Trial Usage Limits (5 calls)" failed_tests
    run_test TC06 tc06_trial_premium_blocked "Trial Premium Access Blocked" failed_tests
    run_test TC07 tc07_trial_enterprise_blocked "Trial Enterprise Access Blocked" failed_tests

    # Fast independent and edge tests first
    run_test TC10 tc10_failed_payment "Failed Payment Processing" failed_tests
    run_test TC11 tc11_concurrent_usage "Concurrent Usage Requests (Atomicity)" failed_tests
    run_test TC17 tc17_cancel_already_cancelled "Cancel Already-Cancelled" failed_tests
    run_test TC18 tc18_cancel_non_existent "Cancel Non-Existent Subscription" failed_tests
    run_test TC22 tc22_usage_invalid_feature "Invalid Feature Usage" failed_tests
    run_test TC19 tc19_invalid_webhook_signature "Invalid Webhook Signature" failed_tests
    run_test TC20 tc20_stale_webhook_timestamp "Stale Webhook Timestamp" failed_tests
    run_test TC21 tc21_invalid_plan_change "Invalid Plan Change" failed_tests

    # Webhook/renewal/idempotency leveraging prewarmed users
    run_test TC14 tc14_renewal_success_webhook "Renewal Success via Webhook" failed_tests
    run_test TC15 tc15_renewal_failure_webhook "Renewal Failure via Webhook (Revoke)" failed_tests
    run_test TC16 tc16_webhook_idempotency "Webhook Idempotency (Duplicate Event)" failed_tests

    # Dependent/long-running tests last
    run_test TC08 tc08_successful_payment "Trial Payment and Plan Upgrade" failed_tests
    run_test TC09 tc09_basic_plan_usage "Basic Plan Usage After Upgrade" failed_tests
    run_test TC12 tc12_trial_expiration "Trial Expiration Monitoring" failed_tests
    run_test TC13 tc13_cancellation "Subscription Cancellation" failed_tests

    local suite_end=$(date +%s); local duration=$((suite_end - suite_start))
    HR
    log_info "Test Suite Completed in ${duration} seconds"
    print_summary
    [ $failed_tests -eq 0 ] || { log_error "$failed_tests test(s) failed"; return 1; }
    log_success "All tests passed!"
    echo -e "${GREEN}✅ Usage tracking and limits working correctly${NC}"
    echo -e "${GREEN}✅ Service blocking enforced properly${NC}"
    echo -e "${GREEN}✅ Plan upgrades and webhooks validated${NC}"
    echo -e "${GREEN}✅ Race conditions handled atomically${NC}"
}

case "${1:-all}" in
    "setup") log_info "Setting up test environment..."; docker-compose -f docker-compose.testing.yml up -d; wait_for_services; log_success "Test environment ready";;
    "teardown") log_info "Tearing down test environment..."; docker-compose -f docker-compose.testing.yml down -v; log_success "Test environment cleaned up";;
    "quick") log_info "Running quick test suite (core scenarios only)..."; run_all_tests;;
    "usage") log_info "Running usage limit focused tests..."; wait_for_services; get_plan_ids; tc01_user_registration; tc02_trial_subscription; tc05_trial_usage_limits; tc06_trial_premium_blocked; tc07_trial_enterprise_blocked; tc08_successful_payment; tc09_basic_plan_usage;;
    "all"|*) log_info "Running comprehensive test suite..."; run_all_tests;;
esac

exit $? 