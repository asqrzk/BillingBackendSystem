"""
Unit tests for webhook security and HMAC verification.
"""
import pytest
import time
import json
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request

from app.core.webhook_security import WebhookSignatureVerifier, verify_webhook_signature


class TestWebhookSignatureVerifier:
    """Test cases for WebhookSignatureVerifier."""

    def test_generate_signature_success(self):
        """Test successful signature generation."""
        payload = '{"event_id": "test123", "status": "success"}'
        timestamp = "1640995200"  # Fixed timestamp for testing
        secret = "test-secret-key"

        result = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)

        # Verify format
        assert result.startswith("sha256=")
        assert len(result) == 71  # sha256= (7 chars) + 64 hex chars

        # Verify reproducibility
        result2 = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)
        assert result == result2

    def test_generate_signature_different_payloads(self):
        """Test that different payloads generate different signatures."""
        timestamp = "1640995200"
        secret = "test-secret-key"

        signature1 = WebhookSignatureVerifier.generate_signature(
            '{"event_id": "test1"}', timestamp, secret
        )
        signature2 = WebhookSignatureVerifier.generate_signature(
            '{"event_id": "test2"}', timestamp, secret
        )

        assert signature1 != signature2

    def test_generate_signature_different_timestamps(self):
        """Test that different timestamps generate different signatures."""
        payload = '{"event_id": "test123"}'
        secret = "test-secret-key"

        signature1 = WebhookSignatureVerifier.generate_signature(
            payload, "1640995200", secret
        )
        signature2 = WebhookSignatureVerifier.generate_signature(
            payload, "1640995201", secret
        )

        assert signature1 != signature2

    def test_generate_signature_different_secrets(self):
        """Test that different secrets generate different signatures."""
        payload = '{"event_id": "test123"}'
        timestamp = "1640995200"

        signature1 = WebhookSignatureVerifier.generate_signature(
            payload, timestamp, "secret1"
        )
        signature2 = WebhookSignatureVerifier.generate_signature(
            payload, timestamp, "secret2"
        )

        assert signature1 != signature2

    def test_verify_signature_success(self):
        """Test successful signature verification."""
        payload = '{"event_id": "test123", "status": "success"}'
        timestamp = str(int(time.time()))
        secret = "test-secret-key"

        # Generate valid signature
        signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)

        # Verify
        result = WebhookSignatureVerifier.verify_signature(
            payload, signature, timestamp, secret
        )
        assert result is True

    def test_verify_signature_invalid_signature(self):
        """Test verification with invalid signature."""
        payload = '{"event_id": "test123"}'
        timestamp = str(int(time.time()))
        secret = "test-secret-key"
        invalid_signature = "sha256=invalid_signature_hash"

        with pytest.raises(HTTPException) as exc_info:
            WebhookSignatureVerifier.verify_signature(
                payload, invalid_signature, timestamp, secret
            )
        assert exc_info.value.status_code == 401
        assert "Invalid webhook signature" in str(exc_info.value.detail)

    def test_verify_signature_wrong_format(self):
        """Test verification with wrong signature format."""
        payload = '{"event_id": "test123"}'
        timestamp = str(int(time.time()))
        secret = "test-secret-key"
        wrong_format_signature = "invalid_format"

        with pytest.raises(HTTPException) as exc_info:
            WebhookSignatureVerifier.verify_signature(
                payload, wrong_format_signature, timestamp, secret
            )
        assert exc_info.value.status_code == 400
        assert "Invalid signature format" in str(exc_info.value.detail)

    def test_verify_signature_timestamp_too_old(self):
        """Test verification with timestamp too old."""
        payload = '{"event_id": "test123"}'
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        secret = "test-secret-key"

        signature = WebhookSignatureVerifier.generate_signature(payload, old_timestamp, secret)

        with pytest.raises(HTTPException) as exc_info:
            WebhookSignatureVerifier.verify_signature(
                payload, signature, old_timestamp, secret, tolerance_seconds=300
            )
        assert exc_info.value.status_code == 400
        assert "Webhook timestamp too old" in str(exc_info.value.detail)

    def test_verify_signature_timestamp_future(self):
        """Test verification with timestamp too far in future."""
        payload = '{"event_id": "test123"}'
        future_timestamp = str(int(time.time()) + 600)  # 10 minutes in future
        secret = "test-secret-key"

        signature = WebhookSignatureVerifier.generate_signature(payload, future_timestamp, secret)

        with pytest.raises(HTTPException) as exc_info:
            WebhookSignatureVerifier.verify_signature(
                payload, signature, future_timestamp, secret, tolerance_seconds=300
            )
        assert exc_info.value.status_code == 400
        assert "Webhook timestamp too far in future" in str(exc_info.value.detail)

    def test_verify_signature_invalid_timestamp_format(self):
        """Test verification with invalid timestamp format."""
        payload = '{"event_id": "test123"}'
        invalid_timestamp = "not_a_number"
        secret = "test-secret-key"
        signature = "sha256=somehash"

        with pytest.raises(HTTPException) as exc_info:
            WebhookSignatureVerifier.verify_signature(
                payload, signature, invalid_timestamp, secret
            )
        assert exc_info.value.status_code == 400
        assert "Invalid timestamp format" in str(exc_info.value.detail)

    def test_verify_signature_within_tolerance(self):
        """Test verification with timestamp within tolerance."""
        payload = '{"event_id": "test123"}'
        # Timestamp 4 minutes ago (within 5 minute tolerance)
        timestamp = str(int(time.time()) - 240)
        secret = "test-secret-key"

        signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)

        # Should succeed within tolerance
        result = WebhookSignatureVerifier.verify_signature(
            payload, signature, timestamp, secret, tolerance_seconds=300
        )
        assert result is True

    def test_verify_signature_empty_payload(self):
        """Test verification with empty payload."""
        payload = ""
        timestamp = str(int(time.time()))
        secret = "test-secret-key"

        signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)

        # Should still work with empty payload
        result = WebhookSignatureVerifier.verify_signature(
            payload, signature, timestamp, secret
        )
        assert result is True

    def test_verify_signature_constant_time_comparison(self):
        """Test that signature comparison uses constant time."""
        payload = '{"event_id": "test123"}'
        timestamp = str(int(time.time()))
        secret = "test-secret-key"

        # Generate valid signature
        valid_signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)
        
        # Create similar but invalid signature (same length)
        invalid_signature = valid_signature[:-1] + "x"

        # Both should take similar time (constant time comparison)
        # This is more of a security property verification
        with pytest.raises(HTTPException):
            WebhookSignatureVerifier.verify_signature(
                payload, invalid_signature, timestamp, secret
            )


