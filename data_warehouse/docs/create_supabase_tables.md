# Create Supabase Tables Guide
# 创建 Supabase 表结构指南

This guide walks you through creating the database tables for the Shanghai Transport Card data warehouse in Supabase.

## Prerequisites

- ✅ Supabase account created
- ✅ Supabase project created and running
- ✅ Database connection information saved
- ✅ Access to Supabase Dashboard

## Step 1: Open SQL Editor

1. Log in to your Supabase account
2. Select your project (e.g., "shanghai-transport")
3. In the left sidebar, click **"SQL Editor"**
4. Click **"New query"** button (top right)

## Step 2: Execute Schema Script

1. Open the file `sql/supabase_schema.sql` in your project
2. Copy the entire contents of the file
3. Paste the SQL script into the SQL Editor
4. Review the script to understand what it creates:
   - 5 tables: `users`, `stations`, `routes`, `transactions`, `topups`
   - Indexes for performance optimization
   - Foreign key constraints for data integrity
   - Triggers for automatic timestamp updates

## Step 3: Run the Script

1. Click **"Run"** button (or press `Ctrl+Enter` / `Cmd+Enter`)
2. Wait for execution to complete (usually a few seconds)
3. Check the results panel at the bottom:
   - You should see "Success. No rows returned" or similar success message
   - If there are errors, they will be displayed in red

## Step 4: Verify Table Creation

### Option 1: Using Table Editor

1. In the left sidebar, click **"Table Editor"**
2. You should see 5 tables listed:
   - `users`
   - `stations`
   - `routes`
   - `transactions`
   - `topups`
3. Click on each table to verify its structure

### Option 2: Using SQL Query

Run this query in SQL Editor:

```sql
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns 
     WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_name IN ('users', 'stations', 'routes', 'transactions', 'topups')
ORDER BY table_name;
```

Expected output:
```
table_name    | column_count
--------------+-------------
routes        | 7
stations      | 7
topups        | 8
transactions  | 10
users         | 6
```

## Step 5: Verify Indexes

Run this query to check indexes:

```sql
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public' 
  AND tablename IN ('users', 'stations', 'routes', 'transactions', 'topups')
ORDER BY tablename, indexname;
```

You should see multiple indexes for each table, including:
- Primary key indexes
- Foreign key indexes
- Performance indexes (on frequently queried columns)

## Step 6: Verify Foreign Keys

Run this query to check foreign key constraints:

```sql
SELECT
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('users', 'stations', 'routes', 'transactions', 'topups')
ORDER BY tc.table_name, tc.constraint_name;
```

Expected foreign key relationships:
- `routes.start_station_id` → `stations.station_id`
- `routes.end_station_id` → `stations.station_id`
- `transactions.user_id` → `users.user_id`
- `transactions.station_id` → `stations.station_id`
- `transactions.route_id` → `routes.route_id`
- `topups.user_id` → `users.user_id`

## Step 7: Test Table Structure

### Test Users Table

```sql
-- Insert a test user
INSERT INTO users (card_number, card_type, is_verified)
VALUES ('TEST001', 'Regular', true)
RETURNING *;

-- Query users
SELECT * FROM users LIMIT 5;
```

### Test Stations Table

```sql
-- Insert a test station
INSERT INTO stations (station_name, station_type, latitude, longitude, district)
VALUES ('Test Station', 'Metro', 31.2304, 121.4737, 'Shanghai')
RETURNING *;

-- Query stations
SELECT * FROM stations LIMIT 5;
```

### Test Routes Table

```sql
-- First, get a station_id (use one from previous test)
-- Then insert a test route
INSERT INTO routes (route_name, route_type, route_number, start_station_id, end_station_id)
VALUES ('Test Route', 'Metro', 'Line 1', 1, 1)
RETURNING *;

-- Query routes
SELECT * FROM routes LIMIT 5;
```

### Test Transactions Table

