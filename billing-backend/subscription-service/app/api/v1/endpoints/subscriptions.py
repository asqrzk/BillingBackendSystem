from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, verify_service_token
from app.schemas.subscription import (
    SubscriptionCreateRequest, 
    TrialSubscriptionRequest,
    PlanChangeRequest,
    SubscriptionResponse,
    SubscriptionListResponse
)
from app.schemas.common import SuccessResponse, ErrorResponse
from app.services.subscription_service import SubscriptionService
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a new subscription for the authenticated user.
    
    - **plan_id**: Plan ID to subscribe to
    """
    try:
        service = SubscriptionService(session)
        
        # Create internal request with user_id from token
        internal_request = type('obj', (object,), {
            'user_id': current_user.id,
            'plan_id': request.plan_id
        })
        
        subscription = await service.create_subscription(internal_request)
        return SubscriptionResponse.from_orm(subscription, include_plan=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.post("/trial", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_trial_subscription(
    request: TrialSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a trial subscription for the authenticated user.
    
    This creates a trial subscription with:
    - Immediate activation (no payment required)
    - Limited trial period (configured in plan)
    - Automatic trial payment charge (1 AED with immediate refund)
    """
    try:
        service = SubscriptionService(session)
        
        # Create internal request with user_id from token
        internal_request = type('obj', (object,), {
            'user_id': current_user.id,
            'trial_plan_id': request.trial_plan_id
        })
        
        subscription = await service.create_trial_subscription(internal_request)
        
        return SubscriptionResponse.from_orm(subscription, include_plan=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create trial subscription")


@router.get("/active", response_model=Optional[SubscriptionResponse])
async def get_active_subscription(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get active subscription for the authenticated user.
    """
    try:
        service = SubscriptionService(session)
        subscription = await service.get_active_subscription(current_user.id)
        
        if not subscription:
            return None
        
        return SubscriptionResponse.from_orm(subscription, include_plan=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve active subscription")


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get subscription details by ID.
    Users can only access their own subscriptions.
    """
    try:
        service = SubscriptionService(session)
        subscription = await service.get_subscription(subscription_id)
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Check if subscription belongs to current user
        if subscription.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return SubscriptionResponse.from_orm(subscription, include_user=True, include_plan=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve subscription")


@router.get("/", response_model=List[SubscriptionResponse])
async def get_user_subscriptions(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get all subscriptions for the authenticated user.
    """
    try:
        service = SubscriptionService(session)
        subscriptions = await service.get_user_subscriptions(current_user.id)
        
        return [
            SubscriptionResponse.from_orm(subscription, include_plan=True) 
            for subscription in subscriptions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve subscriptions")


@router.post("/{subscription_id}/change-plan", response_model=SuccessResponse)
async def change_subscription_plan(
    subscription_id: UUID,
    request: PlanChangeRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Change plan for a subscription.
    Users can only modify their own subscriptions.
    """
    try:
        service = SubscriptionService(session)
        
        # First verify subscription belongs to current user
        subscription = await service.get_subscription(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        if subscription.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        await service.change_plan(subscription_id, request.new_plan_id)
        
        return SuccessResponse(
            message="Plan change request submitted",
            data={"subscription_id": str(subscription_id), "new_plan_id": str(request.new_plan_id)}
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to change subscription plan")


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Cancel a subscription.
    Users can only cancel their own subscriptions.
    """
    try:
        service = SubscriptionService(session)
        
        # First verify subscription belongs to current user
        subscription = await service.get_subscription(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        if subscription.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        cancelled_subscription = await service.cancel_subscription(subscription_id)
        
        return SubscriptionResponse.from_orm(cancelled_subscription, include_plan=True)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


# Internal endpoints for service-to-service communication (workers/consumers)
@router.get("/internal/user/{user_id}", response_model=List[SubscriptionResponse])
async def get_user_subscriptions_internal(
    user_id: int,
    service_token: dict = Depends(verify_service_token),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Internal endpoint for getting user subscriptions.
    Only accessible with service token.
    """
    try:
        service = SubscriptionService(session)
        subscriptions = await service.get_user_subscriptions(user_id)
        
        return [
            SubscriptionResponse.from_orm(subscription, include_plan=True) 
            for subscription in subscriptions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve subscriptions")


@router.get("/internal/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription_internal(
    subscription_id: UUID,
    service_token: dict = Depends(verify_service_token),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Internal endpoint for getting subscription details.
    Only accessible with service token.
    """
    try:
        service = SubscriptionService(session)
        subscription = await service.get_subscription(subscription_id)
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return SubscriptionResponse.from_orm(subscription, include_user=True, include_plan=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve subscription") 