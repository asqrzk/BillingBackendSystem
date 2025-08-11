"""
Pytest configuration and fixtures for subscription service tests.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from uuid import uuid4

# Import models and schemas for fixtures
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreateRequest, TrialSubscriptionRequest
from app.schemas.auth import UserRegisterRequest, UserLoginRequest
from app.schemas.usage import UsageCheckResponse
from app.core.redis_client import RedisClient


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
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock(spec=RedisClient)
    redis_mock.client = AsyncMock()
    redis_mock.queue_message = AsyncMock()
    redis_mock.atomic_usage_check_script = "mock_script"
    return redis_mock


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    return User(
        id=1,
        email="test@example.com",
        first_name="Test",
        last_name="User",
        hashed_password="$2b$12$hashed_password",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_plan():
    """Sample plan for testing."""
    return Plan(
        id=1,
        name="Basic Plan",
        description="Basic subscription plan",
        price=29.99,
        billing_cycle="monthly",
        features={
            "api_calls": 1000,
            "storage_gb": 10,
            "support_level": "email"
        },
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_premium_plan():
    """Sample premium plan for testing."""
    return Plan(
        id=2,
        name="Premium Plan",
        description="Premium subscription plan",
        price=99.99,
        billing_cycle="monthly",
        features={
            "api_calls": 10000,
            "storage_gb": 100,
            "support_level": "priority"
        },
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_trial_plan():
    """Sample trial plan for testing."""
    return Plan(
        id=5,
        name="Trial Plan",
        description="Free trial plan",
        price=1.00,  # Trial plans have 1 AED charge that gets refunded
        billing_cycle="monthly",
        features={
            "api_calls": 100,
            "storage_gb": 1,
            "support_level": "community",
            "trial": True,
            "period_days": 7,
            "renewal_plan": 1  # Integer reference to Basic Plan
        },
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_subscription(sample_user, sample_plan):
    """Sample active subscription for testing."""
    return Subscription(
        id=uuid4(),
        user_id=sample_user.id,
        plan_id=sample_plan.id,
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        trial_end_date=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        user=sample_user,
        plan=sample_plan
    )


@pytest.fixture
def sample_trial_subscription(sample_user, sample_trial_plan):
    """Sample trial subscription for testing."""
    return Subscription(
        id=uuid4(),
        user_id=sample_user.id,
        plan_id=sample_trial_plan.id,
        status="trial",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        trial_end_date=datetime.utcnow() + timedelta(days=7),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        user=sample_user,
        plan=sample_trial_plan
    )


@pytest.fixture
def subscription_create_request(sample_plan):
    """Sample subscription create request."""
    return SubscriptionCreateRequest(
        plan_id=sample_plan.id
    )


@pytest.fixture
def trial_subscription_request(sample_trial_plan):
    """Sample trial subscription request."""
    return TrialSubscriptionRequest(
        trial_plan_id=sample_trial_plan.id
    )


@pytest.fixture
def user_register_request():
    """Sample user registration request."""
    return UserRegisterRequest(
        email="newuser@example.com",
        password="password123",
        first_name="New",
        last_name="User"
    )


@pytest.fixture
def user_login_request():
    """Sample user login request."""
    return UserLoginRequest(
        email="test@example.com",
        password="password123"
    )


# Mock repository fixtures
@pytest.fixture
def mock_user_repo():
    """Mock user repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_email = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_plan_repo():
    """Mock plan repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_all_active = AsyncMock()
    return repo


@pytest.fixture
def mock_subscription_repo():
    """Mock subscription repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_active_subscription_by_user = AsyncMock()
    repo.get_user_subscriptions = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_usage_repo():
    """Mock usage repository."""
    repo = AsyncMock()
    repo.get_user_usage = AsyncMock()
    repo.get_user_feature_usage = AsyncMock()
    repo.create_or_update = AsyncMock()
    repo.reset_usage = AsyncMock()
    return repo


@pytest.fixture
def mock_webhook_repo():
    """Mock webhook repository."""
    repo = AsyncMock()
    repo.get_by_event_id = AsyncMock()
    repo.create_webhook_request = AsyncMock()
    repo.update = AsyncMock()
    repo.mark_processed = AsyncMock()
    return repo 