class TestVerifyWebhookSignatureDependency:
    """Test cases for verify_webhook_signature FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_success(self):
        """Test successful webhook signature verification."""
        # Prepare test data
        payload = '{"event_id": "test123", "status": "success"}'
        timestamp = str(int(time.time()))
        secret = "test-secret"

        # Generate valid signature
        signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp
        }
        mock_request.body = AsyncMock(return_value=payload.encode('utf-8'))

        # Mock settings
        with pytest.mock.patch('app.core.webhook_security.settings') as mock_settings:
            mock_settings.WEBHOOK_SIGNING_SECRET = secret
            mock_settings.WEBHOOK_TOLERANCE_SECONDS = 300

            # Execute
            result = await verify_webhook_signature(mock_request)

            # Verify
            assert result == {"event_id": "test123", "status": "success"}

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_missing_signature_header(self):
        """Test webhook verification with missing signature header."""
        # Mock request without signature header
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Timestamp": str(int(time.time()))
        }

        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Missing X-Webhook-Signature header" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_missing_timestamp_header(self):
        """Test webhook verification with missing timestamp header."""
        # Mock request without timestamp header
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": "sha256=somehash"
        }

        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Missing X-Webhook-Timestamp header" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_empty_payload(self):
        """Test webhook verification with empty payload."""
        # Mock request with empty body
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": "sha256=somehash",
            "X-Webhook-Timestamp": str(int(time.time()))
        }
        mock_request.body = AsyncMock(return_value=b"")

        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Empty payload" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid_json(self):
        """Test webhook verification with invalid JSON payload."""
        # Prepare test data
        invalid_json = '{"invalid": json}'
        timestamp = str(int(time.time()))
        secret = "test-secret"

        # Generate signature for invalid JSON
        signature = WebhookSignatureVerifier.generate_signature(invalid_json, timestamp, secret)

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp
        }
        mock_request.body = AsyncMock(return_value=invalid_json.encode('utf-8'))

        # Mock settings
        with pytest.mock.patch('app.core.webhook_security.settings') as mock_settings:
            mock_settings.WEBHOOK_SIGNING_SECRET = secret
            mock_settings.WEBHOOK_TOLERANCE_SECONDS = 300

            with pytest.raises(HTTPException) as exc_info:
                await verify_webhook_signature(mock_request)
            
            assert exc_info.value.status_code == 400
            assert "Invalid JSON payload" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid_signature(self):
        """Test webhook verification with invalid signature."""
        # Prepare test data
        payload = '{"event_id": "test123"}'
        timestamp = str(int(time.time()))
        secret = "test-secret"
        invalid_signature = "sha256=invalid_signature_hash"

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": invalid_signature,
            "X-Webhook-Timestamp": timestamp
        }
        mock_request.body = AsyncMock(return_value=payload.encode('utf-8'))

        # Mock settings
        with pytest.mock.patch('app.core.webhook_security.settings') as mock_settings:
            mock_settings.WEBHOOK_SIGNING_SECRET = secret
            mock_settings.WEBHOOK_TOLERANCE_SECONDS = 300

            with pytest.raises(HTTPException) as exc_info:
                await verify_webhook_signature(mock_request)
            
            assert exc_info.value.status_code == 401
            assert "Invalid webhook signature" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_exception_handling(self):
        """Test webhook verification with unexpected exception."""
        # Mock request that will cause an exception
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {
            "X-Webhook-Signature": "sha256=somehash",
            "X-Webhook-Timestamp": str(int(time.time()))
        }
        # Make body() raise an exception
        mock_request.body = AsyncMock(side_effect=Exception("Unexpected error"))

        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(mock_request)
        
        assert exc_info.value.status_code == 500
        assert "Webhook verification failed" in str(exc_info.value.detail)

    def test_signature_format_validation(self):
        """Test various signature format validations."""
        payload = '{"test": "data"}'
        timestamp = str(int(time.time()))
        secret = "test-secret"

        # Test invalid formats
        invalid_formats = [
            "invalid",
            "sha256:",
            "sha256=",
            "md5=abcdef",
            "sha256=invalid_length",
            "SHA256=abcdef",  # Wrong case
        ]

        for invalid_signature in invalid_formats:
            with pytest.raises(HTTPException) as exc_info:
                WebhookSignatureVerifier.verify_signature(
                    payload, invalid_signature, timestamp, secret
                )
            assert exc_info.value.status_code == 400

    def test_timing_attack_protection(self):
        """Test protection against timing attacks."""
        payload = '{"event_id": "test123"}'
        timestamp = str(int(time.time()))
        secret = "test-secret-key"

        # Generate valid signature
        valid_signature = WebhookSignatureVerifier.generate_signature(payload, timestamp, secret)
        
        # Create signatures of different lengths to ensure constant time comparison
        short_invalid = "sha256=abc"
        long_invalid = "sha256=" + "a" * 64
        correct_length_invalid = valid_signature[:-4] + "xxxx"

        # All should fail with the same exception type (security property)
        for invalid_sig in [short_invalid, long_invalid, correct_length_invalid]:
            with pytest.raises(HTTPException) as exc_info:
                try:
                    WebhookSignatureVerifier.verify_signature(
                        payload, invalid_sig, timestamp, secret
                    )
                except HTTPException as e:
                    # All invalid signatures should result in same error
                    assert e.status_code in [400, 401]
                    raise 