-- PostgreSQL Logical Replication Setup for Debezium
-- PostgreSQL 逻辑复制设置（Debezium 必需）
--
-- This script enables logical replication required by Debezium CDC.
-- Execute this before registering the Debezium connector.

-- ============================================
-- 1. Set wal_level to logical
-- ============================================
-- This requires PostgreSQL restart to take effect
ALTER SYSTEM SET wal_level = 'logical';

-- Note: After running this, you must restart PostgreSQL:
-- docker restart postgres

-- ============================================
-- 2. Grant Replication Permission
-- ============================================
-- Ensure dbuser has replication privilege
ALTER USER dbuser WITH REPLICATION;

-- ============================================
-- 3. Verify Configuration (after restart)
-- ============================================
-- Run these after restarting PostgreSQL:
-- SHOW wal_level;  -- Should return 'logical'
-- SELECT rolname, rolreplication FROM pg_roles WHERE rolname = 'dbuser';  -- Should show rolreplication = true

-- ============================================
-- Notes:
-- ============================================
-- 1. Debezium will automatically create the replication slot and publication
-- 2. The replication slot name is configured in postgres.json: "slot.name": "debezium_transport_slot"
-- 3. The publication will include all tables matching "table.include.list": "public.*"


