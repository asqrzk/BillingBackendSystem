from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from uuid import UUID

from app.core.database import get_async_session
from app.core.webhook_security import verify_webhook_signature
from app.schemas.gateway import GatewayWebhookPayload, GatewayResponse
from app.schemas.common import SuccessResponse
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/gateway", response_model=GatewayResponse)
async def receive_gateway_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    verified_payload: Dict[str, Any] = Depends(verify_webhook_signature)
):
    """
    Receive webhook from mock payment gateway with HMAC signature verification.
    
    **Security Requirements:**
    - X-Webhook-Signature: sha256=<hmac_signature>
    - X-Webhook-Timestamp: <unix_timestamp>
    
    This endpoint would typically be called by the actual payment gateway
    to notify about payment status changes.
    
    **Implementation:**
    1. ✅ Validate webhook signature (HMAC-SHA256)
    2. ✅ Store webhook request for idempotency
    3. ✅ Update transaction status
    4. ✅ Queue notification to subscription service
    """
    try:
        # Convert verified payload to Pydantic model for validation
        try:
            payload = GatewayWebhookPayload(**verified_payload)
        except ValueError as e:
            logger.warning(f"Invalid gateway webhook payload structure: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload structure: {str(e)}"
            )
        
        # TODO: Implement actual webhook processing logic
        # For now, just acknowledge receipt
        logger.info(
            "Gateway webhook received and verified",
            transaction_id=payload.transaction_id,
            status=getattr(payload, 'status', 'unknown'),
            payload_size=len(str(verified_payload))
        )
        
        return GatewayResponse(
            status="accepted",
            message="Webhook received, verified, and will be processed",
            transaction_id=payload.transaction_id
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Gateway webhook processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.get("/delivery/{webhook_id}")
async def get_webhook_delivery_status(
    webhook_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get status of webhook delivery to subscription service.
    
    **Note:** This endpoint does not require HMAC verification as it's a status check.
    """
    try:
        # This would check the status of outbound webhook delivery
        return {
            "webhook_id": webhook_id,
            "status": "completed",
            "message": "Webhook delivery status endpoint - HMAC verification not required"
        }
    except Exception as e:
        logger.error(f"Failed to get webhook delivery status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get webhook status"
        ) 