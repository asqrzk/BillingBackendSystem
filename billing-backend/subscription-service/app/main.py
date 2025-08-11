from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
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
        logger.info("Subscription Service startup completed")
    except Exception as e:
        logger.error(f"Subscription Service startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        await redis_client.disconnect()
        logger.info("Subscription Service shutdown completed")
    except Exception as e:
        logger.error(f"Subscription Service shutdown failed: {e}")


# Create FastAPI application with security configuration
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    **Subscription Management Service** with JWT Authentication
    
    ## Authentication
    
    Most endpoints require JWT authentication. To authenticate:
    
    1. **Register** a new account: `POST /v1/auth/register`
    2. **Login** to get a token: `POST /v1/auth/login`
    3. Click the **🔒 Authorize** button and enter: `Bearer <your_token>`
    4. Use authenticated endpoints
    
    ## Features
    
    - 🔐 **JWT Authentication** - Secure user authentication
    - 📦 **Subscription Management** - Create, manage, and cancel subscriptions
    - 📊 **Usage Tracking** - Track feature usage with atomic operations
    - 🔄 **Plan Changes** - Upgrade/downgrade subscription plans
    - 💳 **Payment Integration** - Integration with payment service
    - 📈 **Real-time Monitoring** - Redis queues and health checks
    
    ## Quick Start
    
    1. Register: `POST /v1/auth/register`
    2. Create subscription: `POST /v1/subscriptions/`
    3. Track usage: `POST /v1/usage/use`
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

# Configure security scheme for OpenAPI
app.openapi_components = {
    "securitySchemes": {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token (without 'Bearer ' prefix)"
        }
    }
}

# Set global security requirement
app.openapi_security = [{"BearerAuth": []}]

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
            "register": "/v1/auth/register",
            "login": "/v1/auth/login",
            "required": "Bearer JWT token for most endpoints"
        },
        "features": [
            "JWT Authentication",
            "Subscription Management",
            "Usage Tracking",
            "Plan Changes",
            "Payment Integration"
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
            "description": "JWT Bearer token authentication"
        }
    }
    
    # Add security requirement to protected endpoints
    for path, path_item in openapi_schema["paths"].items():
        # Skip auth endpoints and health checks
        if "/auth/" in path or "/health" in path:
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