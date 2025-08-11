"""
Unit tests for PaymentService business logic.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from uuid import uuid4

from app.services.payment_service import PaymentService
from app.models.transaction import Transaction
from app.schemas.payment import PaymentRequest, PaymentResponse


class TestPaymentService:
    """Test cases for PaymentService."""

    @pytest_asyncio.fixture
    async def service(self, mock_session, mock_transaction_repo, mock_gateway_webhook_repo, 
                     mock_webhook_outbound_repo, mock_redis, mock_gateway_service):
        """Create payment service with mocked dependencies."""
        service = PaymentService(mock_session)
        service.transaction_repo = mock_transaction_repo
        service.gateway_webhook_repo = mock_gateway_webhook_repo
        service.webhook_outbound_repo = mock_webhook_outbound_repo
        service.redis = mock_redis
        service.gateway_service = mock_gateway_service
        return service

    @pytest.mark.asyncio
    async def test_process_payment_success(self, service, sample_payment_request, 
                                         sample_gateway_response_success):
        """Test successful payment processing."""
        # Setup mocks
        created_transaction = Transaction(
            id=uuid4(),
            user_id=1,
            subscription_id=sample_payment_request.subscription_id,
            amount=sample_payment_request.amount,
            currency=sample_payment_request.currency,
            status="pending"
        )
        service.transaction_repo.create.return_value = created_transaction
        service.gateway_service.process_payment.return_value = sample_gateway_response_success
        service.transaction_repo.update.return_value = created_transaction
        service._queue_subscription_notification = AsyncMock()

        # Execute
        result = await service.process_payment(sample_payment_request, user_id=1)

        # Verify
        assert isinstance(result, PaymentResponse)
        assert result.status == "success"
        assert result.transaction_id == created_transaction.id
        assert result.amount == sample_payment_request.amount
        
        # Verify repository calls
        service.transaction_repo.create.assert_called_once()
        service.gateway_service.process_payment.assert_called_once()
        service.transaction_repo.update.assert_called()
        service._queue_subscription_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_failure(self, service, sample_payment_request, 
                                         sample_gateway_response_failure):
        """Test failed payment processing."""
        # Setup mocks
        created_transaction = Transaction(
            id=uuid4(),
            user_id=1,
            subscription_id=sample_payment_request.subscription_id,
            amount=sample_payment_request.amount,
            currency=sample_payment_request.currency,
            status="pending"
        )
        service.transaction_repo.create.return_value = created_transaction
        service.gateway_service.process_payment.return_value = sample_gateway_response_failure
        service.transaction_repo.update.return_value = created_transaction
        service._queue_subscription_notification = AsyncMock()

        # Execute
        result = await service.process_payment(sample_payment_request, user_id=1)

        # Verify
        assert result.status == "failed"
        assert "Card declined" in result.message
        service._queue_subscription_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_invalid_card_number(self, service):
        """Test payment processing with invalid card number."""
        # Create request with invalid card number
        invalid_request = PaymentRequest(
            amount=29.99,
            currency="USD",
            card_number="1234567890123456",  # Invalid card number
            card_expiry="12/25",
            card_cvv="123",
            cardholder_name="John Doe",
            subscription_id=uuid4()
        )

        # Execute and verify
        with pytest.raises(ValueError, match="Invalid card number"):
            await service.process_payment(invalid_request, user_id=1)

    @pytest.mark.asyncio
    async def test_process_payment_expired_card(self, service):
        """Test payment processing with expired card."""
        # Create request with expired card
        expired_request = PaymentRequest(
            amount=29.99,
            currency="USD",
            card_number="4242424242424242",
            card_expiry="01/20",  # Expired date
            card_cvv="123",
            cardholder_name="John Doe",
            subscription_id=uuid4()
        )

        # Execute and verify
        with pytest.raises(ValueError, match="Card has expired"):
            await service.process_payment(expired_request, user_id=1)

    @pytest.mark.asyncio
    async def test_process_payment_invalid_cvv(self, service):
        """Test payment processing with invalid CVV."""
        # Create request with invalid CVV
        invalid_cvv_request = PaymentRequest(
            amount=29.99,
            currency="USD",
            card_number="4242424242424242",
            card_expiry="12/25",
            card_cvv="12",  # Too short
            cardholder_name="John Doe",
            subscription_id=uuid4()
        )

        # Execute and verify
        with pytest.raises(ValueError, match="Invalid CVV"):
            await service.process_payment(invalid_cvv_request, user_id=1)

    @pytest.mark.asyncio
    async def test_process_payment_negative_amount(self, service):
        """Test payment processing with negative amount."""
        # Create request with negative amount
        negative_amount_request = PaymentRequest(
            amount=-10.00,
            currency="USD",
            card_number="4242424242424242",
            card_expiry="12/25",
            card_cvv="123",
            cardholder_name="John Doe",
            subscription_id=uuid4()
        )

        # Execute and verify
        with pytest.raises(ValueError, match="Amount must be positive"):
            await service.process_payment(negative_amount_request, user_id=1)

    @pytest.mark.asyncio
    async def test_process_trial_payment_success(self, service, sample_trial_payment_request):
        """Test successful trial payment processing (amount = 0)."""
        # Setup mocks
        created_transaction = Transaction(
            id=uuid4(),
            user_id=1,
            subscription_id=sample_trial_payment_request.subscription_id,
            amount=0.00,
            currency=sample_trial_payment_request.currency,
            status="pending"
        )
        service.transaction_repo.create.return_value = created_transaction
        
        # For trial payments, gateway should return success immediately
        trial_response = MagicMock()
        trial_response.status = "success"
        trial_response.gateway_reference = "trial_ref_123"
        trial_response.message = "Trial payment processed"
        service.gateway_service.process_payment.return_value = trial_response
        
        service.transaction_repo.update.return_value = created_transaction
        service._process_trial_refund = AsyncMock()
        service._queue_subscription_notification = AsyncMock()

        # Execute
        result = await service.process_payment(sample_trial_payment_request, user_id=1)

        # Verify
        assert result.status == "success"
        assert result.amount == 0.00
        service._process_trial_refund.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_payment_gateway_exception(self, service, sample_payment_request):
        """Test payment processing when gateway raises exception."""
        # Setup mocks
        created_transaction = Transaction(
            id=uuid4(),
            user_id=1,
            subscription_id=sample_payment_request.subscription_id,
            amount=sample_payment_request.amount,
            currency=sample_payment_request.currency,
            status="pending"
        )
        service.transaction_repo.create.return_value = created_transaction
        service.gateway_service.process_payment.side_effect = Exception("Gateway timeout")
        service.transaction_repo.update.return_value = created_transaction

        # Execute
        result = await service.process_payment(sample_payment_request, user_id=1)

        # Verify failure handling
        assert result.status == "failed"
        assert "Gateway timeout" in result.message

    @pytest.mark.asyncio
    async def test_get_transaction_success(self, service, sample_transaction):
        """Test getting transaction by ID."""
        # Setup mocks
        service.transaction_repo.get_by_id.return_value = sample_transaction

        # Execute
        result = await service.get_transaction(sample_transaction.id)

        # Verify
        assert result == sample_transaction
        service.transaction_repo.get_by_id.assert_called_once_with(sample_transaction.id)

    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self, service):
        """Test getting non-existent transaction."""
        # Setup mocks
        transaction_id = uuid4()
        service.transaction_repo.get_by_id.return_value = None

        # Execute
        result = await service.get_transaction(transaction_id)

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_get_subscription_transactions(self, service):
        """Test getting transactions by subscription ID."""
        # Setup mocks
        subscription_id = uuid4()
        mock_transactions = [
            Transaction(id=uuid4(), subscription_id=subscription_id, amount=29.99),
            Transaction(id=uuid4(), subscription_id=subscription_id, amount=99.99)
        ]
        service.transaction_repo.get_by_subscription_id.return_value = mock_transactions

        # Execute
        result = await service.get_subscription_transactions(subscription_id)

        # Verify
        assert len(result) == 2
        assert all(t.subscription_id == subscription_id for t in result)
        service.transaction_repo.get_by_subscription_id.assert_called_once_with(subscription_id)

    @pytest.mark.asyncio
    async def test_initiate_refund_success(self, service, sample_transaction):
        """Test successful refund initiation."""
        # Setup mocks
        sample_transaction.status = "completed"
        service.transaction_repo.get_by_id.return_value = sample_transaction
        service.transaction_repo.update.return_value = sample_transaction

        # Execute
        result = await service.initiate_refund(sample_transaction.id)

        # Verify
        assert result is True
        service.transaction_repo.update.assert_called_once()
        update_args = service.transaction_repo.update.call_args[0]
        assert update_args[1]["status"] == "refund_pending"

    @pytest.mark.asyncio
    async def test_initiate_refund_transaction_not_found(self, service):
        """Test refund initiation with non-existent transaction."""
        # Setup mocks
        transaction_id = uuid4()
        service.transaction_repo.get_by_id.return_value = None

        # Execute
        result = await service.initiate_refund(transaction_id)

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_initiate_refund_invalid_status(self, service, sample_transaction):
        """Test refund initiation with invalid transaction status."""
        # Setup mocks
        sample_transaction.status = "pending"  # Can't refund pending transaction
        service.transaction_repo.get_by_id.return_value = sample_transaction

        # Execute
        result = await service.initiate_refund(sample_transaction.id)

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_process_trial_refund(self, service, sample_transaction):
        """Test trial payment refund processing."""
        # Setup mocks
        sample_transaction.amount = 0.00
        service.transaction_repo.update.return_value = sample_transaction

        # Execute
        await service._process_trial_refund(sample_transaction.id, 0.00)

        # Verify
        service.transaction_repo.update.assert_called_once()
        update_args = service.transaction_repo.update.call_args[0]
        assert update_args[1]["refund_amount"] == 0.00

    @pytest.mark.asyncio
    async def test_queue_subscription_notification(self, service, sample_transaction):
        """Test queuing subscription notification."""
        # Execute
        await service._queue_subscription_notification(sample_transaction.id, "success")

        # Verify
        service.redis.queue_message.assert_called_once()
        queue_args = service.redis.queue_message.call_args[0]
        assert queue_args[0] == "queue:subscription_webhook_delivery"
        notification_data = queue_args[1]
        assert notification_data["transaction_id"] == str(sample_transaction.id)
        assert notification_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_card_validation_luhn_algorithm(self, service):
        """Test Luhn algorithm validation for card numbers."""
        valid_cards = [
            "4242424242424242",  # Visa test card
            "5555555555554444",  # MasterCard test card
            "378282246310005",   # American Express test card
        ]
        
        invalid_cards = [
            "4242424242424241",  # Invalid Luhn
            "1234567890123456",  # Invalid Luhn
            "0000000000000000",  # Invalid Luhn
        ]

        # Test valid cards (should not raise exception)
        for card in valid_cards:
            request = PaymentRequest(
                amount=10.00,
                currency="USD",
                card_number=card,
                card_expiry="12/25",
                card_cvv="123",
                cardholder_name="Test User",
                subscription_id=uuid4()
            )
            # This should not raise an exception during validation
            assert service._validate_card_number(card) is True

        # Test invalid cards (should raise exception)
        for card in invalid_cards:
            with pytest.raises(ValueError, match="Invalid card number"):
                service._validate_card_number(card)

    @pytest.mark.asyncio
    async def test_payment_amount_validation(self, service):
        """Test payment amount validation edge cases."""
        subscription_id = uuid4()
        
        # Test zero amount (should be allowed for trials)
        zero_request = PaymentRequest(
            amount=0.00,
            currency="USD",
            card_number="4242424242424242",
            card_expiry="12/25",
            card_cvv="123",
            cardholder_name="Test User",
            subscription_id=subscription_id
        )
        # Should not raise exception
        assert service._validate_amount(0.00) is True

        # Test very small positive amount
        small_request = PaymentRequest(
            amount=0.01,
            currency="USD",
            card_number="4242424242424242",
            card_expiry="12/25",
            card_cvv="123",
            cardholder_name="Test User",
            subscription_id=subscription_id
        )
        # Should not raise exception
        assert service._validate_amount(0.01) is True

        # Test large amount
        large_amount = 99999.99
        assert service._validate_amount(large_amount) is True

    @pytest.mark.asyncio
    async def test_currency_validation(self, service):
        """Test currency code validation."""
        valid_currencies = ["USD", "EUR", "GBP", "CAD", "AUD"]
        invalid_currencies = ["INVALID", "US", "123", ""]

        for currency in valid_currencies:
            assert service._validate_currency(currency) is True

        for currency in invalid_currencies:
            with pytest.raises(ValueError, match="Invalid currency"):
                service._validate_currency(currency)

    @pytest.mark.asyncio
    async def test_concurrent_payment_processing(self, service, sample_payment_request):
        """Test that payment processing handles concurrent requests properly."""
        # Setup mocks for concurrent processing
        created_transaction = Transaction(
            id=uuid4(),
            user_id=1,
            subscription_id=sample_payment_request.subscription_id,
            amount=sample_payment_request.amount,
            currency=sample_payment_request.currency,
            status="pending"
        )
        service.transaction_repo.create.return_value = created_transaction
        
        # Mock gateway response
        gateway_response = MagicMock()
        gateway_response.status = "success"
        gateway_response.gateway_reference = "ref_123"
        service.gateway_service.process_payment.return_value = gateway_response
        
        service.transaction_repo.update.return_value = created_transaction
        service._queue_subscription_notification = AsyncMock()

        # Execute multiple payments concurrently
        import asyncio
        tasks = [
            service.process_payment(sample_payment_request, user_id=1)
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert all(result.status == "success" for result in results)
        assert service.transaction_repo.create.call_count == 3 