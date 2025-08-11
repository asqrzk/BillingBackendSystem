"""
Unit tests for WebhookService business logic.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from uuid import uuid4

from app.services.webhook_service import WebhookService
from app.schemas.webhook import WebhookPayload, WebhookResponse


class TestWebhookService:
    """Test cases for WebhookService."""

    @pytest_asyncio.fixture
    async def service(self, mock_session, mock_redis, mock_subscription_repo, mock_webhook_repo):
        """Create webhook service with mocked dependencies."""
        service = WebhookService(mock_session)
        service.redis = mock_redis
        service.subscription_repo = mock_subscription_repo
        service.webhook_repo = mock_webhook_repo
        return service

    @pytest.fixture
    def sample_webhook_payload(self):
        """Sample webhook payload."""
        return WebhookPayload(
            event_id="test-event-123",
            transaction_id=uuid4(),
            subscription_id=uuid4(),
            status="success",
            amount=29.99,
            currency="USD",
            occurred_at=datetime.utcnow()
        )

    @pytest.mark.asyncio
    async def test_process_payment_webhook_success_new(self, service, sample_webhook_payload):
        """Test processing new successful payment webhook."""
        # Setup mocks
        service.webhook_repo.get_by_event_id.return_value = None  # New webhook
        service.webhook_repo.create_webhook_request.return_value = AsyncMock()
        service.redis.queue_message.return_value = AsyncMock()

        # Execute
        result = await service.process_payment_webhook(sample_webhook_payload)

        # Verify
        assert isinstance(result, WebhookResponse)
        assert result.status == "accepted"
        assert "queued for processing" in result.message
        service.webhook_repo.get_by_event_id.assert_called_once_with("test-event-123")
        service.webhook_repo.create_webhook_request.assert_called_once()
        service.redis.queue_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_webhook_duplicate_processed(self, service, sample_webhook_payload):
        """Test processing duplicate webhook that was already processed."""
        # Setup mocks
        existing_webhook = MagicMock()
        existing_webhook.is_processed = True
        service.webhook_repo.get_by_event_id.return_value = existing_webhook

        # Execute
        result = await service.process_payment_webhook(sample_webhook_payload)

        # Verify
        assert result.status == "duplicate"
        assert "already processed" in result.message
        service.webhook_repo.create_webhook_request.assert_not_called()
        service.redis.queue_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_payment_webhook_duplicate_unprocessed(self, service, sample_webhook_payload):
        """Test processing duplicate webhook that wasn't processed yet."""
        # Setup mocks
        existing_webhook = MagicMock()
        existing_webhook.is_processed = False
        existing_webhook.id = 123
        service.webhook_repo.get_by_event_id.return_value = existing_webhook
        service.webhook_repo.update.return_value = AsyncMock()
        service.redis.queue_message.return_value = AsyncMock()

        # Execute
        result = await service.process_payment_webhook(sample_webhook_payload)

        # Verify
        assert result.status == "accepted"
        service.webhook_repo.update.assert_called_once_with(123, {
            "transaction_id": sample_webhook_payload.transaction_id,
            "payload": sample_webhook_payload.dict()
        })
        service.redis.queue_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_webhook_exception_handling(self, service, sample_webhook_payload):
        """Test webhook processing with exception."""
        # Setup mocks to raise exception
        service.webhook_repo.get_by_event_id.side_effect = Exception("Database error")

        # Execute and verify
        with pytest.raises(Exception, match="Database error"):
            await service.process_payment_webhook(sample_webhook_payload)

    @pytest.mark.asyncio
    async def test_process_webhook_event_success_payment(self, service, sample_subscription):
        """Test processing webhook event for successful payment."""
        # Setup mocks
        event_id = "test-event-123"
        payload = {
            "transaction_id": str(uuid4()),
            "subscription_id": str(sample_subscription.id),
            "status": "success",
            "amount": 29.99
        }
        
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service._handle_payment_success = AsyncMock()
        service.webhook_repo.get_by_event_id.return_value = MagicMock(id=123)
        service.webhook_repo.mark_processed.return_value = AsyncMock()

        # Execute
        result = await service.process_webhook_event(event_id, payload)

        # Verify
        assert result is True
        service.subscription_repo.get_by_id.assert_called_once()
        service._handle_payment_success.assert_called_once()
        service.webhook_repo.mark_processed.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_process_webhook_event_failed_payment(self, service, sample_subscription):
        """Test processing webhook event for failed payment."""
        # Setup mocks
        event_id = "test-event-123"
        payload = {
            "transaction_id": str(uuid4()),
            "subscription_id": str(sample_subscription.id),
            "status": "failed",
            "amount": 29.99
        }
        
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service._handle_payment_failure = AsyncMock()
        service.webhook_repo.get_by_event_id.return_value = MagicMock(id=123)
        service.webhook_repo.mark_processed.return_value = AsyncMock()

        # Execute
        result = await service.process_webhook_event(event_id, payload)

        # Verify
        assert result is True
        service._handle_payment_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_event_subscription_not_found(self, service):
        """Test processing webhook event when subscription is not found."""
        # Setup mocks
        event_id = "test-event-123"
        payload = {
            "subscription_id": str(uuid4()),
            "status": "success"
        }
        
        service.subscription_repo.get_by_id.return_value = None

        # Execute
        result = await service.process_webhook_event(event_id, payload)

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_payment_success_trial_subscription(self, service, sample_trial_subscription):
        """Test handling successful payment for trial subscription."""
        # Setup mocks
        sample_trial_subscription.status = "trial"
        transaction_id = uuid4()
        amount = 0.00  # Trial payment amount
        
        service.subscription_repo.update.return_value = AsyncMock()

        # Execute
        await service._handle_payment_success(sample_trial_subscription, transaction_id, amount)

        # Verify subscription status remains as trial for trial payments
        service.subscription_repo.update.assert_called_once()
        update_args = service.subscription_repo.update.call_args[0]
        assert update_args[0] == sample_trial_subscription.id
        # For trial, status should remain trial or be updated appropriately

    @pytest.mark.asyncio
    async def test_handle_payment_success_regular_subscription(self, service, sample_subscription):
        """Test handling successful payment for regular subscription."""
        # Setup mocks
        sample_subscription.status = "pending"
        transaction_id = uuid4()
        amount = 29.99
        
        service.subscription_repo.update.return_value = AsyncMock()

        # Execute
        await service._handle_payment_success(sample_subscription, transaction_id, amount)

        # Verify subscription is activated
        service.subscription_repo.update.assert_called_once()
        update_args = service.subscription_repo.update.call_args[0]
        assert update_args[0] == sample_subscription.id
        update_data = update_args[1]
        assert update_data["status"] == "active"

    @pytest.mark.asyncio
    async def test_handle_payment_success_renewal_subscription(self, service, sample_subscription):
        """Test handling successful payment for subscription renewal."""
        # Setup mocks
        sample_subscription.status = "active"
        transaction_id = uuid4()
        amount = 29.99
        
        service.subscription_repo.update.return_value = AsyncMock()

        # Execute
        await service._handle_payment_success(sample_subscription, transaction_id, amount)

        # Verify subscription end date is extended
        service.subscription_repo.update.assert_called_once()
        update_args = service.subscription_repo.update.call_args[0]
        update_data = update_args[1]
        assert "end_date" in update_data
        # End date should be extended based on billing cycle

    @pytest.mark.asyncio
    async def test_handle_payment_failure_pending_subscription(self, service, sample_subscription):
        """Test handling failed payment for pending subscription."""
        # Setup mocks
        sample_subscription.status = "pending"
        transaction_id = uuid4()
        amount = 29.99
        
        service.subscription_repo.update.return_value = AsyncMock()

        # Execute
        await service._handle_payment_failure(sample_subscription, transaction_id, amount)

        # Verify subscription is marked as payment_failed
        service.subscription_repo.update.assert_called_once()
        update_args = service.subscription_repo.update.call_args[0]
        update_data = update_args[1]
        assert update_data["status"] == "payment_failed"

    @pytest.mark.asyncio
    async def test_handle_payment_failure_renewal_subscription(self, service, sample_subscription):
        """Test handling failed payment for subscription renewal."""
        # Setup mocks
        sample_subscription.status = "active"
        transaction_id = uuid4()
        amount = 29.99
        
        service.subscription_repo.update.return_value = AsyncMock()

        # Execute
        await service._handle_payment_failure(sample_subscription, transaction_id, amount)

        # Verify subscription status is updated appropriately
        service.subscription_repo.update.assert_called_once()
        update_args = service.subscription_repo.update.call_args[0]
        update_data = update_args[1]
        # Should handle renewal failure appropriately

    @pytest.mark.asyncio
    async def test_get_webhook_status_found(self, service):
        """Test getting webhook status when webhook exists."""
        # Setup mocks
        event_id = "test-event-123"
        mock_webhook_status = {
            "event_id": event_id,
            "status": "processed",
            "processed_at": datetime.utcnow(),
            "retry_count": 0,
            "error_message": None
        }
        service.webhook_repo.get_webhook_status.return_value = mock_webhook_status

        # Execute
        result = await service.get_webhook_status(event_id)

        # Verify
        assert result == mock_webhook_status
        service.webhook_repo.get_webhook_status.assert_called_once_with(event_id)

    @pytest.mark.asyncio
    async def test_get_webhook_status_not_found(self, service):
        """Test getting webhook status when webhook doesn't exist."""
        # Setup mocks
        event_id = "non-existent-event"
        service.webhook_repo.get_webhook_status.return_value = None

        # Execute
        result = await service.get_webhook_status(event_id)

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_webhook_idempotency_check(self, service, sample_webhook_payload):
        """Test webhook idempotency - same event_id should not be processed twice."""
        # Setup mocks for first call
        service.webhook_repo.get_by_event_id.return_value = None
        service.webhook_repo.create_webhook_request.return_value = AsyncMock()
        service.redis.queue_message.return_value = AsyncMock()

        # First call
        result1 = await service.process_payment_webhook(sample_webhook_payload)
        assert result1.status == "accepted"

        # Setup mocks for second call (duplicate)
        existing_webhook = MagicMock()
        existing_webhook.is_processed = True
        service.webhook_repo.get_by_event_id.return_value = existing_webhook

        # Second call with same event_id
        result2 = await service.process_payment_webhook(sample_webhook_payload)
        assert result2.status == "duplicate"

    @pytest.mark.asyncio
    async def test_webhook_queue_parameters(self, service, sample_webhook_payload):
        """Test that webhook data is queued with correct parameters."""
        # Setup mocks
        service.webhook_repo.get_by_event_id.return_value = None
        service.webhook_repo.create_webhook_request.return_value = AsyncMock()
        service.redis.queue_message.return_value = AsyncMock()

        # Execute
        await service.process_payment_webhook(sample_webhook_payload)

        # Verify queue parameters
        queue_call = service.redis.queue_message.call_args[0]
        assert queue_call[0] == "queue:payment_webhook_processing"
        
        webhook_data = queue_call[1]
        assert webhook_data["event_id"] == sample_webhook_payload.event_id
        assert webhook_data["transaction_id"] == str(sample_webhook_payload.transaction_id)
        assert webhook_data["subscription_id"] == str(sample_webhook_payload.subscription_id)
        assert "max_retries" in webhook_data

    @pytest.mark.asyncio
    async def test_process_webhook_event_unknown_status(self, service, sample_subscription):
        """Test processing webhook event with unknown payment status."""
        # Setup mocks
        event_id = "test-event-123"
        payload = {
            "transaction_id": str(uuid4()),
            "subscription_id": str(sample_subscription.id),
            "status": "unknown_status",
            "amount": 29.99
        }
        
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.webhook_repo.get_by_event_id.return_value = MagicMock(id=123)
        service.webhook_repo.mark_processed.return_value = AsyncMock()

        # Execute
        result = await service.process_webhook_event(event_id, payload)

        # Verify - should still mark as processed even if status is unknown
        assert result is True
        service.webhook_repo.mark_processed.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_webhook_processing_exception_handling(self, service):
        """Test exception handling during webhook event processing."""
        # Setup mocks
        event_id = "test-event-123"
        payload = {"invalid": "payload"}
        
        service.subscription_repo.get_by_id.side_effect = Exception("Database error")

        # Execute
        result = await service.process_webhook_event(event_id, payload)

        # Verify - should return False on exception
        assert result is False 