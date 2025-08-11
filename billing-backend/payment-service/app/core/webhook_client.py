import asyncio
import httpx
import json
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin

from .config import settings
from .webhook_security import WebhookSignatureVerifier
from .logging import get_logger

logger = get_logger(__name__)


class WebhookClient:
    """Client for sending HMAC-signed webhooks to external services."""
    
    def __init__(self, base_url: str, signing_secret: str, timeout: int = 30):
        """
        Initialize webhook client.
        
        Args:
            base_url: Base URL of the target service
            signing_secret: Secret for HMAC signature generation
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.signing_secret = signing_secret
        self.timeout = timeout
        
    async def send_webhook(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Send HMAC-signed webhook to target endpoint.
        
        Args:
            endpoint: Target endpoint path (e.g., "/v1/webhooks/payment")
            payload: Webhook payload data
            event_id: Optional event ID for tracking
            retries: Number of retry attempts
            
        Returns:
            Response data from the webhook endpoint
            
        Raises:
            httpx.HTTPError: If webhook delivery fails after retries
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        
        # Convert payload to JSON string
        payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        
        # Generate timestamp and signature
        timestamp = str(int(time.time()))
        signature = WebhookSignatureVerifier.generate_signature(
            payload_json, timestamp, self.signing_secret
        )
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp,
            "User-Agent": f"{settings.APP_NAME}/{settings.VERSION}"
        }
        
        if event_id:
            headers["X-Webhook-Event-ID"] = event_id
        
        # Send webhook with retries
        last_exception = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(
                        "Sending webhook",
                        url=url,
                        event_id=event_id,
                        attempt=attempt + 1,
                        payload_size=len(payload_json)
                    )
                    
                    response = await client.post(
                        url,
                        content=payload_json,
                        headers=headers
                    )
                    
                    # Check if successful
                    if response.status_code < 400:
                        logger.info(
                            "Webhook delivered successfully",
                            url=url,
                            event_id=event_id,
                            status_code=response.status_code,
                            response_time_ms=response.elapsed.total_seconds() * 1000
                        )
                        
                        try:
                            return response.json()
                        except json.JSONDecodeError:
                            return {"status": "success", "raw_response": response.text}
                    
                    # Log failed response
                    logger.warning(
                        "Webhook delivery failed",
                        url=url,
                        event_id=event_id,
                        status_code=response.status_code,
                        response_text=response.text[:500]
                    )
                    
                    # Don't retry for client errors (4xx)
                    if 400 <= response.status_code < 500:
                        response.raise_for_status()
                    
                    # Retry for server errors (5xx)
                    if attempt < retries:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"Retrying webhook in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
            
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Webhook timeout",
                    url=url,
                    event_id=event_id,
                    attempt=attempt + 1,
                    timeout=self.timeout
                )
                
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying webhook in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
            
            except httpx.HTTPError as e:
                last_exception = e
                logger.error(
                    "Webhook HTTP error",
                    url=url,
                    event_id=event_id,
                    attempt=attempt + 1,
                    error=str(e)
                )
                
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying webhook in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
            
            except Exception as e:
                last_exception = e
                logger.error(
                    "Webhook unexpected error",
                    url=url,
                    event_id=event_id,
                    attempt=attempt + 1,
                    error=str(e)
                )
                
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying webhook in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue
        
        # All retries exhausted
        logger.error(
            "Webhook delivery failed after all retries",
            url=url,
            event_id=event_id,
            retries=retries
        )
        
        if last_exception:
            raise last_exception
        else:
            raise httpx.HTTPError("Webhook delivery failed after all retries")


# Global webhook client instance for subscription service
subscription_webhook_client = WebhookClient(
    base_url=settings.SUBSCRIPTION_SERVICE_URL,
    signing_secret=settings.WEBHOOK_SIGNING_SECRET,
    timeout=settings.WEBHOOK_TIMEOUT_SECONDS
) 