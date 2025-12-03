-- Databricks Delta Lake Schema for Data Warehouse
-- This script creates the target tables for dbt models
-- Execute in Databricks SQL Editor or via dbt

-- ============================================
-- Create Catalog and Schema (if not exists)
-- ============================================
-- CREATE CATALOG IF NOT EXISTS shanghai_transport;
-- USE CATALOG shanghai_transport;
-- CREATE SCHEMA IF NOT EXISTS transport_dw;

-- Note: Airbyte may have already created tables in the default schema
-- These tables are for dbt models (staging, dimensions, facts, marts)

-- ============================================
-- Staging Layer Tables (will be created by dbt)
-- ============================================
-- These are typically views, not tables, created by dbt staging models
-- stg_users, stg_stations, stg_routes, stg_transactions, stg_topups

-- ============================================
-- Dimension Tables (created by dbt)
-- ============================================
-- dim_user, dim_station, dim_route, dim_time
-- These will be created by dbt dimension models

-- ============================================
-- Fact Tables (created by dbt)
-- ============================================
-- fact_transactions, fact_topups
-- These will be created by dbt fact models with partitioning

-- ============================================
-- Marts Tables (created by dbt)
-- ============================================
-- daily_active_users, daily_topup_summary, station_flow_daily, etc.
-- These will be created by dbt marts models

-- ============================================
-- Verification Queries
-- ============================================
-- Check existing tables (from Airbyte sync)
-- SHOW TABLES IN hive_metastore.shanghai_transport;

-- Check table structure
-- DESCRIBE EXTENDED hive_metastore.shanghai_transport.users;

-- Note: Actual table creation will be done by dbt models
-- This file is for reference only
