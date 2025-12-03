# Generate Test Data Guide
# 生成测试数据指南

This guide explains how to use the mock data generation script to populate the Shanghai Transport Card database with test data.

## Prerequisites

- ✅ Supabase database tables created (see `create_supabase_tables.md`)
- ✅ Python 3.8 or higher installed
- ✅ `.env` file configured with database credentials
- ✅ Required Python packages installed

## Step 1: Install Required Dependencies

Install the required Python packages:

```bash
pip install psycopg2-binary python-dotenv faker
```

Or if you're using a requirements file:

```bash
pip install -r requirements.txt
```

**Required packages:**
- `psycopg2-binary`: PostgreSQL database adapter
- `python-dotenv`: Load environment variables from .env file
- `faker`: Generate realistic fake data (with Chinese locale support)

## Step 2: Verify Environment Variables

Ensure your `.env` file in `data_warehouse` directory contains:

```bash
# Supabase Database Configuration
SUPABASE_DB_HOST=your-database-host
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=your-database-user
SUPABASE_DB_PASSWORD=your-database-password
```

**Note**: The script will read these variables automatically. Make sure the `.env` file is in the `data_warehouse` directory.

## Step 3: Run the Data Generation Script

### Basic Usage

Navigate to the scripts directory and run:

```bash
cd data_warehouse/scripts
python generate_mock_data.py
```

This will generate:
- 1000 users (default)
- Stations (real Shanghai Metro stations)
- Routes (Metro lines and Bus routes)
- 30 days of transaction data (default)
- 5000 transactions per day (default)
- Top-up records for 30 days

### Custom Parameters

You can customize the data generation with command-line arguments:

```bash
# Generate 2000 users and 60 days of data
python generate_mock_data.py --users 2000 --days 60

# Generate 10000 transactions per day
python generate_mock_data.py --transactions-per-day 10000

# Generate only users and stations (skip transactions and topups)
python generate_mock_data.py --skip-transactions --skip-topups

# Generate only transactions (assumes users/stations already exist)
python generate_mock_data.py --skip-users --skip-stations --skip-routes
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--users` | Number of users to generate | 1000 |
| `--days` | Number of days of transaction data | 30 |
| `--transactions-per-day` | Number of transactions per day | 5000 |
| `--skip-users` | Skip user generation | False |
| `--skip-stations` | Skip station generation | False |
| `--skip-routes` | Skip route generation | False |
| `--skip-transactions` | Skip transaction generation | False |
| `--skip-topups` | Skip topup generation | False |

## Step 4: Verify Generated Data

After running the script, verify the data in Supabase:

### Option 1: Using Supabase Dashboard

1. Go to Supabase Dashboard > Table Editor
2. Click on each table to view the generated data
3. Check record counts match your expectations

### Option 2: Using SQL Queries

Run these queries in Supabase SQL Editor:

```sql
-- Check record counts
SELECT 
    'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'stations', COUNT(*) FROM stations
UNION ALL
SELECT 'routes', COUNT(*) FROM routes
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'topups', COUNT(*) FROM topups;

-- Check user distribution by card type
SELECT card_type, COUNT(*) as count 
FROM users 
GROUP BY card_type;

-- Check transaction distribution by type
SELECT transaction_type, COUNT(*) as count 
FROM transactions 
GROUP BY transaction_type;

-- Check date range of transactions
SELECT 
    MIN(transaction_date) as earliest_date,
    MAX(transaction_date) as latest_date,
    COUNT(*) as total_transactions
FROM transactions;
```

## Generated Data Details

### Users
- **Card Numbers**: Unique format `SH` + 9 digits (e.g., `SH123456789`)
- **Card Types**: Regular (70%), Student (15%), Senior (12%), Disabled (3%)
- **Verification**: Random, but Student/Senior/Disabled cards are always verified
- **Creation Dates**: Random dates within last 2 years