```sql
-- Insert a test transaction (requires existing user_id and station_id)
INSERT INTO transactions (user_id, station_id, transaction_date, transaction_time, amount, transaction_type)
VALUES (1, 1, CURRENT_DATE, CURRENT_TIME, 3.00, 'Entry')
RETURNING *;

-- Query transactions
SELECT * FROM transactions LIMIT 5;
```

### Test Topups Table

```sql
-- Insert a test top-up (requires existing user_id)
INSERT INTO topups (user_id, topup_date, topup_time, amount, payment_method)
VALUES (1, CURRENT_DATE, CURRENT_TIME, 50.00, 'Mobile')
RETURNING *;

-- Query topups
SELECT * FROM topups LIMIT 5;
```

## Step 8: Clean Up Test Data (Optional)

After testing, you may want to clean up test data:

```sql
-- Delete test data (in reverse order of dependencies)
DELETE FROM topups WHERE user_id IN (SELECT user_id FROM users WHERE card_number = 'TEST001');
DELETE FROM transactions WHERE user_id IN (SELECT user_id FROM users WHERE card_number = 'TEST001');
DELETE FROM routes WHERE route_name = 'Test Route';
DELETE FROM stations WHERE station_name = 'Test Station';
DELETE FROM users WHERE card_number = 'TEST001';
```

## Common Issues and Solutions

### Issue: "relation already exists"

**Cause**: Tables were already created previously.

**Solution**: 
- Option 1: Drop existing tables first (be careful - this deletes data):
```sql
DROP TABLE IF EXISTS topups CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS stations CASCADE;
DROP TABLE IF EXISTS users CASCADE;
```
Then re-run the schema script.

- Option 2: The script uses `CREATE TABLE IF NOT EXISTS`, so it's safe to run again.

### Issue: Foreign key constraint violation

**Cause**: Trying to insert data that violates foreign key constraints.

**Solution**: 
- Ensure referenced records exist first
- Insert data in the correct order: users → stations → routes → transactions/topups

### Issue: Check constraint violation

**Cause**: Data doesn't meet table constraints (e.g., negative amount, invalid card_type).

**Solution**: 
- Review the constraint requirements in the schema
- Ensure data meets all constraints before inserting

### Issue: Permission denied

**Cause**: Insufficient database permissions.

**Solution**: 
- Ensure you're using the `postgres` user (default admin user)
- Check project settings if using a different user

## Table Structure Summary

### users
- **Purpose**: Store user and card information
- **Key Columns**: user_id (PK), card_number (unique), card_type
- **Indexes**: card_number, card_type, created_at

### stations
- **Purpose**: Store station/stop information
- **Key Columns**: station_id (PK), station_name, station_type, location
- **Indexes**: station_name, station_type, location, district

### routes
- **Purpose**: Store route/line information
- **Key Columns**: route_id (PK), route_name, route_type
- **Foreign Keys**: start_station_id, end_station_id → stations
- **Indexes**: route_name, route_type, station references

### transactions
- **Purpose**: Store transaction records
- **Key Columns**: transaction_id (PK), user_id, station_id, amount
- **Foreign Keys**: user_id → users, station_id → stations, route_id → routes
- **Indexes**: Multiple indexes for performance (user, station, date, etc.)

### topups
- **Purpose**: Store top-up records
- **Key Columns**: topup_id (PK), user_id, amount
- **Foreign Keys**: user_id → users
- **Indexes**: user_id, date, payment_method

## Next Steps

After successfully creating tables:

1. ✅ Verify all tables are created correctly
2. ✅ Verify indexes and constraints
3. ✅ Test basic insert/select operations
4. ➡️ Proceed to **Step 3: Generate Mock Data** (see `generate_test_data.md`)

## Additional Resources

- [Supabase Table Editor Guide](https://supabase.com/docs/guides/database/tables)
- [PostgreSQL CREATE TABLE Documentation](https://www.postgresql.org/docs/current/sql-createtable.html)
- [PostgreSQL Indexes Documentation](https://www.postgresql.org/docs/current/indexes.html)


