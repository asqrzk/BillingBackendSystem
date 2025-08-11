"""
Unit tests for SubscriptionService business logic.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.subscription_service import SubscriptionService
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreateRequest, TrialSubscriptionRequest


class TestSubscriptionService:
    """Test cases for SubscriptionService."""

    @pytest_asyncio.fixture
    async def service(self, mock_session, mock_redis, mock_user_repo, mock_plan_repo, 
                     mock_subscription_repo, mock_usage_repo):
        """Create subscription service with mocked dependencies."""
        service = SubscriptionService(mock_session)
        service.redis = mock_redis
        service.user_repo = mock_user_repo
        service.plan_repo = mock_plan_repo
        service.subscription_repo = mock_subscription_repo
        service.usage_repo = mock_usage_repo
        return service

    @pytest.mark.asyncio
    async def test_create_subscription_success(self, service, sample_user, sample_plan, 
                                             subscription_create_request):
        """Test successful subscription creation."""
        # Setup mocks
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = sample_plan
        service.subscription_repo.get_active_subscription_by_user.return_value = None
        
        created_subscription = Subscription(
            id=uuid4(),
            user_id=sample_user.id,
            plan_id=sample_plan.id,
            status="pending",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        service.subscription_repo.create.return_value = created_subscription

        # Execute
        result = await service.create_subscription(subscription_create_request)

        # Verify
        assert result.user_id == sample_user.id
        assert result.plan_id == sample_plan.id
        assert result.status == "pending"
        service.user_repo.get_by_id.assert_called_once_with(subscription_create_request.user_id)
        service.plan_repo.get_by_id.assert_called_once_with(subscription_create_request.plan_id)
        service.subscription_repo.get_active_subscription_by_user.assert_called_once_with(sample_user.id)
        service.subscription_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_user_not_found(self, service, subscription_create_request):
        """Test subscription creation with non-existent user."""
        # Setup mocks
        service.user_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="User with ID .* not found"):
            await service.create_subscription(subscription_create_request)

    @pytest.mark.asyncio
    async def test_create_subscription_plan_not_found(self, service, sample_user, 
                                                    subscription_create_request):
        """Test subscription creation with non-existent plan."""
        # Setup mocks
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="Plan with ID .* not found or inactive"):
            await service.create_subscription(subscription_create_request)

    @pytest.mark.asyncio
    async def test_create_subscription_plan_inactive(self, service, sample_user, sample_plan,
                                                   subscription_create_request):
        """Test subscription creation with inactive plan."""
        # Setup mocks
        sample_plan.is_active = False
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = sample_plan

        # Execute and verify
        with pytest.raises(ValueError, match="Plan with ID .* not found or inactive"):
            await service.create_subscription(subscription_create_request)

    @pytest.mark.asyncio
    async def test_create_subscription_existing_active_subscription(self, service, sample_user, 
                                                                  sample_plan, sample_subscription,
                                                                  subscription_create_request):
        """Test subscription creation when user already has active subscription."""
        # Setup mocks
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = sample_plan
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription

        # Execute and verify
        with pytest.raises(ValueError, match="User .* already has an active subscription"):
            await service.create_subscription(subscription_create_request)

    @pytest.mark.asyncio
    async def test_create_subscription_yearly_billing(self, service, sample_user, sample_plan,
                                                     subscription_create_request):
        """Test subscription creation with yearly billing cycle."""
        # Setup mocks
        sample_plan.billing_cycle = "yearly"
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = sample_plan
        service.subscription_repo.get_active_subscription_by_user.return_value = None
        
        created_subscription = Subscription(
            id=uuid4(),
            user_id=sample_user.id,
            plan_id=sample_plan.id,
            status="pending",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=365)
        )
        service.subscription_repo.create.return_value = created_subscription

        # Execute
        result = await service.create_subscription(subscription_create_request)

        # Verify end date is set to one year from now (approximately)
        expected_end_date = datetime.utcnow() + timedelta(days=365)
        assert abs((result.end_date - expected_end_date).total_seconds()) < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_create_trial_subscription_success(self, service, sample_user, sample_trial_plan,
                                                   trial_subscription_request):
        """Test successful trial subscription creation."""
        # Setup mocks
        service.user_repo.get_by_id.return_value = sample_user
        service.plan_repo.get_by_id.return_value = sample_trial_plan
        service.subscription_repo.get_active_subscription_by_user.return_value = None
        
        created_subscription = Subscription(
            id=uuid4(),
            user_id=sample_user.id,
            plan_id=sample_trial_plan.id,
            status="trial",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            trial_end_date=datetime.utcnow() + timedelta(days=7)
        )
        service.subscription_repo.create.return_value = created_subscription

        # Execute with user_id = 1
        result = await service.create_trial_subscription(trial_subscription_request, user_id=1)

        # Verify
        assert result.status == "trial"
        assert result.trial_end_date is not None
        service.subscription_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_subscription_success(self, service, sample_subscription):
        """Test successful subscription cancellation."""
        # Setup mocks
        sample_subscription.status = "active"
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.subscription_repo.update.return_value = sample_subscription

        # Execute
        result = await service.cancel_subscription(sample_subscription.id)

        # Verify
        service.subscription_repo.update.assert_called_once()
        update_call_args = service.subscription_repo.update.call_args[0]
        assert update_call_args[0] == sample_subscription.id
        assert "cancelled" in str(update_call_args[1])  # Status should be cancelled

    @pytest.mark.asyncio
    async def test_cancel_subscription_not_found(self, service):
        """Test cancelling non-existent subscription."""
        # Setup mocks
        subscription_id = uuid4()
        service.subscription_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="Subscription .* not found"):
            await service.cancel_subscription(subscription_id)

    @pytest.mark.asyncio
    async def test_cancel_subscription_already_cancelled(self, service, sample_subscription):
        """Test cancelling already cancelled subscription."""
        # Setup mocks
        sample_subscription.status = "cancelled"
        service.subscription_repo.get_by_id.return_value = sample_subscription

        # Execute and verify
        with pytest.raises(ValueError, match="Subscription is not active"):
            await service.cancel_subscription(sample_subscription.id)

    @pytest.mark.asyncio
    async def test_change_plan_success(self, service, sample_subscription, sample_premium_plan):
        """Test successful plan change."""
        # Setup mocks
        sample_subscription.status = "active"
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.plan_repo.get_by_id.return_value = sample_premium_plan
        service.subscription_repo.update.return_value = sample_subscription

        # Execute
        result = await service.change_plan(sample_subscription.id, sample_premium_plan.id)

        # Verify
        service.subscription_repo.update.assert_called_once()
        update_call_args = service.subscription_repo.update.call_args[0]
        assert update_call_args[1]["plan_id"] == sample_premium_plan.id

    @pytest.mark.asyncio
    async def test_change_plan_subscription_not_found(self, service, sample_premium_plan):
        """Test plan change with non-existent subscription."""
        # Setup mocks
        subscription_id = uuid4()
        service.subscription_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="Subscription .* not found"):
            await service.change_plan(subscription_id, sample_premium_plan.id)

    @pytest.mark.asyncio
    async def test_change_plan_new_plan_not_found(self, service, sample_subscription):
        """Test plan change with non-existent new plan."""
        # Setup mocks
        sample_subscription.status = "active"
        new_plan_id = uuid4()
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.plan_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="New plan .* not found or inactive"):
            await service.change_plan(sample_subscription.id, new_plan_id)

    @pytest.mark.asyncio
    async def test_change_plan_same_plan(self, service, sample_subscription, sample_plan):
        """Test plan change to the same plan."""
        # Setup mocks
        sample_subscription.status = "active"
        sample_subscription.plan_id = sample_plan.id
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.plan_repo.get_by_id.return_value = sample_plan

        # Execute and verify
        with pytest.raises(ValueError, match="Subscription is already on this plan"):
            await service.change_plan(sample_subscription.id, sample_plan.id)

    @pytest.mark.asyncio
    async def test_get_active_subscription_success(self, service, sample_subscription):
        """Test getting active subscription."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription

        # Execute
        result = await service.get_active_subscription(sample_subscription.user_id)

        # Verify
        assert result == sample_subscription
        service.subscription_repo.get_active_subscription_by_user.assert_called_once_with(
            sample_subscription.user_id
        )

    @pytest.mark.asyncio
    async def test_get_active_subscription_none_found(self, service):
        """Test getting active subscription when none exists."""
        # Setup mocks
        user_id = 1
        service.subscription_repo.get_active_subscription_by_user.return_value = None

        # Execute
        result = await service.get_active_subscription(user_id)

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_process_subscription_renewal_success(self, service, sample_subscription):
        """Test successful subscription renewal."""
        # Setup mocks
        sample_subscription.status = "active"
        service.subscription_repo.get_by_id.return_value = sample_subscription
        service.subscription_repo.update.return_value = sample_subscription

        # Execute
        result = await service.process_subscription_renewal(sample_subscription.id)

        # Verify
        assert result is True
        service.subscription_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_subscription_renewal_not_found(self, service):
        """Test renewal of non-existent subscription."""
        # Setup mocks
        subscription_id = uuid4()
        service.subscription_repo.get_by_id.return_value = None

        # Execute
        result = await service.process_subscription_renewal(subscription_id)

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_process_subscription_renewal_inactive(self, service, sample_subscription):
        """Test renewal of inactive subscription."""
        # Setup mocks
        sample_subscription.status = "cancelled"
        service.subscription_repo.get_by_id.return_value = sample_subscription

        # Execute
        result = await service.process_subscription_renewal(sample_subscription.id)

        # Verify
        assert result is False 