-- Billing System Database Initialization Script
-- This script creates the complete database schema and seeds initial data

-- Create database (if running outside Docker)
-- CREATE DATABASE billing_db;
-- CREATE USER billing_user WITH PASSWORD 'billing_pass';
-- GRANT ALL PRIVILEGES ON DATABASE billing_db TO billing_user;

-- Use the database
-- \c billing_db;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), -- For JWT authentication
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on email for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Plans table
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'AED',
    billing_cycle VARCHAR(20) DEFAULT 'monthly', -- monthly, yearly
    trial_period_days INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    features JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, active, trial, past_due, cancelled, revoked
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    canceled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_end_date ON subscriptions(end_date);

-- Subscription events table for audit trail
CREATE TABLE IF NOT EXISTS subscription_events (
    id SERIAL PRIMARY KEY,
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    transaction_id UUID,
    old_plan_id INTEGER REFERENCES plans(id),
    new_plan_id INTEGER REFERENCES plans(id),
    effective_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for subscription events
CREATE INDEX IF NOT EXISTS idx_subscription_events_subscription_id ON subscription_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_event_type ON subscription_events(event_type);

-- Payment Webhook Requests table
CREATE TABLE IF NOT EXISTS payment_webhook_requests (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for webhook requests
CREATE INDEX IF NOT EXISTS idx_webhook_requests_event_id ON payment_webhook_requests(event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_requests_processed ON payment_webhook_requests(processed);

-- Transactions table (for payment service)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    subscription_id UUID,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'AED',
    status VARCHAR(20) NOT NULL,
    gateway_reference VARCHAR(100),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for transactions
CREATE INDEX IF NOT EXISTS idx_transactions_subscription_id ON transactions(subscription_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_gateway_reference ON transactions(gateway_reference);

-- Gateway webhook requests table
CREATE TABLE IF NOT EXISTS gateway_webhook_requests (
    id SERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT _gateway_webhook_transaction_uc UNIQUE (transaction_id)
);

-- Webhook outbound requests table
CREATE TABLE IF NOT EXISTS webhook_outbound_requests (
    id SERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL,
    url VARCHAR(500) NOT NULL,
    payload JSONB NOT NULL,
    response_code INTEGER,
    response_body TEXT,
    retry_count INTEGER DEFAULT 0,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User usage tracking table
CREATE TABLE IF NOT EXISTS user_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature_name VARCHAR(50) NOT NULL,
    usage_count INTEGER DEFAULT 0,
    reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_user_feature UNIQUE (user_id, feature_name)
);

-- Create indexes for user usage
CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_feature_name ON user_usage(feature_name);
CREATE INDEX IF NOT EXISTS idx_user_usage_reset_at ON user_usage(reset_at);

-- Insert seed data

-- Insert users (with password hashes for testing - password is 'password123')
INSERT INTO users (email, password_hash, first_name, last_name) VALUES
('john.doe@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwAlCh7WzMQoIJe7q', 'John', 'Doe'),
('jane.smith@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwAlCh7WzMQoIJe7q', 'Jane', 'Smith'),
('alice.johnson@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwAlCh7WzMQoIJe7q', 'Alice', 'Johnson'),
('bob.wilson@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwAlCh7WzMQoIJe7q', 'Bob', 'Wilson'),
('carol.brown@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwAlCh7WzMQoIJe7q', 'Carol', 'Brown')
ON CONFLICT (email) DO NOTHING;

-- Insert plans
INSERT INTO plans (id, name, description, price, billing_cycle, trial_period_days, features) VALUES
(1, 'Basic Plan', 'Perfect for individuals', 29.00, 'monthly', 0, '{"limits": {"api_calls": 1000, "premium_api_calls": 100}, "storage_gb": 5, "support": "email"}'),
(2, 'Pro Plan', 'Great for growing teams', 99.00, 'monthly', 0, '{"limits": {"api_calls": 10000, "premium_api_calls": 1000}, "storage_gb": 50, "support": "priority", "analytics": true}'),
(3, 'Enterprise Plan', 'For large organizations', 299.00, 'monthly', 0, '{"limits": {"api_calls": 100000, "premium_api_calls": 10000, "enterprise_api_calls": 1000}, "storage_gb": 500, "support": "dedicated", "analytics": true, "custom_features": true}'),
(4, 'Annual Pro', 'Pro plan with annual billing', 999.00, 'yearly', 0, '{"limits": {"api_calls": 10000, "premium_api_calls": 1000}, "storage_gb": 50, "support": "priority", "analytics": true}'),
(5, 'Free Trial', 'Free trial plan', 1.00, 'monthly', 14, '{"limits": {"api_calls": 100}, "storage_gb": 1, "support": "community", "trial": true, "period_days": 14, "renewal_plan": 1}')
ON CONFLICT (id) DO NOTHING;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to all tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_plans_updated_at BEFORE UPDATE ON plans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_subscription_events_updated_at BEFORE UPDATE ON subscription_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_payment_webhook_requests_updated_at BEFORE UPDATE ON payment_webhook_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_gateway_webhook_requests_updated_at BEFORE UPDATE ON gateway_webhook_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_webhook_outbound_requests_updated_at BEFORE UPDATE ON webhook_outbound_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_usage_updated_at BEFORE UPDATE ON user_usage FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 