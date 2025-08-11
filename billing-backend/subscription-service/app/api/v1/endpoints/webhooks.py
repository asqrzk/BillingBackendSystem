from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_async_session
from app.core.webhook_security import verify_webhook_signature
from app.services.webhook_service import WebhookService
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/payment", response_model=WebhookResponse)
async def process_payment_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    verified_payload: Dict[str, Any] = Depends(verify_webhook_signature)
):
    """
    Process webhook from payment service with HMAC signature verification.
    
    **Security Requirements:**
    - X-Webhook-Signature: sha256=<hmac_signature>
    - X-Webhook-Timestamp: <unix_timestamp>
    
    This endpoint receives payment status updates from the payment service
    and processes them asynchronously to update subscription statuses.
    
    **Payload Fields:**
    - **event_id**: Unique identifier for this webhook event
    - **transaction_id**: ID of the transaction
    - **subscription_id**: ID of the subscription
    - **status**: Payment status (success, failed, etc.)
    - **amount**: Payment amount
    - **currency**: Payment currency
    - **occurred_at**: When the payment event occurred
    """
    try:
        # Convert verified payload to Pydantic model for validation
        try:
            payload = WebhookPayload(**verified_payload)
        except ValueError as e:
            logger.warning(f"Invalid webhook payload structure: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload structure: {str(e)}"
            )
        
        service = WebhookService(session)
        response = await service.process_payment_webhook(payload)
        
        logger.info(
            "Payment webhook processed successfully",
            event_id=payload.event_id,
            transaction_id=payload.transaction_id,
            status=payload.status
        )
        
        return response
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process payment webhook"
        )


@router.get("/status/{event_id}")
async def get_webhook_status(
    event_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get the processing status of a webhook event.
    
    Returns information about whether the webhook has been processed,
    retry count, and any error messages.
    
    **Note:** This endpoint does not require HMAC verification as it's a status check.
    """
    try:
        service = WebhookService(session)
        status_info = await service.get_webhook_status(event_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook event not found"
            )
        
        return status_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get webhook status"
        ) 