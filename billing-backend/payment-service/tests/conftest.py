"""
Pytest configuration and fixtures for payment service tests.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import uuid4

# Import models and schemas for fixtures
from app.models.transaction import Transaction
from app.models.gateway_webhook_request import GatewayWebhookRequest
from app.models.webhook_outbound_request import WebhookOutboundRequest
from app.schemas.payment import PaymentRequest, PaymentResponse
from app.schemas.gateway import MockGatewayPaymentRequest, MockGatewayPaymentResponse


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_payment_request():
    """Sample payment request for testing."""
    return PaymentRequest(
        amount=29.99,
        currency="USD",
        card_number="4242424242424242",
        card_expiry="12/25",
        card_cvv="123",
        cardholder_name="John Doe",
        subscription_id=uuid4()
    )


@pytest.fixture
def sample_trial_payment_request():
    """Sample trial payment request for testing."""
    return PaymentRequest(
        amount=0.00,
        currency="USD",
        card_number="4242424242424242",
        card_expiry="12/25",
        card_cvv="123",
        cardholder_name="John Doe",
        subscription_id=uuid4()
    )


@pytest.fixture
def sample_transaction():
    """Sample transaction for testing."""
    return Transaction(
        id=uuid4(),
        user_id=1,
        subscription_id=uuid4(),
        amount=29.99,
        currency="USD",
        status="completed",
        gateway_reference="gw_ref_123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_pending_transaction():
    """Sample pending transaction for testing."""
    return Transaction(
        id=uuid4(),
        user_id=1,
        subscription_id=uuid4(),
        amount=29.99,
        currency="USD",
        status="pending",
        gateway_reference=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_gateway_request():
    """Sample gateway payment request for testing."""
    return MockGatewayPaymentRequest(
        amount=29.99,
        currency="USD",
        card_number="4242424242424242",
        card_expiry="12/25",
        card_cvv="123",
        cardholder_name="John Doe",
        transaction_id=uuid4()
    )


@pytest.fixture
def sample_gateway_response_success():
    """Sample successful gateway response for testing."""
    return MockGatewayPaymentResponse(
        transaction_id=uuid4(),
        status="success",
        gateway_reference="gw_ref_123",
        message="Payment processed successfully",
        processing_time_ms=1500
    )


@pytest.fixture
def sample_gateway_response_failure():
    """Sample failed gateway response for testing."""
    return MockGatewayPaymentResponse(
        transaction_id=uuid4(),
        status="failed",
        gateway_reference=None,
        message="Card declined",
        processing_time_ms=800
    )


@pytest.fixture
def sample_webhook_outbound():
    """Sample outbound webhook request for testing."""
    return WebhookOutboundRequest(
        id=123,
        transaction_id=uuid4(),
        target_url="http://subscription-service:8000/v1/webhooks/payment",
        payload={"status": "success", "amount": 29.99},
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_gateway_webhook():
    """Sample gateway webhook request for testing."""
    return GatewayWebhookRequest(
        id=456,
        transaction_id=uuid4(),
        payload={"status": "completed", "gateway_reference": "gw_123"},
        status="processed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


# Mock repository fixtures
@pytest.fixture
def mock_transaction_repo():
    """Mock transaction repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_subscription_id = AsyncMock()
    return repo


@pytest.fixture
def mock_gateway_webhook_repo():
    """Mock gateway webhook repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_transaction_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_webhook_outbound_repo():
    """Mock webhook outbound repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_pending_webhooks = AsyncMock()
    repo.mark_completed = AsyncMock()
    return repo


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.queue_message = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_gateway_service():
    """Mock gateway service."""
    service = AsyncMock()
    service.process_payment = AsyncMock()
    return service 