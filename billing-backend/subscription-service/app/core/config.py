from typing import Optional
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Subscription Service"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://billing_user:billing_pass@localhost:5432/billing_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    
    # External Services
    PAYMENT_SERVICE_URL: str = "http://localhost:8002"
    
    # Queue Settings
    QUEUE_BATCH_SIZE: int = 100
    QUEUE_TIMEOUT: int = 10
    
    # Retry Settings
    MAX_RETRY_ATTEMPTS: dict = {
        'payment_initiation': 3,
        'payment_webhook_processing': 5,
        'subscription_renewal': 2,
        'plan_change': 3,
        'usage_sync': 2
    }
    
    RETRY_DELAYS: dict = {
        'payment_initiation': 300,      # 5 minutes
        'payment_webhook_processing': 180,  # 3 minutes
        'subscription_renewal': 43200,  # 12 hours
        'plan_change': 300,            # 5 minutes
        'usage_sync': 60               # 1 minute
    }
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # JWT Settings
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Webhook Security
    WEBHOOK_SIGNING_SECRET: str = "webhook-signing-secret-change-in-production"
    WEBHOOK_TOLERANCE_SECONDS: int = 300  # 5 minutes tolerance for timestamp verification
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings() 