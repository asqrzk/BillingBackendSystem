#!/usr/bin/env python3
"""
Webhook Testing Utility

This script allows you to test HMAC-signed webhooks for the billing backend system.
It generates proper signatures and sends test webhook requests.

Usage:
    python scripts/test_webhook.py --help
    python scripts/test_webhook.py subscription --event-id test123
    python scripts/test_webhook.py gateway --transaction-id 550e8400-e29b-41d4-a716-446655440001
"""

import argparse
import asyncio
import json
import time
import sys
import os
from typing import Dict, Any
from uuid import uuid4

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Default configuration
DEFAULT_CONFIG = {
    "subscription_service_url": "http://localhost:8001",
    "payment_service_url": "http://localhost:8002", 
    "webhook_secret": "dev-webhook-secret-change-in-production-32-chars-minimum",
    "timeout": 30
}


def generate_signature(payload: str, timestamp: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    import hmac
    import hashlib
    
    # Create signed payload: timestamp.payload_json
    signed_payload = f"{timestamp}.{payload}"
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={signature}"


async def send_webhook(url: str, payload: Dict[str, Any], secret: str) -> Dict[str, Any]:
    """Send HMAC-signed webhook to target URL."""
    # Convert payload to JSON string
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    # Generate timestamp and signature
    timestamp = str(int(time.time()))
    signature = generate_signature(payload_json, timestamp, secret)
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
        "User-Agent": "webhook-tester/1.0"
    }
    
    print(f"📤 Sending webhook to: {url}")
    print(f"🔐 Signature: {signature[:20]}...")
    print(f"⏰ Timestamp: {timestamp}")
    print(f"📋 Payload size: {len(payload_json)} bytes")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_CONFIG["timeout"]) as client:
            response = await client.post(
                url,
                content=payload_json,
                headers=headers
            )
            
            print(f"✅ Response: {response.status_code}")
            print(f"⏱️  Response time: {response.elapsed.total_seconds():.3f}s")
            
            try:
                response_data = response.json()
                print(f"📄 Response body:")
                print(json.dumps(response_data, indent=2))
            except json.JSONDecodeError:
                print(f"📄 Response body (text): {response.text}")
            
            return {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "response": response_data if 'response_data' in locals() else response.text
            }
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status_code": 0, "success": False, "error": str(e)}


def create_payment_webhook_payload(
    event_id: str = None,
    transaction_id: str = None,
    subscription_id: str = None,
    status: str = "success",
    amount: float = 29.00
) -> Dict[str, Any]:
    """Create payment webhook payload for subscription service."""
    return {
        "event_id": event_id or f"test_payment_{int(time.time())}",
        "transaction_id": transaction_id or str(uuid4()),
        "subscription_id": subscription_id or str(uuid4()),
        "status": status,
        "amount": amount,
        "currency": "AED",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": {
            "test": True,
            "source": "webhook_tester"
        }
    }


def create_gateway_webhook_payload(
    transaction_id: str = None,
    status: str = "completed",
    amount: float = 29.00
) -> Dict[str, Any]:
    """Create gateway webhook payload for payment service."""
    return {
        "transaction_id": transaction_id or str(uuid4()),
        "status": status,
        "amount": amount,
        "currency": "AED",
        "gateway_reference": f"gw_ref_{int(time.time())}",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": {
            "test": True,
            "source": "webhook_tester",
            "gateway": "mock"
        }
    }


async def test_subscription_webhook(args):
    """Test subscription service payment webhook."""
    print("🔔 Testing Subscription Service Payment Webhook")
    print("=" * 50)
    
    payload = create_payment_webhook_payload(
        event_id=args.event_id,
        transaction_id=args.transaction_id,
        subscription_id=args.subscription_id,
        status=args.status,
        amount=args.amount
    )
    
    url = f"{args.base_url}/v1/webhooks/payment"
    result = await send_webhook(url, payload, args.secret)
    
    return result


async def test_gateway_webhook(args):
    """Test payment service gateway webhook."""
    print("🔔 Testing Payment Service Gateway Webhook")
    print("=" * 50)
    
    payload = create_gateway_webhook_payload(
        transaction_id=args.transaction_id,
        status=args.status,
        amount=args.amount
    )
    
    url = f"{args.base_url}/v1/webhooks/gateway"
    result = await send_webhook(url, payload, args.secret)
    
    return result


async def test_invalid_signature(args):
    """Test webhook with invalid signature."""
    print("🔔 Testing Invalid Signature (Should Fail)")
    print("=" * 50)
    
    payload = create_payment_webhook_payload()
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    # Use wrong signature
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": "sha256=invalid_signature_this_should_fail",
        "X-Webhook-Timestamp": str(int(time.time())),
        "User-Agent": "webhook-tester/1.0"
    }
    
    url = f"{args.base_url}/v1/webhooks/payment"
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_CONFIG["timeout"]) as client:
            response = await client.post(url, content=payload_json, headers=headers)
            
            print(f"❌ Expected failure: {response.status_code}")
            print(f"📄 Error response: {response.text}")
            
            return {"status_code": response.status_code, "expected_failure": True}
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"error": str(e)}


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test HMAC-signed webhooks")
    parser.add_argument("service", choices=["subscription", "gateway", "invalid"], 
                       help="Which service to test")
    parser.add_argument("--base-url", 
                       help="Base URL (default: subscription=localhost:8001, gateway=localhost:8002)")
    parser.add_argument("--secret", default=DEFAULT_CONFIG["webhook_secret"],
                       help="Webhook signing secret")
    parser.add_argument("--event-id", help="Event ID for subscription webhooks")
    parser.add_argument("--transaction-id", help="Transaction ID")
    parser.add_argument("--subscription-id", help="Subscription ID")
    parser.add_argument("--status", default="success", 
                       choices=["success", "failed", "pending", "completed"],
                       help="Payment/transaction status")
    parser.add_argument("--amount", type=float, default=29.00, help="Amount")
    
    args = parser.parse_args()
    
    # Set default base URL based on service
    if not args.base_url:
        if args.service == "subscription":
            args.base_url = DEFAULT_CONFIG["subscription_service_url"]
        elif args.service == "gateway":
            args.base_url = DEFAULT_CONFIG["payment_service_url"]
        else:  # invalid
            args.base_url = DEFAULT_CONFIG["subscription_service_url"]
    
    print(f"🚀 Webhook Tester")
    print(f"🎯 Target: {args.base_url}")
    print(f"🔑 Secret: {args.secret[:10]}..." if args.secret else "None")
    print()
    
    # Run the appropriate test
    if args.service == "subscription":
        result = asyncio.run(test_subscription_webhook(args))
    elif args.service == "gateway":
        result = asyncio.run(test_gateway_webhook(args))
    elif args.service == "invalid":
        result = asyncio.run(test_invalid_signature(args))
    
    print()
    print("=" * 50)
    if result.get("success"):
        print("✅ Webhook test PASSED")
        sys.exit(0)
    elif result.get("expected_failure"):
        print("✅ Expected failure test PASSED")
        sys.exit(0)
    else:
        print("❌ Webhook test FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main() 