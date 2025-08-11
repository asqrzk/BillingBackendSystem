from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.models.transaction import Transaction
from app.schemas.transaction import PaymentRequest, PaymentResponse
from app.schemas.gateway import MockGatewayPaymentRequest
from app.services.gateway_service import MockGatewayService
from .base_service import BaseService
from app.core.webhook_client import WebhookClient
from app.core.config import settings
from app.schemas.queue import QueueMessageEnvelope


class PaymentService(BaseService):
    """Service for payment processing operations."""
    
    def __init__(self, session):
        super().__init__(session)
        self.gateway_service = MockGatewayService()
    
    async def process_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Process a payment request."""
        try:
            # Create transaction record
            transaction_data = {
                "subscription_id": request.subscription_id,
                "amount": float(request.amount),
                "currency": request.currency,
                "status": "pending",
                "transaction_metadata": {
                    "trial": request.trial,
                    "renewal": request.renewal,
                    "card_last_four": request.card_number[-4:],
                    "cardholder_name": request.cardholder_name
                }
            }
            
            transaction = await self.transaction_repo.create(transaction_data)
            
            # Update status to processing
            await self.transaction_repo.update_status(
                transaction.id, 
                "processing"
            )
            
            # Process through mock gateway
            gateway_request = MockGatewayPaymentRequest(
                transaction_id=transaction.id,
                amount=float(request.amount),
                currency=request.currency,
                card_number=request.card_number,
                card_expiry=request.card_expiry,
                card_cvv=request.card_cvv,
                cardholder_name=request.cardholder_name,
                metadata={
                    "trial": request.trial,
                    "renewal": request.renewal
                }
            )
            
            gateway_response = await self.gateway_service.process_payment(gateway_request)
            
            # Update transaction with gateway response
            await self.transaction_repo.update_status(
                transaction.id,
                gateway_response.status,
                gateway_response.gateway_reference,
                gateway_response.message if gateway_response.status == "failed" else None
            )
            
            # For trial payments, enqueue refund initiation job (async handled by worker)
            if request.trial and gateway_response.status == "success":
                refund_message = {
                    "transaction_id": str(transaction.id),
                    "amount": float(request.amount),
                    "reason": "trial_refund"
                }
                await self.redis.queue_message("q:pay:refund_initiation", refund_message)
            
            # Queue webhook notification to subscription service
            if gateway_response.status in ["success", "failed"]:
                await self._queue_subscription_notification(transaction.id, gateway_response.status)
            
            await self.commit()
            
            self.logger.info(
                f"Payment processed",
                transaction_id=str(transaction.id),
                status=gateway_response.status,
                amount=float(request.amount)
            )
            
            # Build complete API response
            return PaymentResponse(
                transaction_id=transaction.id,
                status=gateway_response.status,
                amount=float(request.amount),
                currency=request.currency,
                gateway_reference=gateway_response.gateway_reference,
                processed_at=datetime.utcnow(),
                message=gateway_response.message,
            )
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Payment processing failed: {e}")
            raise
    
    async def get_transaction(self, transaction_id: UUID) -> Optional[Transaction]:
        """Get transaction by ID."""
        return await self.transaction_repo.get_by_id(transaction_id)
    
    async def get_subscription_transactions(self, subscription_id: UUID) -> List[Transaction]:
        """Get all transactions for a subscription."""
        return await self.transaction_repo.get_by_subscription_id(subscription_id)
    
    async def initiate_refund(self, transaction_id: UUID) -> bool:
        """Initiate refund for a transaction."""
        try:
            transaction = await self.transaction_repo.get_by_id(transaction_id)
            if not transaction or not transaction.is_successful:
                return False
            
            # Process refund through gateway
            gateway_response = await self.gateway_service.initiate_refund(
                transaction_id, 
                float(transaction.amount),
                "manual_refund"
            )
            
            # Update transaction status
            await self.transaction_repo.update_status(
                transaction_id,
                gateway_response.status,
                gateway_response.gateway_reference,
                gateway_response.message if gateway_response.status == "refund_error" else None
            )
            
            await self.commit()
            return gateway_response.status == "refund_complete"
            
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Refund initiation failed: {e}")
            return False
    
    async def _process_trial_refund(self, transaction_id: UUID, amount: float):
        """Process automatic refund for trial payment."""
        try:
            gateway_response = await self.gateway_service.initiate_refund(
                transaction_id,
                amount,
                "trial_refund"
            )
            
            # Log trial refund (don't update original transaction status)
            self.logger.info(
                f"Trial refund processed",
                transaction_id=str(transaction_id),
                refund_status=gateway_response.status,
                amount=amount
            )
            
        except Exception as e:
            self.logger.error(f"Trial refund failed: {e}")
    
    async def _queue_subscription_notification(self, transaction_id: UUID, status: str):
        """Queue webhook notification to subscription service."""
        try:
            transaction = await self.transaction_repo.get_by_id(transaction_id)
            if not transaction:
                return
            
            webhook_data = {
                "event_id": f"payment_{transaction_id}_{int(datetime.utcnow().timestamp())}",
                "transaction_id": str(transaction_id),
                "subscription_id": str(transaction.subscription_id) if transaction.subscription_id else None,
                "status": status,
                "amount": float(transaction.amount),
                "currency": transaction.currency,
                "occurred_at": datetime.utcnow().isoformat(),
                "metadata": transaction.transaction_metadata or {},
                # best-effort action flag for downstream processing
                "action": (
                    "renewal" if (transaction.transaction_metadata or {}).get("renewal") else (
                        "trial" if (transaction.transaction_metadata or {}).get("trial") else "initial"
                    )
                ),
            }
            
            # Envelop and enqueue for retryable delivery by worker
            envelope = QueueMessageEnvelope(
                action=webhook_data["action"],
                correlation_id=str(transaction.subscription_id) if transaction.subscription_id else None,
                idempotency_key=webhook_data["event_id"],
                payload=webhook_data,
            )
            await self.redis.queue_message("q:pay:subscription_update", envelope.model_dump())
            
            # Also send immediately (best-effort) to reduce latency in tests
            try:
                webhook_client = WebhookClient(
                    base_url=settings.SUBSCRIPTION_SERVICE_URL,
                    signing_secret=settings.WEBHOOK_SIGNING_SECRET
                )
                await webhook_client.send_webhook(
                    endpoint="/v1/webhooks/payment",
                    payload=webhook_data,
                    event_id=webhook_data["event_id"],
                )
                self.logger.info(
                    "Webhook notification sent immediately",
                    transaction_id=str(transaction_id),
                    status=status
                )
            except Exception as send_err:
                # Non-fatal: worker will retry via queue
                self.logger.warning(f"Immediate webhook send failed, will rely on worker: {send_err}")
            
            self.logger.info(
                f"Webhook notification queued",
                transaction_id=str(transaction_id),
                status=status
            )
            
        except Exception as e:
            self.logger.error(f"Failed to queue webhook notification: {e}") 