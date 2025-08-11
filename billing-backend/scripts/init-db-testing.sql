-- Billing System Database Initialization Script - TESTING VERSION
-- This script creates the complete database schema and seeds initial data with SMALL LIMITS for testing

-- Create database (if running outside Docker)
-- CREATE DATABASE billing_test_db;
-- CREATE USER billing_user WITH PASSWORD 'billing_pass';
-- GRANT ALL PRIVILEGES ON DATABASE billing_test_db TO billing_user;

-- Use the database
-- \c billing_test_db;

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
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES plans(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_date TIMESTAMP WITH TIME ZONE,
    canceled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_id ON subscriptions(plan_id);

-- Subscription Events table for tracking plan changes, renewals, etc.
CREATE TABLE IF NOT EXISTS subscription_events (
    id SERIAL PRIMARY KEY,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- created, renewed, plan_changed, cancelled, etc.
    transaction_id UUID, -- Link to payment transaction if applicable
    old_plan_id INTEGER REFERENCES plans(id),
    new_plan_id INTEGER REFERENCES plans(id),
    effective_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for subscription events
CREATE INDEX IF NOT EXISTS idx_subscription_events_subscription_id ON subscription_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_type ON subscription_events(event_type);

-- User Usage table for tracking feature usage
CREATE TABLE IF NOT EXISTS user_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    feature_name VARCHAR(50) NOT NULL,
    usage_count INTEGER DEFAULT 0,
    reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, feature_name)
);

-- Create indexes for user usage
CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_feature ON user_usage(feature_name);
CREATE INDEX IF NOT EXISTS idx_user_usage_reset_at ON user_usage(reset_at);

-- Transactions table (from payment service)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'AED',
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, success, failed
    gateway_reference VARCHAR(255),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for transactions
CREATE INDEX IF NOT EXISTS idx_transactions_subscription_id ON transactions(subscription_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_gateway_ref ON transactions(gateway_reference);

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

-- Insert test users
INSERT INTO users (email, password_hash, first_name, last_name) VALUES
('testuser1@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj95lxfaq5PW', 'Test', 'User1'),
('testuser2@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj95lxfaq5PW', 'Test', 'User2'),
('testuser3@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj95lxfaq5PW', 'Test', 'User3'),
('admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj95lxfaq5PW', 'Admin', 'User')
ON CONFLICT (email) DO NOTHING;

-- Insert plans with SMALL LIMITS for testing
INSERT INTO plans (id, name, description, price, billing_cycle, trial_period_days, features) VALUES
(5, 'Trial Plan', 'Free trial plan', 1.00, 'monthly', 0.00139, '{"limits": {"api_calls": 5}, "storage_gb": 1, "support": "community", "trial": true, "period_days": 0.00139, "renewal_plan": 1}'),
(1, 'Basic Plan', 'Perfect for individuals', 29.00, 'monthly', 0, '{"limits": {"api_calls": 10, "premium_api_calls": 5}, "storage_gb": 5, "support": "email"}'),
(2, 'Pro Plan', 'Great for growing teams', 99.00, 'monthly', 0, '{"limits": {"api_calls": 50, "premium_api_calls": 25}, "storage_gb": 50, "support": "priority", "analytics": true}'),
(3, 'Enterprise Plan', 'For large organizations', 299.00, 'monthly', 0, '{"limits": {"api_calls": 100, "premium_api_calls": 50, "enterprise_api_calls": 20}, "storage_gb": 500, "support": "dedicated", "analytics": true, "custom_features": true}')
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

-- Create test data verification view
CREATE OR REPLACE VIEW plan_limits_summary AS
SELECT 
    name,
    price,
    billing_cycle,
    features->>'limits' as limits,
    features->>'features' as available_features
FROM plans 
ORDER BY price;

-- Display the created plans for verification
SELECT 
    name,
    price || ' ' || currency as price_currency,
    billing_cycle,
    (features->'limits'->>'api_calls')::int as basic_api_calls,
    (features->'limits'->>'premium_api_calls')::int as premium_api_calls,
    (features->'limits'->>'enterprise_api_calls')::int as enterprise_api_calls,
    ((features->'limits'->>'api_calls')::int + 
     COALESCE((features->'limits'->>'premium_api_calls')::int, 0) + 
     COALESCE((features->'limits'->>'enterprise_api_calls')::int, 0)) as total_api_calls
FROM plans 
ORDER BY price;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_plans_name ON plans(name);
CREATE INDEX IF NOT EXISTS idx_plans_features_limits ON plans USING GIN ((features->'limits'));
CREATE INDEX IF NOT EXISTS idx_plans_features_features ON plans USING GIN ((features->'features')); 