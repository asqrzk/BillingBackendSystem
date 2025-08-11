from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
import json

from app.models.subscription_event import SubscriptionEvent
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.core.config import settings
from .base_service import BaseService

def serialize_payload(payload: WebhookPayload) -> Dict[str, Any]:
    """Convert webhook payload to JSON-serializable dict."""
    payload_dict = payload.dict()
    
    # Convert UUIDs to strings
    if isinstance(payload_dict.get('transaction_id'), UUID):
        payload_dict['transaction_id'] = str(payload_dict['transaction_id'])
    if isinstance(payload_dict.get('subscription_id'), UUID):
        payload_dict['subscription_id'] = str(payload_dict['subscription_id'])
    
    # Convert datetime to ISO string
    if isinstance(payload_dict.get('occurred_at'), datetime):
        payload_dict['occurred_at'] = payload_dict['occurred_at'].isoformat()
    
    return payload_dict


class WebhookService(BaseService):
    """Service for handling webhook requests from payment service."""
    
    async def process_payment_webhook(self, payload: WebhookPayload) -> WebhookResponse:
        """Process incoming payment webhook."""
        try:
            # Check for duplicate webhook (idempotency)
            existing_webhook = await self.webhook_repo.get_by_event_id(payload.event_id)
            if existing_webhook:
                if existing_webhook.is_processed:
                    self.logger.info(f"Webhook already processed", event_id=payload.event_id)
                    return WebhookResponse(
                        status="duplicate",
                        message="Event already processed",
                        event_id=payload.event_id
                    )
                else:
                    # Update existing unprocessed webhook
                    await self.webhook_repo.update(existing_webhook.id, {
                        "payload": serialize_payload(payload)
                    })
            else:
                # Create new webhook request record
                await self.webhook_repo.create_webhook_request(
                    event_id=payload.event_id,
                    payload=serialize_payload(payload)
                )
            
            # Synchronous processing by design (payment service does delivery retries)
            processed = await self.process_webhook_event(payload.event_id, serialize_payload(payload))
            if not processed:
                raise RuntimeError("Webhook processing returned false")
            
            await self.commit()
            
            return WebhookResponse(
                status="processed",
                message="Webhook processed successfully",
                event_id=payload.event_id
            )
        
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Error processing payment webhook: {e}")
            raise
    
    async def process_webhook_event(self, event_id: str, payload: Dict[str, Any]) -> bool:
        """Process webhook event (called by worker)."""
        try:
            # payload dict may be the full message wrapper; unwrap if needed
            actual = payload.get("payload", payload)
            transaction_id = UUID(actual["transaction_id"]) if isinstance(actual.get("transaction_id"), str) else actual.get("transaction_id")
            subscription_id = UUID(actual["subscription_id"]) if isinstance(actual.get("subscription_id"), str) else actual.get("subscription_id")
            status = actual["status"]
            amount = actual.get("amount", 0.0)
            
            # Get subscription
            subscription = await self.subscription_repo.get_with_relationships(subscription_id)
            if not subscription:
                self.logger.error(f"Subscription not found for webhook", 
                                subscription_id=str(subscription_id),
                                event_id=event_id)
                return False
            
            # Process based on payment status
            if status == "success":
                await self._handle_payment_success(subscription, transaction_id, amount)
            elif status == "failed":
                await self._handle_payment_failure(subscription, transaction_id, amount)
            else:
                self.logger.warning(f"Unknown payment status", 
                                  status=status,
                                  event_id=event_id)
                return False
            
            # Mark webhook as processed
            webhook = await self.webhook_repo.get_by_event_id(event_id)
            if webhook:
                await self.webhook_repo.mark_processed(webhook.id)
            
            await self.commit()
            
            self.logger.info(f"Webhook event processed successfully",
                           event_id=event_id,
                           status=status,
                           subscription_id=str(subscription_id))
            
            return True
        
        except Exception as e:
            await self.rollback()
            self.logger.error(f"Error processing webhook event: {e}")
            return False
    
    async def _handle_payment_success(self, subscription, transaction_id: UUID, amount: float):
        """Handle successful payment."""
        if subscription.status == "pending":
            # If this is a trial plan, activate as 'trial'; otherwise activate as 'active'
            new_status = "trial" if subscription.plan.is_trial_plan else "active"
            await self.subscription_repo.update_status(subscription.id, new_status)
            
            # Create success event
            event_data = {
                "subscription_id": subscription.id,
                "event_type": "payment_success",
                "transaction_id": transaction_id,
                "old_plan_id": None,  # No plan change
                "new_plan_id": None,  # No plan change
                "effective_at": datetime.utcnow(),  # Effective immediately
                "event_metadata": {
                    "amount": amount,
                    "status_change": f"pending -> {new_status}"
                }
            }
        
        elif subscription.status == "past_due":
            # Reactivate past due subscription
            await self.subscription_repo.update_status(subscription.id, "active")
            
            # Create reactivation event
            event_data = {
                "subscription_id": subscription.id,
                "event_type": "payment_success",
                "transaction_id": transaction_id,
                "old_plan_id": None,  # No plan change
                "new_plan_id": None,  # No plan change
                "effective_at": datetime.utcnow(),  # Effective immediately
                "event_metadata": {
                    "amount": amount,
                    "status_change": "past_due -> active"
                }
            }
        
        elif subscription.status in ["active", "trial"]:
            # Renewal payment
            # Extend subscription dates
            if subscription.plan.billing_cycle == "yearly":
                subscription.extend_subscription()  # This adds 365 days
            else:
                subscription.extend_subscription(1)  # This adds 30 days
            
            await self.subscription_repo.update(subscription.id, {
                "end_date": subscription.end_date
            })
            
            # If on trial and there is a renewal plan configured, only switch plan on actual renewal (not initial trial activation)
            if subscription.status == "active":
                status_change = "active -> active (renewed)"
                old_plan_id = None
                new_plan_id = None
            else:  # status == trial
                renewal_plan = await self.plan_repo.get_renewal_plan(subscription.plan.id)
                if renewal_plan:
                    old_plan_id = subscription.plan.id  # Current trial plan
                    new_plan_id = renewal_plan.id       # New basic/pro plan
                    await self.subscription_repo.update(subscription.id, {"plan_id": renewal_plan.id, "status": "active"})
                    status_change = f"trial -> active ({renewal_plan.name})"
                else:
                    old_plan_id = None
                    new_plan_id = None
                    status_change = "trial -> trial (extended)"
            
            # Create renewal event
            event_data = {
                "subscription_id": subscription.id,
                "event_type": "renewed",
                "transaction_id": transaction_id,
                "old_plan_id": old_plan_id,
                "new_plan_id": new_plan_id,
                "effective_at": datetime.utcnow(),  # Effective immediately
                "event_metadata": {
                    "amount": amount,
                    "new_end_date": subscription.end_date.isoformat(),
                    "status_change": status_change
                }
            }
        
        else:
            # Unexpected subscription status
            self.logger.warning(f"Payment success for unexpected subscription status",
                              subscription_id=str(subscription.id),
                              status=subscription.status)
            return
        
        # Create the event
        event = SubscriptionEvent(**event_data)
        self.session.add(event)
    
    async def _handle_payment_failure(self, subscription, transaction_id: UUID, amount: float):
        """Handle failed payment."""
        if subscription.status == "pending":
            # Keep as pending, will be retried
            event_type = "payment_failed"
            metadata = {
                "amount": amount,
                "reason": "initial_payment_failed"
            }
        
        elif subscription.status in ["active", "trial"]:
            # Mark as revoked on renewal failure
            await self.subscription_repo.update_status(subscription.id, "revoked")
            
            event_type = "payment_failed"
            metadata = {
                "amount": amount,
                "status_change": f"{subscription.status} -> revoked",
                "reason": "renewal_payment_failed"
            }
            
            # No retry for revoked in this testing flow
        
        else:
            # Already past due or cancelled
            event_type = "payment_failed"
            metadata = {
                "amount": amount,
                "reason": "payment_failed_existing_status",
                "current_status": subscription.status
            }
        
        # Create failure event
        event_data = {
            "subscription_id": subscription.id,
            "event_type": event_type,
            "transaction_id": transaction_id,
            "old_plan_id": None,  # No plan change
            "new_plan_id": None,  # No plan change
            "effective_at": datetime.utcnow(),  # Effective immediately
            "event_metadata": metadata
        }
        
        event = SubscriptionEvent(**event_data)
        self.session.add(event)
    
    async def get_webhook_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook processing status."""
        webhook = await self.webhook_repo.get_by_event_id(event_id)
        if not webhook:
            return None
        
        return {
            "event_id": event_id,
            "processed": webhook.processed,
            "processed_at": webhook.processed_at,
            "retry_count": webhook.retry_count,
            "error_message": webhook.error_message,
            "created_at": webhook.created_at
        } 