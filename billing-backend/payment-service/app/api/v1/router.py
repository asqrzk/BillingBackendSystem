from fastapi import APIRouter

from .endpoints import payments, webhooks, health

api_router = APIRouter()

api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(health.router, prefix="/health", tags=["health"]) 