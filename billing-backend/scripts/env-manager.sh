#!/bin/bash

# Environment Manager Script
# This script helps manage different environments (dev, staging, production)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
ACTION="help"
SERVICE=""

# Function to display usage
usage() {
    echo -e "${BLUE}Environment Manager for Billing Backend${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS] ACTION"
    echo ""
    echo "Actions:"
    echo "  start       Start services for the specified environment"
    echo "  stop        Stop services"
    echo "  restart     Restart services"
    echo "  logs        Show logs for services"
    echo "  build       Build images for the environment"
    echo "  validate    Validate configuration for environment"
    echo "  secrets     Generate secure secrets for production"
    echo "  deploy      Deploy to the specified environment"
    echo ""
    echo "Options:"
    echo "  -e, --env       Environment (development|staging|production) [default: development]"
    echo "  -s, --service   Specific service to target (optional)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -e development start    # Start development environment"
    echo "  $0 -e production validate  # Validate production config"
    echo "  $0 -e staging deploy       # Deploy to staging"
    echo "  $0 secrets                 # Generate production secrets"
}

# Function to validate environment
validate_environment() {
    if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
        echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'. Must be development, staging, or production.${NC}"
        exit 1
    fi
}

# Function to check if required files exist
check_requirements() {
    local env_file="config/environments/${ENVIRONMENT}.env"
    local base_file="config/environments/base.env"
    local compose_file="docker-compose.${ENVIRONMENT}.yml"
    
    if [[ ! -f "$base_file" ]]; then
        echo -e "${RED}Error: Base configuration file '$base_file' not found.${NC}"
        exit 1
    fi
    
    if [[ ! -f "$env_file" ]]; then
        echo -e "${RED}Error: Environment file '$env_file' not found.${NC}"
        exit 1
    fi
    
    if [[ ! -f "$compose_file" ]] && [[ "$ENVIRONMENT" != "development" ]]; then
        echo -e "${YELLOW}Warning: Docker compose file '$compose_file' not found. Using default docker-compose.yml${NC}"
    fi
}

# Function to generate secure secrets
generate_secrets() {
    echo -e "${BLUE}Generating secure secrets for production...${NC}"
    
    JWT_SECRET=$(openssl rand -hex 32)
    WEBHOOK_SECRET=$(openssl rand -hex 32)
    GENERAL_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    API_KEY=$(openssl rand -hex 24)
    
    echo -e "${GREEN}Generated secrets (save these securely):${NC}"
    echo ""
    echo "JWT_SECRET_KEY_PROD=${JWT_SECRET}"
    echo "WEBHOOK_SIGNING_SECRET_PROD=${WEBHOOK_SECRET}"
    echo "SECRET_KEY_PROD=${GENERAL_SECRET}"
    echo "DB_PASSWORD=${DB_PASSWORD}"
    echo "PAYMENT_GATEWAY_API_KEY_PROD=${API_KEY}"
    echo ""
    echo -e "${YELLOW}Important: Store these in your secret management system!${NC}"
}

# Function to validate configuration
validate_config() {
    echo -e "${BLUE}Validating configuration for environment: ${ENVIRONMENT}${NC}"
    
    # Set environment variable for validation
    export ENVIRONMENT="$ENVIRONMENT"
    
    # Create a temporary Python script to validate config
    cat > /tmp/validate_config.py << EOF
import sys
import os
sys.path.append('config')

try:
    from config_loader import get_config
    config = get_config()
    print(f"✅ Configuration valid for environment: {config.ENVIRONMENT}")
    print(f"   App: {config.APP_NAME} v{config.VERSION}")
    print(f"   Database: {config.DATABASE_URL[:50]}...")
    print(f"   Redis: {config.REDIS_URL[:50]}...")
    print(f"   Debug: {config.DEBUG}")
    print(f"   Log Level: {config.LOG_LEVEL}")
except Exception as e:
    print(f"❌ Configuration validation failed: {e}")
    sys.exit(1)
EOF
    
    python /tmp/validate_config.py
    rm /tmp/validate_config.py
    
    echo -e "${GREEN}Configuration validation complete!${NC}"
}

# Function to start services
start_services() {
    echo -e "${BLUE}Starting services for environment: ${ENVIRONMENT}${NC}"
    check_requirements
    
    export ENVIRONMENT="$ENVIRONMENT"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose -f docker-compose.development.yml up -d
    elif [[ "$ENVIRONMENT" == "production" ]]; then
        # Ensure external network exists
        docker network create billing-network 2>/dev/null || true
        docker-compose -f docker-compose.production.yml up -d
    else
        # For staging, use production compose but with staging env
        docker network create billing-network 2>/dev/null || true
        ENVIRONMENT=staging docker-compose -f docker-compose.production.yml up -d
    fi
    
    echo -e "${GREEN}Services started successfully!${NC}"
}

# Function to stop services
stop_services() {
    echo -e "${BLUE}Stopping services...${NC}"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose -f docker-compose.development.yml down
    elif [[ "$ENVIRONMENT" == "production" ]]; then
        docker-compose -f docker-compose.production.yml down
    else
        ENVIRONMENT=staging docker-compose -f docker-compose.production.yml down
    fi
    
    echo -e "${GREEN}Services stopped successfully!${NC}"
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}Showing logs for environment: ${ENVIRONMENT}${NC}"
    
    local compose_file="docker-compose.development.yml"
    if [[ "$ENVIRONMENT" != "development" ]]; then
        compose_file="docker-compose.production.yml"
    fi
    
    if [[ -n "$SERVICE" ]]; then
        docker-compose -f "$compose_file" logs -f "$SERVICE"
    else
        docker-compose -f "$compose_file" logs -f
    fi
}

# Function to build images
build_images() {
    echo -e "${BLUE}Building images for environment: ${ENVIRONMENT}${NC}"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose -f docker-compose.development.yml build
    else
        # For staging/production, build with proper tags
        docker build -t billing-backend/subscription-service:latest ./subscription-service
        docker build -t billing-backend/payment-service:latest ./payment-service
        
        if [[ -n "$IMAGE_TAG" ]]; then
            docker tag billing-backend/subscription-service:latest billing-backend/subscription-service:$IMAGE_TAG
            docker tag billing-backend/payment-service:latest billing-backend/payment-service:$IMAGE_TAG
        fi
    fi
    
    echo -e "${GREEN}Build complete!${NC}"
}

# Function to deploy
deploy() {
    echo -e "${BLUE}Deploying to environment: ${ENVIRONMENT}${NC}"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        echo -e "${YELLOW}Development deployment - starting local services${NC}"
        start_services
    else
        echo -e "${BLUE}Production/Staging deployment${NC}"
        validate_config
        build_images
        start_services
        
        echo -e "${GREEN}Deployment complete!${NC}"
        echo -e "${YELLOW}Don't forget to run database migrations if needed!${NC}"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        start|stop|restart|logs|build|validate|secrets|deploy)
            ACTION="$1"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ "$ACTION" != "help" && "$ACTION" != "secrets" ]]; then
    validate_environment
fi

# Execute action
case $ACTION in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    logs)
        show_logs
        ;;
    build)
        build_images
        ;;
    validate)
        validate_config
        ;;
    secrets)
        generate_secrets
        ;;
    deploy)
        deploy
        ;;
    help)
        usage
        ;;
    *)
        echo -e "${RED}Unknown action: $ACTION${NC}"
        usage
        exit 1
        ;;
esac 