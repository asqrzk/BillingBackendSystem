from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis_client import redis_client
from app.api.v1.router import api_router


# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    try:
        await redis_client.connect()
        logger.info("Payment Service startup completed")
    except Exception as e:
        logger.error(f"Payment Service startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        await redis_client.disconnect()
        logger.info("Payment Service shutdown completed")
    except Exception as e:
        logger.error(f"Payment Service shutdown failed: {e}")


# Create FastAPI application with security configuration
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    **Payment Processing Service** with JWT Authentication
    
    ## Authentication
    
    This service uses JWT authentication for user endpoints. To authenticate:
    
    1. **Get a token** from the Subscription Service: `POST /v1/auth/login`
    2. Click the **🔒 Authorize** button and enter: `Bearer <your_token>`
    3. Use authenticated endpoints
    
    ## Features
    
    - 🔐 **JWT Authentication** - Secure user authentication
    - 💳 **Mock Payment Gateway** - Simulated payment processing
    - 🔄 **Transaction Management** - Create and track payment transactions
    - 📊 **Transaction History** - View transaction history by user
    - 💰 **Refund Processing** - Initiate refunds for successful payments
    - 🔗 **Service Integration** - Webhook notifications to subscription service
    
    ## Mock Gateway
    
    - **Success Card**: `4242424242424242` (guaranteed success)
    - **Other Cards**: 85% success rate with random delays (500-3000ms)
    - **Trial Payments**: 1 AED charge with immediate refund
    
    ## Quick Start
    
    1. Get JWT token from Subscription Service
    2. Process payment: `POST /v1/payments/process`
    3. View transactions: `GET /v1/payments/transactions`
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    # Configure security for Swagger UI
    swagger_ui_parameters={
        "persistAuthorization": True,
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for production
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )

# Include API router
app.include_router(api_router, prefix="/v1")


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
        "docs_url": "/docs",
        "health_check": "/v1/health",
        "authentication": {
            "source": "Subscription Service /v1/auth/login",
            "required": "Bearer JWT token for user endpoints"
        },
        "mock_gateway": {
            "success_card": settings.PAYMENT_GATEWAY_SUCCESS_CARD,
            "success_rate": f"{settings.GATEWAY_SUCCESS_RATE * 100}%",
            "processing_delay": f"{settings.GATEWAY_MIN_DELAY_MS}-{settings.GATEWAY_MAX_DELAY_MS}ms"
        },
        "features": [
            "JWT Authentication",
            "Mock Payment Gateway",
            "Transaction Management",
            "Refund Processing",
            "Service Integration"
        ]
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "details": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


# Override OpenAPI schema to include security
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token authentication (get from Subscription Service)"
        }
    }
    
    # Add security requirement to user endpoints (exclude internal and health)
    for path, path_item in openapi_schema["paths"].items():
        # Skip internal endpoints, webhooks, and health checks
        if "/internal/" in path or "/webhooks/" in path or "/health" in path:
            continue
        
        for method, operation in path_item.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                operation["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 