### Stations
- **Metro Stations**: Real Shanghai Metro station names from Lines 1, 2, and 10
- **Bus Stops**: Generated bus stop names
- **Locations**: Realistic coordinates within Shanghai area
- **Districts**: Random Shanghai districts

### Routes
- **Metro Routes**: Based on real Shanghai Metro lines
- **Bus Routes**: Generated bus route numbers (100-119)
- **Station Associations**: Linked to generated stations

### Transactions
- **Time Range**: Within Metro operating hours (5:00 AM - 11:30 PM)
- **Amounts**: Typical metro fares (3-9 RMB)
- **Types**: Entry (40%), Exit (40%), Transfer (20%)
- **Distribution**: Evenly distributed across days and stations

### Topups
- **Amounts**: Common top-up amounts (50, 100, 200, 500 RMB)
- **Frequency**: 1-2 topups per user per month on average
- **Payment Methods**: Cash (20%), Card (30%), Mobile (40%), Online (10%)
- **Time Range**: 6:00 AM - 10:00 PM

## Performance Considerations

### Large Data Generation

For generating large amounts of data:

1. **Batch Processing**: The script uses batch inserts for efficiency
2. **Transaction Batching**: Transactions are inserted in batches of 1000
3. **Memory Usage**: Large datasets may take time - be patient

### Recommended Limits

- **Users**: Up to 10,000 users (reasonable performance)
- **Days**: Up to 365 days (1 year of data)
- **Transactions per day**: Up to 50,000 (may take several minutes)

### Example: Generate 1 Year of Data

```bash
python generate_mock_data.py --users 5000 --days 365 --transactions-per-day 10000
```

This may take 10-30 minutes depending on your database connection speed.

## Troubleshooting

### Error: "SUPABASE_DB_PASSWORD not set"

**Solution**: Ensure your `.env` file exists in `data_warehouse` directory and contains `SUPABASE_DB_PASSWORD`.

### Error: "Error connecting to database"

**Solutions**:
- Verify database credentials in `.env` file
- Check if Supabase project is running
- Verify network connectivity
- Check if IP is whitelisted (if using IP restrictions)

### Error: "Foreign key constraint violation"

**Solution**: Ensure you generate data in the correct order:
1. Users
2. Stations
3. Routes (depends on stations)
4. Transactions (depends on users, stations, routes)
5. Topups (depends on users)

### Error: "Duplicate key value violates unique constraint"

**Solution**: The script handles duplicates with `ON CONFLICT DO NOTHING`. If you see this error, it may indicate:
- Running the script multiple times (this is OK - duplicates are skipped)
- Manual data conflicts

### Slow Performance

**Solutions**:
- Reduce `--transactions-per-day` value
- Generate data in smaller batches
- Check database connection speed
- Consider generating data during off-peak hours

## Data Quality Checks

After generation, run these quality checks:

```sql
-- Check for NULL values in required fields
SELECT 'users' as table_name, COUNT(*) as null_card_numbers
FROM users WHERE card_number IS NULL;

SELECT 'transactions' as table_name, COUNT(*) as null_amounts
FROM transactions WHERE amount IS NULL OR amount <= 0;

-- Check data ranges
SELECT 
    MIN(amount) as min_amount,
    MAX(amount) as max_amount,
    AVG(amount) as avg_amount
FROM transactions;

SELECT 
    MIN(amount) as min_topup,
    MAX(amount) as max_topup,
    AVG(amount) as avg_topup
FROM topups;

-- Check date ranges
SELECT 
    MIN(transaction_date) as earliest_transaction,
    MAX(transaction_date) as latest_transaction
FROM transactions;
```

## Next Steps

After generating test data:

1. ✅ Verify data quality using SQL queries
2. ✅ Check data distribution and ranges
3. ➡️ Proceed to **Step 4: Data Validation** (see `validate_data.md`)

## Additional Resources

- [Supabase Table Editor Guide](https://supabase.com/docs/guides/database/tables)
- [PostgreSQL psycopg2 Documentation](https://www.psycopg.org/docs/)
- [Faker Documentation](https://faker.readthedocs.io/)


