import asyncio
import random
import time
from typing import Dict, Any
from uuid import UUID

from app.core.config import settings
from app.schemas.gateway import MockGatewayPaymentRequest, MockGatewayPaymentResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class MockGatewayService:
    """Mock payment gateway service that simulates payment processing."""
    
    def __init__(self):
        self.success_card = settings.PAYMENT_GATEWAY_SUCCESS_CARD
        self.fail_card = "4000000000000002"  # Specific fail card for testing
        self.success_rate = settings.GATEWAY_SUCCESS_RATE
        self.min_delay_ms = settings.GATEWAY_MIN_DELAY_MS
        self.max_delay_ms = settings.GATEWAY_MAX_DELAY_MS
    
    async def process_payment(self, request: MockGatewayPaymentRequest) -> MockGatewayPaymentResponse:
        """Process payment through mock gateway."""
        start_time = time.time()
        
        # Simulate processing delay
        delay_ms = random.randint(self.min_delay_ms, self.max_delay_ms)
        await asyncio.sleep(delay_ms / 1000.0)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        gateway_reference = f"gw_{int(time.time() * 1000)}{random.randint(1000, 9999)}"
        
        # Check for specific fail card first
        if request.card_number == self.fail_card:
            return MockGatewayPaymentResponse(
                gateway_reference=gateway_reference,
                status="failed",
                message="Payment failed: card_declined",
                processing_time_ms=processing_time_ms,
                error_code="card_declined",
                metadata={"card_last_four": request.card_number[-4:]}
            )
        
        # Determine success/failure for other cards
        is_success_card = request.card_number == self.success_card
        random_success = random.random() < self.success_rate
        
        if is_success_card or random_success:
            return MockGatewayPaymentResponse(
                gateway_reference=gateway_reference,
                status="success",
                message="Payment processed successfully",
                processing_time_ms=processing_time_ms,
                metadata={
                    "card_last_four": request.card_number[-4:],
                    "cardholder_name": request.cardholder_name
                }
            )
        else:
            error_reasons = ["insufficient_funds", "card_declined", "expired_card", "invalid_cvv"]
            error_code = random.choice(error_reasons)
            
            return MockGatewayPaymentResponse(
                gateway_reference=gateway_reference,
                status="failed", 
                message=f"Payment failed: {error_code}",
                processing_time_ms=processing_time_ms,
                error_code=error_code,
                metadata={"card_last_four": request.card_number[-4:]}
            )

    async def initiate_refund(self, transaction_id: UUID, amount: float, reason: str = "trial_refund") -> Dict[str, Any]:
        """Simulate initiating a refund with the mock gateway."""
        # Simulate processing delay
        delay_ms = random.randint(self.min_delay_ms // 2, self.max_delay_ms)
        await asyncio.sleep(delay_ms / 1000.0)
        
        refund_reference = f"rf_{int(time.time() * 1000)}{random.randint(1000, 9999)}"
        logger.info(
            "Refund initiated",
            transaction_id=str(transaction_id),
            amount=amount,
            reason=reason,
            refund_reference=refund_reference,
        )
        return {
            "refund_reference": refund_reference,
            "status": "initiated",
            "transaction_id": str(transaction_id),
            "amount": amount,
            "reason": reason,
        } 