from typing import Optional
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Payment Service"
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
    SUBSCRIPTION_SERVICE_URL: str = "http://localhost:8001"
    
    # Payment Gateway Settings
    PAYMENT_GATEWAY_SUCCESS_CARD: str = "4242424242424242"
    PAYMENT_GATEWAY_BASE_URL: str = "https://mock-gateway.example.com"
    PAYMENT_GATEWAY_API_KEY: str = "mock_gateway_key_change_in_production"
    
    # Gateway Response Simulation
    GATEWAY_MIN_DELAY_MS: int = 500    # Minimum processing delay
    GATEWAY_MAX_DELAY_MS: int = 3000   # Maximum processing delay
    GATEWAY_SUCCESS_RATE: float = 0.85  # 85% success rate for non-success cards
    
    # Queue Settings
    QUEUE_BATCH_SIZE: int = 100
    QUEUE_TIMEOUT: int = 10
    
    # Retry Settings
    MAX_RETRY_ATTEMPTS: dict = {
        'payment_processing': 3,
        'gateway_webhook_processing': 5,
        'subscription_notification': 3,
        'transaction_update': 2,
        'webhook_delivery': 5
    }
    
    RETRY_DELAYS: dict = {
        'payment_processing': 300,         # 5 minutes
        'gateway_webhook_processing': 120, # 2 minutes
        'subscription_notification': 180,  # 3 minutes
        'transaction_update': 60,          # 1 minute
        'webhook_delivery': 300           # 5 minutes
    }
    
    # Webhook Settings
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_RETRY_MULTIPLIER: float = 2.0
    WEBHOOK_MAX_RETRY_DELAY: int = 3600  # 1 hour
    
    # Security
    SECRET_KEY: str = "your-payment-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # JWT Settings (must match subscription service)
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Webhook Security (must match subscription service)
    WEBHOOK_SIGNING_SECRET: str = "webhook-signing-secret-change-in-production"
    WEBHOOK_TOLERANCE_SECONDS: int = 300  # 5 minutes tolerance for timestamp verification
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings() 