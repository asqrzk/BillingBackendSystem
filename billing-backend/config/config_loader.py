"""
Centralized Configuration Loader

This module provides a robust configuration management system that:
1. Loads environment-specific configurations
2. Validates required settings
3. Handles secret management
4. Provides environment-aware defaults
"""

import os
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import logging

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


class BaseConfig(BaseSettings):
    """Base configuration class with common validation and loading logic"""
    
    # Application
    APP_NAME: str = Field(default="Billing Backend")
    VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    
    # Database
    DATABASE_URL: str = Field(..., description="Database connection URL")
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    
    # Redis
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=50)
    
    # External Services
    SUBSCRIPTION_SERVICE_URL: str = Field(..., description="Subscription service URL")
    PAYMENT_SERVICE_URL: str = Field(..., description="Payment service URL")
    
    # Security - These should be overridden per environment
    JWT_SECRET_KEY: str = Field(..., min_length=32, description="JWT signing secret")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    
    WEBHOOK_SIGNING_SECRET: str = Field(..., min_length=32, description="Webhook signing secret")
    WEBHOOK_TOLERANCE_SECONDS: int = Field(default=300)
    
    SECRET_KEY: str = Field(..., min_length=32, description="General application secret")
    
    # Payment Gateway
    PAYMENT_GATEWAY_BASE_URL: str = Field(default="https://mock-gateway.example.com")
    PAYMENT_GATEWAY_API_KEY: str = Field(..., description="Payment gateway API key")
    PAYMENT_GATEWAY_SUCCESS_CARD: str = Field(default="4242424242424242")
    
    # Optional development settings
    ENABLE_CORS: bool = Field(default=False)
    ENABLE_RELOAD: bool = Field(default=False)
    
    @validator('ENVIRONMENT')
    def validate_environment(cls, v):
        allowed_envs = ['development', 'staging', 'production', 'testing']
        if v not in allowed_envs:
            raise ValueError(f'Environment must be one of: {allowed_envs}')
        return v
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'Log level must be one of: {allowed_levels}')
        return v.upper()
    
    @validator('JWT_SECRET_KEY', 'WEBHOOK_SIGNING_SECRET', 'SECRET_KEY')
    def validate_secrets(cls, v, field):
        if len(v) < 32:
            raise ValueError(f'{field.name} must be at least 32 characters long')
        if v.startswith('dev-') and os.getenv('ENVIRONMENT') == 'production':
            raise ValueError(f'{field.name} cannot use development defaults in production')
        return v

    class Config:
        case_sensitive = True
        validate_assignment = True


class ConfigLoader:
    """
    Configuration loader that handles environment-specific settings
    """
    
    def __init__(self, service_name: Optional[str] = None):
        self.service_name = service_name
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.config_dir = Path(__file__).parent / 'environments'
        
    def load_config(self) -> BaseConfig:
        """Load configuration for the current environment"""
        try:
            # Load environment files in order: base -> environment-specific
            env_files = self._get_env_files()
            
            # Validate environment files exist
            missing_files = [f for f in env_files if not f.exists()]
            if missing_files:
                raise ConfigValidationError(
                    f"Missing configuration files: {[str(f) for f in missing_files]}"
                )
            
            # Create settings with proper env_file loading
            settings = BaseConfig(_env_file=env_files)
            
            # Perform environment-specific validation
            self._validate_environment_config(settings)
            
            logger.info(f"Configuration loaded successfully for environment: {self.environment}")
            if self.service_name:
                logger.info(f"Service: {self.service_name}")
            
            return settings
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigValidationError(f"Configuration loading failed: {e}")
    
    def _get_env_files(self) -> List[Path]:
        """Get list of environment files to load in order"""
        env_files = [
            self.config_dir / 'base.env',
            self.config_dir / f'{self.environment}.env'
        ]
        
        # Add service-specific config if specified
        if self.service_name:
            service_file = self.config_dir / f'{self.service_name}.{self.environment}.env'
            if service_file.exists():
                env_files.append(service_file)
        
        return env_files
    
    def _validate_environment_config(self, settings: BaseConfig) -> None:
        """Perform environment-specific validation"""
        
        if settings.ENVIRONMENT == 'production':
            self._validate_production_config(settings)
        elif settings.ENVIRONMENT == 'staging':
            self._validate_staging_config(settings)
        elif settings.ENVIRONMENT == 'development':
            self._validate_development_config(settings)
    
    def _validate_production_config(self, settings: BaseConfig) -> None:
        """Production-specific validation"""
        # Ensure DEBUG is disabled
        if settings.DEBUG:
            raise ConfigValidationError("DEBUG must be False in production")
        
        # Ensure secrets are not using development defaults
        dev_patterns = ['dev-', 'development', 'test-', 'mock_']
        for secret_field in ['JWT_SECRET_KEY', 'WEBHOOK_SIGNING_SECRET', 'SECRET_KEY']:
            secret_value = getattr(settings, secret_field)
            if any(pattern in secret_value.lower() for pattern in dev_patterns):
                raise ConfigValidationError(
                    f"{secret_field} uses development pattern in production"
                )
        
        # Ensure production database/redis URLs
        if 'localhost' in settings.DATABASE_URL:
            raise ConfigValidationError("Production cannot use localhost database")
        
        if 'localhost' in settings.REDIS_URL:
            raise ConfigValidationError("Production cannot use localhost Redis")
    
    def _validate_staging_config(self, settings: BaseConfig) -> None:
        """Staging-specific validation"""
        if settings.DEBUG:
            logger.warning("DEBUG is enabled in staging - consider disabling for production-like testing")
    
    def _validate_development_config(self, settings: BaseConfig) -> None:
        """Development-specific validation"""
        # Just log some useful info for development
        logger.info("Development environment loaded")
        if not settings.DEBUG:
            logger.info("DEBUG is disabled - set DEBUG=true for development debugging")


# Global config loader instances
def get_config(service_name: Optional[str] = None) -> BaseConfig:
    """
    Get configuration for the current environment
    
    Args:
        service_name: Optional service name for service-specific config
        
    Returns:
        BaseConfig: Loaded and validated configuration
    """
    loader = ConfigLoader(service_name=service_name)
    return loader.load_config()


# Environment detection helpers
def is_production() -> bool:
    """Check if running in production environment"""
    return os.getenv('ENVIRONMENT', 'development') == 'production'


def is_development() -> bool:
    """Check if running in development environment"""
    return os.getenv('ENVIRONMENT', 'development') == 'development'


def is_staging() -> bool:
    """Check if running in staging environment"""
    return os.getenv('ENVIRONMENT', 'development') == 'staging' 