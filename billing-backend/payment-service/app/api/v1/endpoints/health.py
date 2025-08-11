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
        "service": "payment-service",
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
        "service": "payment-service", 
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }
    
    # Database check
    try:
        await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {"status": "healthy", "message": "Database connection OK"}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "message": f"Database error: {str(e)}"}
        health_status["status"] = "unhealthy"
    
    # Redis check
    try:
        if not redis_client.client:
            await redis_client.connect()
        await redis_client.client.ping()
        health_status["checks"]["redis"] = {"status": "healthy", "message": "Redis connection OK"}
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "unhealthy", "message": f"Redis error: {str(e)}"}
        health_status["status"] = "unhealthy"
    
    # Mock Gateway check
    try:
        # Simple validation that gateway config is available
        gateway_status = {
            "success_card_configured": bool(settings.PAYMENT_GATEWAY_SUCCESS_CARD),
            "delay_range": f"{settings.GATEWAY_MIN_DELAY_MS}-{settings.GATEWAY_MAX_DELAY_MS}ms",
            "success_rate": f"{settings.GATEWAY_SUCCESS_RATE * 100}%"
        }
        health_status["checks"]["mock_gateway"] = {"status": "healthy", "config": gateway_status}
    except Exception as e:
        health_status["checks"]["mock_gateway"] = {"status": "unhealthy", "message": f"Gateway config error: {str(e)}"}
        health_status["status"] = "unhealthy"
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@router.get("/queues")
async def get_queue_status():
    """Get payment service queue status."""
    try:
        if not redis_client.client:
            await redis_client.connect()
        
        queue_stats = {}
        payment_queues = [
            "queue:payment_processing",
            "queue:gateway_webhook_processing", 
            "queue:webhook_delivery",
            "queue:payment_processing:delayed",
            "queue:gateway_webhook_processing:delayed",
            "queue:webhook_delivery:delayed"
        ]
        
        for queue_name in payment_queues:
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