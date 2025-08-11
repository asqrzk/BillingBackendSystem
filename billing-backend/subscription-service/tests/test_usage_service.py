"""
Unit tests for UsageService business logic.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.usage_service import UsageService
from app.schemas.usage import UsageCheckResponse, UsageResponse, UsageStatsResponse


class TestUsageService:
    """Test cases for UsageService."""

    @pytest_asyncio.fixture
    async def service(self, mock_session, mock_redis, mock_subscription_repo, mock_usage_repo):
        """Create usage service with mocked dependencies."""
        service = UsageService(mock_session)
        service.redis = mock_redis
        service.subscription_repo = mock_subscription_repo
        service.usage_repo = mock_usage_repo
        return service

    @pytest.mark.asyncio
    async def test_use_feature_success(self, service, sample_subscription):
        """Test successful feature usage."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        
        # Mock Redis atomic script returns current usage after increment
        service.redis.client.eval.return_value = 1
        
        # Execute
        result = await service.use_feature(user_id=1, feature_name="api_calls", delta=1)

        # Verify
        assert isinstance(result, UsageCheckResponse)
        assert result.allowed is True
        assert result.current_usage == 1
        assert result.limit == 1000  # From sample_plan features
        service.subscription_repo.get_active_subscription_by_user.assert_called_once_with(1)
        service.redis.client.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_use_feature_no_active_subscription(self, service):
        """Test feature usage with no active subscription."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="No active subscription found for user 1"):
            await service.use_feature(user_id=1, feature_name="api_calls")

    @pytest.mark.asyncio
    async def test_use_feature_feature_not_available(self, service, sample_subscription):
        """Test using feature not available in plan."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription

        # Execute and verify
        with pytest.raises(ValueError, match="Feature 'premium_feature' is not available"):
            await service.use_feature(user_id=1, feature_name="premium_feature")

    @pytest.mark.asyncio
    async def test_use_feature_limit_exceeded(self, service, sample_subscription):
        """Test feature usage when limit is exceeded."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        
        # Mock Redis atomic script returns -1 indicating limit exceeded
        service.redis.client.eval.return_value = -1
        
        # Execute
        result = await service.use_feature(user_id=1, feature_name="api_calls", delta=1)

        # Verify
        assert result.allowed is False
        assert result.current_usage == 1000  # Should be at limit
        assert result.limit == 1000

    @pytest.mark.asyncio
    async def test_use_feature_multiple_delta(self, service, sample_subscription):
        """Test feature usage with delta > 1."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        service.redis.client.eval.return_value = 5

        # Execute
        result = await service.use_feature(user_id=1, feature_name="api_calls", delta=5)

        # Verify
        assert result.allowed is True
        assert result.current_usage == 5
        # Verify Redis script was called with correct delta
        eval_args = service.redis.client.eval.call_args[0]
        assert eval_args[3] == "5"  # delta parameter

    @pytest.mark.asyncio
    async def test_get_user_usage_success(self, service):
        """Test getting user usage successfully."""
        # Setup mocks
        mock_usage_data = [
            {
                "feature_name": "api_calls",
                "current_usage": 500,
                "limit": 1000,
                "reset_date": datetime.utcnow()
            },
            {
                "feature_name": "storage_gb",
                "current_usage": 5,
                "limit": 10,
                "reset_date": datetime.utcnow()
            }
        ]
        service.usage_repo.get_user_usage.return_value = mock_usage_data

        # Execute
        result = await service.get_user_usage(user_id=1)

        # Verify
        assert len(result) == 2
        assert all(isinstance(usage, UsageResponse) for usage in result)
        service.usage_repo.get_user_usage.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_user_feature_usage_success(self, service):
        """Test getting specific feature usage."""
        # Setup mocks
        mock_usage = {
            "feature_name": "api_calls",
            "current_usage": 500,
            "limit": 1000,
            "reset_date": datetime.utcnow()
        }
        service.usage_repo.get_user_feature_usage.return_value = mock_usage

        # Execute
        result = await service.get_user_feature_usage(user_id=1, feature_name="api_calls")

        # Verify
        assert isinstance(result, UsageResponse)
        assert result.feature_name == "api_calls"
        assert result.current_usage == 500
        service.usage_repo.get_user_feature_usage.assert_called_once_with(1, "api_calls")

    @pytest.mark.asyncio
    async def test_get_user_feature_usage_not_found(self, service):
        """Test getting feature usage when not found."""
        # Setup mocks
        service.usage_repo.get_user_feature_usage.return_value = None

        # Execute
        result = await service.get_user_feature_usage(user_id=1, feature_name="api_calls")

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_reset_user_usage_specific_feature(self, service):
        """Test resetting usage for specific feature."""
        # Setup mocks
        service.usage_repo.reset_usage.return_value = 1
        service.redis.client.delete = AsyncMock(return_value=1)

        # Execute
        result = await service.reset_user_usage(user_id=1, feature_name="api_calls")

        # Verify
        assert result == 1
        service.usage_repo.reset_usage.assert_called_once_with(1, "api_calls")
        service.redis.client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_user_usage_all_features(self, service):
        """Test resetting usage for all features."""
        # Setup mocks
        service.usage_repo.reset_usage.return_value = 3
        service.redis.client.delete = AsyncMock(return_value=3)

        # Execute
        result = await service.reset_user_usage(user_id=1)

        # Verify
        assert result == 3
        service.usage_repo.reset_usage.assert_called_once_with(1, None)

    @pytest.mark.asyncio
    async def test_get_usage_stats_success(self, service, sample_subscription):
        """Test getting usage statistics."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        
        mock_usage_data = [
            {
                "feature_name": "api_calls",
                "current_usage": 500,
                "limit": 1000,
                "reset_date": datetime.utcnow()
            },
            {
                "feature_name": "storage_gb",
                "current_usage": 8,
                "limit": 10,
                "reset_date": datetime.utcnow()
            }
        ]
        service.usage_repo.get_user_usage.return_value = mock_usage_data

        # Execute
        result = await service.get_usage_stats(user_id=1)

        # Verify
        assert isinstance(result, UsageStatsResponse)
        assert result.total_features == 2
        assert len(result.features) == 2
        assert result.subscription_status == "active"
        assert result.subscription_plan == "Basic Plan"

    @pytest.mark.asyncio
    async def test_get_usage_stats_no_subscription(self, service):
        """Test getting usage stats with no active subscription."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match="No active subscription found"):
            await service.get_usage_stats(user_id=1)

    @pytest.mark.asyncio
    async def test_sync_usage_schedule_success(self, service):
        """Test scheduled usage synchronization."""
        # Setup mocks
        mock_redis_keys = [
            "usage:1:api_calls",
            "usage:1:storage_gb",
            "usage:2:api_calls"
        ]
        service.redis.client.keys = AsyncMock(return_value=mock_redis_keys)
        service.redis.client.get = AsyncMock(return_value="100")
        service._sync_usage_to_db = AsyncMock()

        # Execute
        await service.sync_usage_schedule()

        # Verify
        service.redis.client.keys.assert_called_once_with("usage:*")
        assert service._sync_usage_to_db.call_count == 3

    @pytest.mark.asyncio
    async def test_reset_expired_usage_schedule_success(self, service):
        """Test scheduled reset of expired usage."""
        # Setup mocks
        expired_subscriptions = [
            {"user_id": 1, "subscription_id": uuid4()},
            {"user_id": 2, "subscription_id": uuid4()}
        ]
        service.subscription_repo.get_expired_usage_periods = AsyncMock(
            return_value=expired_subscriptions
        )
        service.reset_user_usage = AsyncMock(return_value=2)

        # Execute
        await service.reset_expired_usage_schedule()

        # Verify
        service.subscription_repo.get_expired_usage_periods.assert_called_once()
        assert service.reset_user_usage.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_usage_to_db_success(self, service):
        """Test syncing usage data to database."""
        # Execute
        await service._sync_usage_to_db(user_id=1, feature_name="api_calls", current_usage=100)

        # Verify
        service.usage_repo.create_or_update.assert_called_once_with(
            user_id=1,
            feature_name="api_calls",
            current_usage=100
        )

    @pytest.mark.asyncio
    async def test_sync_usage_to_db_exception_handling(self, service):
        """Test exception handling in DB sync."""
        # Setup mocks to raise exception
        service.usage_repo.create_or_update.side_effect = Exception("DB Error")

        # Execute - should not raise exception
        await service._sync_usage_to_db(user_id=1, feature_name="api_calls", current_usage=100)

        # Verify method was called (exception was caught and logged)
        service.usage_repo.create_or_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_use_feature_redis_script_parameters(self, service, sample_subscription):
        """Test that Redis atomic script is called with correct parameters."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        service.redis.client.eval.return_value = 1

        # Execute
        await service.use_feature(user_id=1, feature_name="api_calls", delta=1)

        # Verify Redis script call parameters
        eval_args = service.redis.client.eval.call_args[0]
        eval_kwargs = service.redis.client.eval.call_args[1] if len(service.redis.client.eval.call_args) > 1 else {}
        
        assert eval_args[0] == "mock_script"  # script
        assert eval_args[1] == 2  # number of keys
        assert eval_args[2] == "usage:1:api_calls"  # usage key
        assert eval_args[3] == "limit:1:api_calls"  # limit key
        assert eval_args[4] == "1"  # delta
        assert eval_args[5] == "1000"  # limit
        # Timestamp should be recent
        timestamp = int(eval_args[6])
        current_timestamp = int(datetime.utcnow().timestamp())
        assert abs(timestamp - current_timestamp) < 10  # Within 10 seconds

    @pytest.mark.asyncio
    async def test_get_usage_stats_percentage_calculation(self, service, sample_subscription):
        """Test usage percentage calculation in stats."""
        # Setup mocks
        service.subscription_repo.get_active_subscription_by_user.return_value = sample_subscription
        
        mock_usage_data = [
            {
                "feature_name": "api_calls",
                "current_usage": 750,  # 75% usage
                "limit": 1000,
                "reset_date": datetime.utcnow()
            },
            {
                "feature_name": "storage_gb",
                "current_usage": 2,  # 20% usage
                "limit": 10,
                "reset_date": datetime.utcnow()
            }
        ]
        service.usage_repo.get_user_usage.return_value = mock_usage_data

        # Execute
        result = await service.get_usage_stats(user_id=1)

        # Verify percentage calculations
        api_calls_feature = next(f for f in result.features if f.feature_name == "api_calls")
        storage_feature = next(f for f in result.features if f.feature_name == "storage_gb")
        
        assert api_calls_feature.usage_percentage == 75.0
        assert storage_feature.usage_percentage == 20.0 