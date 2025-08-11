import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional
from fastapi import HTTPException, status, Request

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


class WebhookSignatureVerifier:
    """Industry-standard webhook signature verification using HMAC-SHA256."""
    
    @staticmethod
    def generate_signature(payload: str, timestamp: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.
        
        Format: sha256=<hex_digest>
        Payload to sign: timestamp.payload
        
        Args:
            payload: JSON string of the webhook payload
            timestamp: Unix timestamp as string
            secret: Webhook signing secret
            
        Returns:
            Signature in format: sha256=<hex_digest>
        """
        # Create signed payload: timestamp.payload_json
        signed_payload = f"{timestamp}.{payload}"
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    @staticmethod
    def verify_signature(
        payload: str,
        signature_header: str,
        timestamp_header: str,
        secret: str,
        tolerance_seconds: int = 300
    ) -> bool:
        """
        Verify webhook signature with timestamp tolerance.
        
        Args:
            payload: Raw JSON string of the webhook payload
            signature_header: Value of X-Webhook-Signature header
            timestamp_header: Value of X-Webhook-Timestamp header
            secret: Webhook signing secret
            tolerance_seconds: Maximum age of webhook in seconds
            
        Returns:
            True if signature is valid and within tolerance
            
        Raises:
            HTTPException: If verification fails
        """
        try:
            # Validate timestamp format and age
            try:
                webhook_timestamp = int(timestamp_header)
            except (ValueError, TypeError):
                logger.warning("Invalid webhook timestamp format", timestamp=timestamp_header)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid timestamp format"
                )
            
            # Check if webhook is within tolerance
            current_timestamp = int(time.time())
            age_seconds = current_timestamp - webhook_timestamp
            
            if age_seconds > tolerance_seconds:
                logger.warning(
                    "Webhook timestamp too old",
                    age_seconds=age_seconds,
                    tolerance_seconds=tolerance_seconds
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Webhook timestamp too old"
                )
            
            if age_seconds < -tolerance_seconds:
                logger.warning(
                    "Webhook timestamp too far in future",
                    age_seconds=age_seconds
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Webhook timestamp too far in future"
                )
            
            # Generate expected signature
            expected_signature = WebhookSignatureVerifier.generate_signature(
                payload, timestamp_header, secret
            )
            
            # Verify signature using constant-time comparison
            if not hmac.compare_digest(signature_header, expected_signature):
                logger.warning(
                    "Webhook signature verification failed",
                    expected_prefix=expected_signature[:20] + "...",
                    received_prefix=signature_header[:20] + "..." if len(signature_header) > 20 else signature_header
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
            
            logger.info("Webhook signature verified successfully")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Webhook signature verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Signature verification failed"
            )


async def verify_webhook_signature(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to verify webhook signatures.
    
    Expected headers:
    - X-Webhook-Signature: sha256=<hex_digest>
    - X-Webhook-Timestamp: <unix_timestamp>
    
    Returns:
        Parsed webhook payload as dict
        
    Raises:
        HTTPException: If signature verification fails
    """
    try:
        # Get required headers
        signature_header = request.headers.get("X-Webhook-Signature")
        timestamp_header = request.headers.get("X-Webhook-Timestamp")
        
        if not signature_header:
            logger.warning("Missing X-Webhook-Signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-Webhook-Signature header"
            )
        
        if not timestamp_header:
            logger.warning("Missing X-Webhook-Timestamp header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-Webhook-Timestamp header"
            )
        
        # Read raw body
        body = await request.body()
        if not body:
            logger.warning("Empty webhook payload")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty payload"
            )
        
        payload_str = body.decode('utf-8')
        
        # Verify signature
        WebhookSignatureVerifier.verify_signature(
            payload=payload_str,
            signature_header=signature_header,
            timestamp_header=timestamp_header,
            secret=settings.WEBHOOK_SIGNING_SECRET,
            tolerance_seconds=settings.WEBHOOK_TOLERANCE_SECONDS
        )
        
        # Parse and return payload
        try:
            payload_data = json.loads(payload_str)
            logger.info(
                "Webhook signature verified and payload parsed",
                event_id=payload_data.get("event_id"),
                payload_size=len(payload_str)
            )
            return payload_data
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification failed"
        ) 