# Configuration Management System

This directory contains the robust configuration management system for the Billing Backend, following 12-Factor App principles and industry best practices.

## Overview

The configuration system provides:
- ✅ **Environment-specific configurations** (dev, staging, production)
- ✅ **Centralized configuration management**
- ✅ **Configuration validation and type safety**
- ✅ **Secret management integration**
- ✅ **Docker-compose per environment**
- ✅ **Zero configuration duplication**

## Directory Structure

```
config/
├── environments/           # Environment-specific configuration files
│   ├── base.env           # Base configuration shared across all environments
│   ├── development.env    # Development environment settings
│   ├── staging.env        # Staging environment settings
│   └── production.env     # Production environment settings
├── config_loader.py       # Centralized configuration loader with validation
└── README.md              # This documentation
```

## Environment Files

### Base Configuration (`base.env`)
Contains settings shared across all environments:
- Application metadata
- Default pool sizes and timeouts
- JWT algorithm and token expiration
- Webhook settings
- Development/testing gateway settings

### Environment-Specific Files
Each environment file contains:
- Environment-specific database/Redis URLs
- Service discovery URLs
- Security secrets (via environment variables)
- Environment-specific feature flags
- Performance tuning parameters

## Configuration Loading

### In Your Services

Replace your existing config classes with the new centralized loader:

```python
# OLD - Don't use this anymore
from app.core.config import settings

# NEW - Use the centralized config loader
from config.config_loader import get_config

# Load configuration for your service
config = get_config(service_name="subscription")  # or "payment"

# Access configuration
database_url = config.DATABASE_URL
jwt_secret = config.JWT_SECRET_KEY
```

### Environment Detection

```python
from config.config_loader import is_production, is_development, is_staging

if is_production():
    # Production-specific logic
    pass
elif is_development():
    # Development-specific logic
    pass
```

## Environment Management

### Using the Environment Manager Script

The `scripts/env-manager.sh` script provides easy environment management:

```bash
# Development
./scripts/env-manager.sh -e development start
./scripts/env-manager.sh -e development logs

# Staging
./scripts/env-manager.sh -e staging validate
./scripts/env-manager.sh -e staging deploy

# Production
./scripts/env-manager.sh -e production secrets  # Generate secure secrets
./scripts/env-manager.sh -e production validate
./scripts/env-manager.sh -e production deploy
```

### Docker Compose Files

- `docker-compose.development.yml` - Local development with volume mounts and reload
- `docker-compose.production.yml` - Production deployment with proper resource limits

## Secret Management

### Development
Development secrets are included in the repository for convenience but are clearly marked as development-only.

### Staging/Production
Production secrets use environment variable substitution:

```bash
# In production.env
JWT_SECRET_KEY=${JWT_SECRET_KEY_PROD}
DATABASE_URL=postgresql://user:${DB_PASSWORD}@host:5432/db
```

### Generating Secrets
```bash
# Generate secure secrets for production
./scripts/env-manager.sh secrets
```

Store these secrets in your secret management system (AWS Secrets Manager, HashiCorp Vault, etc.).

## Configuration Validation

The system includes comprehensive validation:

### Automatic Validation
- **Type checking** via Pydantic
- **Length validation** for secrets (minimum 32 characters)
- **Environment-specific validation** (e.g., no localhost URLs in production)
- **Secret pattern detection** (prevents dev secrets in production)

### Manual Validation
```bash
# Validate configuration for an environment
./scripts/env-manager.sh -e production validate
```

## Migration from Old System

### Step 1: Update Service Config Files

Replace your service config files:

```python
# subscription-service/app/core/config.py
from config.config_loader import get_config

# Load configuration
settings = get_config(service_name="subscription")
```

### Step 2: Update Imports

Find and replace across your services:

```python
# OLD
from app.core.config import settings

# NEW  
from config.config_loader import get_config
settings = get_config()
```

### Step 3: Use New Docker Compose

```bash
# Instead of
docker-compose up

# Use
./scripts/env-manager.sh -e development start
```

## Best Practices

### 1. Environment Variables
- Use `${VAR_NAME}` substitution for secrets in staging/production
- Never commit production secrets to repository
- Use development-specific defaults only in development.env

### 2. Service URLs
- Use service discovery names in Docker environments
- Use localhost URLs only for local development
- Configure environment-specific service URLs

### 3. Security
- Generate strong secrets (minimum 32 characters)
- Rotate secrets regularly
- Use secret management systems for production
- Validate configuration before deployment

### 4. Database and Redis
- Use separate instances per environment
- Configure connection pooling per environment
- Use environment-specific database names

## Environment Deployment Guide

### Development
```bash
# Start local development
./scripts/env-manager.sh -e development start

# View logs
./scripts/env-manager.sh -e development logs

# Stop services
./scripts/env-manager.sh -e development stop
```

### Staging
```bash
# Validate configuration
./scripts/env-manager.sh -e staging validate

# Deploy to staging
./scripts/env-manager.sh -e staging deploy

# Monitor logs
./scripts/env-manager.sh -e staging logs
```

### Production
```bash
# Generate production secrets
./scripts/env-manager.sh secrets

# Store secrets in your secret management system
# Set environment variables for secret substitution

# Validate production configuration
./scripts/env-manager.sh -e production validate

# Deploy to production
./scripts/env-manager.sh -e production deploy
```

## Troubleshooting

### Configuration Validation Errors
1. Check that all environment files exist
2. Verify secret lengths (minimum 32 characters)
3. Ensure no development patterns in production secrets
4. Validate database/Redis URLs for environment

### Docker Deployment Issues
1. Ensure external networks exist for production
2. Check that required environment variables are set
3. Verify image tags for production deployment
4. Check resource limits and health checks

### Secret Management
1. Generate secrets using the provided script
2. Store secrets securely in your secret management system
3. Set environment variables for substitution
4. Never commit production secrets to repository

## Support

For questions about the configuration system:
1. Check this documentation
2. Validate your configuration using the validation script
3. Review the config_loader.py for detailed validation rules
4. Check environment-specific files for examples 