-- Shanghai Transport Card Database Schema
-- Supabase PostgreSQL Database
-- Execute this script in Supabase Dashboard > SQL Editor

-- Enable UUID extension (if needed)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    card_number VARCHAR(50) UNIQUE NOT NULL,
    card_type VARCHAR(20) NOT NULL CHECK (card_type IN ('Regular', 'Student', 'Senior', 'Disabled')),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_card_number ON users(card_number);
CREATE INDEX IF NOT EXISTS idx_users_card_type ON users(card_type);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 2. Stations Table
-- ============================================
CREATE TABLE IF NOT EXISTS stations (
    station_id BIGSERIAL PRIMARY KEY,
    station_name VARCHAR(100) NOT NULL,
    station_type VARCHAR(20) NOT NULL CHECK (station_type IN ('Metro', 'Bus', 'Ferry', 'Other')),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    district VARCHAR(50),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for stations table
CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(station_name);
CREATE INDEX IF NOT EXISTS idx_stations_type ON stations(station_type);
CREATE INDEX IF NOT EXISTS idx_stations_location ON stations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_stations_district ON stations(district);

-- ============================================
-- 3. Routes Table
-- ============================================
CREATE TABLE IF NOT EXISTS routes (
    route_id BIGSERIAL PRIMARY KEY,
    route_name VARCHAR(100) NOT NULL,
    route_type VARCHAR(20) NOT NULL CHECK (route_type IN ('Metro', 'Bus', 'Ferry', 'Other')),
    route_number VARCHAR(50),
    start_station_id BIGINT,
    end_station_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign keys
    CONSTRAINT fk_routes_start_station 
        FOREIGN KEY (start_station_id) 
        REFERENCES stations(station_id) 
        ON DELETE SET NULL,
    CONSTRAINT fk_routes_end_station 
        FOREIGN KEY (end_station_id) 
        REFERENCES stations(station_id) 
        ON DELETE SET NULL
);

-- Indexes for routes table
CREATE INDEX IF NOT EXISTS idx_routes_name ON routes(route_name);
CREATE INDEX IF NOT EXISTS idx_routes_type ON routes(route_type);
CREATE INDEX IF NOT EXISTS idx_routes_start_station ON routes(start_station_id);
CREATE INDEX IF NOT EXISTS idx_routes_end_station ON routes(end_station_id);

-- ============================================
-- 4. Transactions Table
-- ============================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    station_id BIGINT NOT NULL,
    route_id BIGINT,
    transaction_date DATE NOT NULL,
    transaction_time TIME NOT NULL,
    amount DECIMAL(10, 2) NOT NULL CHECK (amount > 0),
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('Entry', 'Exit', 'Transfer', 'Top-up', 'Refund')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign keys
    CONSTRAINT fk_transactions_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(user_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_transactions_station 
        FOREIGN KEY (station_id) 
        REFERENCES stations(station_id) 
        ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_route 
        FOREIGN KEY (route_id) 
        REFERENCES routes(route_id) 
        ON DELETE SET NULL
);

-- Indexes for transactions table
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_station_id ON transactions(station_id);
CREATE INDEX IF NOT EXISTS idx_transactions_route_id ON transactions(route_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_datetime ON transactions(transaction_date, transaction_time);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_transactions_station_date ON transactions(station_id, transaction_date);

-- ============================================
-- 5. Topups Table
-- ============================================
CREATE TABLE IF NOT EXISTS topups (
    topup_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    topup_date DATE NOT NULL,
    topup_time TIME NOT NULL,
    amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 10.00),  -- Minimum top-up amount
    payment_method VARCHAR(20) CHECK (payment_method IN ('Cash', 'Card', 'Mobile', 'Online', 'Other')),
    topup_location VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key
    CONSTRAINT fk_topups_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(user_id) 
        ON DELETE CASCADE
);

-- Indexes for topups table
CREATE INDEX IF NOT EXISTS idx_topups_user_id ON topups(user_id);
CREATE INDEX IF NOT EXISTS idx_topups_date ON topups(topup_date);
CREATE INDEX IF NOT EXISTS idx_topups_user_date ON topups(user_id, topup_date);
CREATE INDEX IF NOT EXISTS idx_topups_payment_method ON topups(payment_method);

-- ============================================
-- Comments for Documentation
-- ============================================
COMMENT ON TABLE users IS 'User information and transport card details';
COMMENT ON TABLE stations IS 'Station/stop information for metro, bus, and other transport modes';
COMMENT ON TABLE routes IS 'Route/line information connecting stations';
COMMENT ON TABLE transactions IS 'Transaction records for card usage';
COMMENT ON TABLE topups IS 'Top-up records for card recharge';

COMMENT ON COLUMN users.card_type IS 'Card type: Regular, Student, Senior, or Disabled';
COMMENT ON COLUMN stations.station_type IS 'Type of station: Metro, Bus, Ferry, or Other';
COMMENT ON COLUMN routes.route_type IS 'Type of route: Metro, Bus, Ferry, or Other';
COMMENT ON COLUMN transactions.transaction_type IS 'Type of transaction: Entry, Exit, Transfer, Top-up, or Refund';
COMMENT ON COLUMN transactions.amount IS 'Transaction amount in RMB, must be positive';
COMMENT ON COLUMN topups.amount IS 'Top-up amount in RMB, minimum 10.00';

-- ============================================
-- Verification Queries (Optional - for testing)
-- ============================================
-- Check table creation
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'public' 
-- AND table_name IN ('users', 'stations', 'routes', 'transactions', 'topups');

-- Check indexes
-- SELECT indexname, tablename FROM pg_indexes 
-- WHERE schemaname = 'public' 
-- AND tablename IN ('users', 'stations', 'routes', 'transactions', 'topups');

-- Check foreign keys
-- SELECT conname, conrelid::regclass, confrelid::regclass 
-- FROM pg_constraint 
-- WHERE contype = 'f' 
-- AND conrelid::regclass::text IN ('users', 'stations', 'routes', 'transactions', 'topups');
