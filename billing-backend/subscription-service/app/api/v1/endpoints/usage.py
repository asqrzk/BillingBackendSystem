from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, verify_service_token
from app.schemas.usage import UsageRequest, UsageCheckResponse, UsageResponse, UsageStatsResponse
from app.schemas.common import SuccessResponse
from app.services.usage_service import UsageService
from app.models.user import User

router = APIRouter()


@router.post("/use", response_model=UsageCheckResponse)
async def use_feature(
    request: UsageRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Use a feature and track usage atomically.
    
    - **feature_name**: Name of the feature to use
    - **delta**: Usage increment (default: 1)
    
    Returns current usage status and whether limit was exceeded.
    """
    try:
        service = UsageService(session)
        result = await service.use_feature(
            current_user.id, 
            request.feature_name, 
            request.delta
        )
        
        if not result.success:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Usage limit exceeded")
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process feature usage")


@router.get("/", response_model=List[UsageResponse])
async def get_user_usage(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get all feature usage for the authenticated user.
    """
    try:
        service = UsageService(session)
        usage_records = await service.get_user_usage(current_user.id)
        
        return usage_records
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve usage data")


@router.get("/feature/{feature_name}", response_model=UsageResponse)
async def get_feature_usage(
    feature_name: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get specific feature usage for the authenticated user.
    
    - **feature_name**: Name of the feature
    """
    try:
        service = UsageService(session)
        usage = await service.get_user_feature_usage(current_user.id, feature_name)
        
        if not usage:
            # Return zero usage if no record exists
            from app.schemas.usage import UsageResponse
            from datetime import datetime, timedelta
            return UsageResponse(
                user_id=current_user.id,
                feature_name=feature_name,
                usage_count=0,
                limit=0,  # Will be determined by plan
                remaining=0,
                reset_at=datetime.utcnow() + timedelta(days=30),
                last_updated=datetime.utcnow()
            )
        
        return usage
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve feature usage")


@router.post("/reset", response_model=SuccessResponse)
async def reset_user_usage(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Reset all usage for the authenticated user.
    This is typically used for testing or administrative purposes.
    """
    try:
        service = UsageService(session)
        count = await service.reset_user_usage(current_user.id)
        
        return SuccessResponse(
            message=f"Usage reset for {count} features",
            data={"user_id": current_user.id, "features_reset": count}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to reset usage")


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get usage statistics for the authenticated user.
    """
    try:
        service = UsageService(session)
        stats = await service.get_usage_stats(current_user.id)
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve usage statistics")


# Internal endpoints for service-to-service communication (workers/consumers)
@router.get("/internal/user/{user_id}", response_model=List[UsageResponse])
async def get_user_usage_internal(
    user_id: int,
    service_token: dict = Depends(verify_service_token),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Internal endpoint for getting user usage.
    Only accessible with service token.
    """
    try:
        service = UsageService(session)
        usage_records = await service.get_user_usage(user_id)
        
        return usage_records
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve usage data")


@router.get("/internal/user/{user_id}/feature/{feature_name}", response_model=UsageResponse)
async def get_user_feature_usage_internal(
    user_id: int,
    feature_name: str,
    service_token: dict = Depends(verify_service_token),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Internal endpoint for getting specific feature usage.
    Only accessible with service token.
    """
    try:
        service = UsageService(session)
        usage = await service.get_user_feature_usage(user_id, feature_name)
        
        if not usage:
            # Return zero usage if no record exists
            from app.schemas.usage import UsageResponse
            from datetime import datetime, timedelta
            return UsageResponse(
                user_id=user_id,
                feature_name=feature_name,
                usage_count=0,
                limit=0,
                remaining=0,
                reset_at=datetime.utcnow() + timedelta(days=30),
                last_updated=datetime.utcnow()
            )
        
        return usage
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve feature usage")


@router.post("/internal/user/{user_id}/reset", response_model=SuccessResponse)
async def reset_user_usage_internal(
    user_id: int,
    service_token: dict = Depends(verify_service_token),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Internal endpoint for resetting user usage.
    Only accessible with service token.
    """
    try:
        service = UsageService(session)
        count = await service.reset_user_usage(user_id)
        
        return SuccessResponse(
            message=f"Usage reset for {count} features",
            data={"user_id": user_id, "features_reset": count}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to reset usage") 