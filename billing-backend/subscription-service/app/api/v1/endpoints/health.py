from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio

from app.core.database import get_async_session
from app.core.redis_client import redis_client
from app.core.config import settings

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "subscription-service",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@router.get("/detailed")
async def detailed_health_check(
    session: AsyncSession = Depends(get_async_session)
):
    """Detailed health check including dependencies."""
    health_status = {
        "status": "healthy",
        "service": "subscription-service", 
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }
    
    # Database check
    try:
        await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {"status": "healthy", "message": "Database connection OK"}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Redis check
    try:
        if not redis_client.client:
            await redis_client.connect()
        await redis_client.client.ping()
        health_status["checks"]["redis"] = {"status": "healthy", "message": "Redis connection OK"}
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Queue check
    try:
        if not redis_client.client:
            await redis_client.connect()
        
        queue_stats = {}
        subscription_queues = [
            "queue:payment_initiation",
            "queue:trial_payment", 
            "queue:plan_change",
            "queue:usage_sync",
            "queue:webhook_processing",
            "queue:subscription_renewal",
            "queue:payment_initiation:delayed",
            "queue:trial_payment:delayed",
            "queue:plan_change:delayed"
        ]
        
        for queue_name in subscription_queues:
            if ":delayed" in queue_name:
                # For delayed queues (sorted sets)
                active_depth = await redis_client.client.zcard(queue_name)
                queue_stats[queue_name] = {
                    "active_depth": active_depth,
                    "delayed_depth": 0,  # This IS the delayed queue
                    "failed_depth": 0,
                    "total_depth": active_depth
                }
            else:
                # For regular queues (lists)
                active_depth = await redis_client.get_queue_length(queue_name)
                failed_depth = await redis_client.get_queue_length(f"{queue_name}:failed")
                delayed_depth = await redis_client.client.zcard(f"{queue_name}:delayed")
                
                queue_stats[queue_name] = {
                    "active_depth": active_depth,
                    "delayed_depth": delayed_depth,
                    "failed_depth": failed_depth,
                    "total_depth": active_depth + delayed_depth + failed_depth
                }
        
        health_status["checks"]["queues"] = {
            "status": "healthy",
            "stats": queue_stats
        }
        
    except Exception as e:
        health_status["checks"]["queues"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@router.get("/queues")
async def get_queue_status():
    """Get subscription service queue status."""
    try:
        if not redis_client.client:
            await redis_client.connect()
        
        queue_stats = {}
        subscription_queues = [
            "queue:payment_initiation",
            "queue:trial_payment", 
            "queue:plan_change",
            "queue:usage_sync",
            "queue:webhook_processing",
            "queue:subscription_renewal",
            "queue:payment_initiation:delayed",
            "queue:trial_payment:delayed",
            "queue:plan_change:delayed"
        ]
        
        for queue_name in subscription_queues:
            if ":delayed" in queue_name:
                # For delayed queues (sorted sets)
                count = await redis_client.client.zcard(queue_name)
            else:
                # For regular queues (lists)
                count = await redis_client.get_queue_length(queue_name)
            
            queue_stats[queue_name] = {"length": count}
        
        return {
            "status": "healthy",
            "queues": queue_stats,
            "total_messages": sum(q["length"] for q in queue_stats.values())
        }
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Queue status check failed: {str(e)}") 