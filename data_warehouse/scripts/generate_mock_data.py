#!/usr/bin/env python3
"""
Generate Mock Data for Shanghai Transport Card Database
生成上海交通卡数据库的模拟测试数据

This script generates realistic test data for the entire year 2025:
- Users (default: 100 users, with different card types, created before 2025)
- Stations (Metro and Bus stations in Shanghai)
- Routes (Metro lines and Bus routes)
- Transactions (800-1200 daily for weekdays, 480-720 for weekends, with rush hour patterns)
- Topups (card recharge records with monthly patterns)

TARGET DATABASES:
- Supabase/PostgreSQL (default): Writes to tables: users, stations, routes, transactions, topups
- Databricks (use --databricks flag): Writes to tables: src_users, src_stations, src_routes, src_transactions, src_topups

IMPORTANT: This script will CLEAR all existing data before generation (use --skip-clear to prevent this).
Data is distributed across all 12 months of 2025 for monthly analysis.

USAGE:
  # Generate data to Supabase/PostgreSQL (default)
  python generate_mock_data.py

  # Generate data to Databricks
  python generate_mock_data.py --databricks

  # Generate data with custom user count
  python generate_mock_data.py --users 200 --databricks
"""

import os
import sys
import argparse
import random
from datetime import datetime, timedelta, time
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from faker import Faker

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Initialize Faker for generating realistic data
fake = Faker('en_US')  # Use English locale for realistic English names/addresses

# Database connection configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('SUPABASE_DB_HOST', 'db.your-project.supabase.co'),
    'port': int(os.getenv('SUPABASE_DB_PORT', '5432')),
    'database': os.getenv('SUPABASE_DB_NAME', 'postgres'),
    'user': os.getenv('SUPABASE_DB_USER', 'postgres'),
    'password': os.getenv('SUPABASE_DB_PASSWORD')
}

# Databricks configuration
DATABRICKS_CONFIG = {
    'server_hostname': os.getenv('DATABRICKS_SERVER_HOSTNAME'),
    'http_path': os.getenv('DATABRICKS_HTTP_PATH'),
    'access_token': os.getenv('DATABRICKS_TOKEN'),
    'catalog': os.getenv('DATABRICKS_CATALOG', 'workspace'),
    'schema': os.getenv('DATABRICKS_SCHEMA', 'public')
}

# Shanghai Metro Lines (station names in English)
SHANGHAI_METRO_STATIONS = {
    'Line 1': ['Fujin Road', 'Youyi West Road', 'Bao\'an Highway', 'Gongfu Xincun', 'Hulan Road', 'Tonghe Xincun', 'Gonghang Road', 'Pengpu Xincun', 'Wenushui Road', 'Shanghai Circus World', 'Yanchang Road', 'North Zhongshan Road', 'Shanghai Railway Station', 'Hanzhong Road', 'Xinzha Road', 'People\'s Square', 'South Huangpi Road', 'South Shaanxi Road', 'Changshu Road', 'Hengshan Road', 'Xujiahui', 'Shanghai Stadium', 'Caobao Road', 'Shanghai South Railway Station', 'Jinjiang Amusement Park', 'Xinzhuang'],
    'Line 2': ['Xujing East', 'Hongqiao Railway Station', 'Hongqiao Terminal 2', 'Songhong Road', 'Beixinjing', 'Weining Road', 'Loushanguan Road', 'Zhongshan Park', 'Jiangsu Road', 'Jing\'an Temple', 'West Nanjing Road', 'People\'s Square', 'East Nanjing Road', 'Lujiazui', 'Dongchang Road', 'Century Avenue', 'Shanghai Science & Technology Museum', 'Century Park', 'Longyang Road', 'Zhangjiang Hi-Tech Park', 'Jinke Road', 'Guanglan Road', 'Tangzhen', 'Chuangxin Middle Road', 'Huaxia East Road', 'Chuansha', 'Lingkong Road', 'Yuandong Avenue', 'Haitian 3rd Road', 'Pudong International Airport'],
    'Line 10': ['Xinjiangwancheng', 'Yingao East Road', 'Sanmen Road', 'Jiangwan Stadium', 'Wujiaochang', 'Guoquan Road', 'Tongji University', 'Siping Road', 'Youdian Xincun', 'Hailun Road', 'North Sichuan Road', 'Tiantong Road', 'East Nanjing Road', 'Yuyuan Garden', 'Old West Gate', 'Xintiandi', 'South Shaanxi Road', 'Shanghai Library', 'Jiaotong University', 'Hongqiao Road', 'Songyuan Road', 'Yili Road', 'Shuicheng Road', 'Longxi Road', 'Shanghai Zoo', 'Hongqiao Terminal 1', 'Hongqiao Terminal 2', 'Hongqiao Railway Station']
}

# Card types and their distribution
CARD_TYPES = ['Regular', 'Student', 'Senior', 'Disabled']
CARD_TYPE_WEIGHTS = [0.7, 0.15, 0.12, 0.03]  # 70% regular, 15% student, etc.

# Transaction types
TRANSACTION_TYPES = ['Entry', 'Exit', 'Transfer']
TRANSACTION_TYPE_WEIGHTS = [0.4, 0.4, 0.2]  # 40% entry, 40% exit, 20% transfer

# Payment methods for topups
PAYMENT_METHODS = ['Cash', 'Card', 'Mobile', 'Online']
PAYMENT_METHOD_WEIGHTS = [0.2, 0.3, 0.4, 0.1]

# Metro operating hours (5:00 AM to 11:30 PM)
METRO_START_HOUR = 5
METRO_END_HOUR = 23
METRO_END_MINUTE = 30


def get_db_connection(use_databricks=False):
    """Establish database connection (Supabase/PostgreSQL or Databricks)"""
    if use_databricks:
        try:
            from databricks import sql as databricks_sql
            
            if not DATABRICKS_CONFIG['server_hostname'] or not DATABRICKS_CONFIG['access_token']:
                print("Error: Databricks configuration not set. Please check .env file.")
                sys.exit(1)
            
            conn = databricks_sql.connect(
                server_hostname=DATABRICKS_CONFIG['server_hostname'],
                http_path=DATABRICKS_CONFIG['http_path'],
                access_token=DATABRICKS_CONFIG['access_token']
            )
            print(f"✓ Connected to Databricks: {DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}")
            return conn
        except ImportError:
            print("Error: databricks-sql-connector not installed. Install it with: pip install databricks-sql-connector")
            sys.exit(1)
        except Exception as e:
            print(f"Error connecting to Databricks: {e}")
            sys.exit(1)
    else:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except psycopg2.Error as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)


def batch_insert_databricks(cursor, table_name, columns, values_list, conn, batch_size=1000):
    """Helper function for batch insert in Databricks - optimized for performance"""
    total_rows = len(values_list)
    
    for i in range(0, total_rows, batch_size):
        batch = values_list[i:i + batch_size]
        
        # Format all rows in this batch
        all_rows = []
        for values in batch:
            formatted_values = []
            for v in values:
                if v is None:
                    formatted_values.append('NULL')
                elif isinstance(v, bool):
                    formatted_values.append(str(v))
                elif isinstance(v, (int, float, Decimal)):
                    formatted_values.append(str(v))
                elif isinstance(v, (datetime, time)):
                    formatted_values.append(f"'{v}'")
                else:
                    # Escape single quotes in strings
                    escaped_value = str(v).replace("'", "''")
                    formatted_values.append(f"'{escaped_value}'")
            all_rows.append(f"({', '.join(formatted_values)})")
        
        # Single INSERT with multiple rows
        insert_query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES {', '.join(all_rows)}
        """
        cursor.execute(insert_query)
        conn.commit()
        
        if total_rows > batch_size:
            print(f"  Inserted batch {i//batch_size + 1}/{(total_rows + batch_size - 1)//batch_size} ({len(batch)} rows)")


def clear_all_data(conn, use_databricks=False):
    """Clear all existing data from database tables"""
    print("\nClearing existing data from database...")
    cursor = conn.cursor()
    
    try:
        if use_databricks:
            # Databricks uses src_ prefix tables
            catalog = DATABRICKS_CONFIG['catalog']
            schema = DATABRICKS_CONFIG['schema']
            tables = ['src_transactions', 'src_topups', 'src_routes', 'src_stations', 'src_users']
            
            for table in tables:
                full_table_name = f"{catalog}.{schema}.{table}"
                cursor.execute(f"DELETE FROM {full_table_name}")
                # Databricks doesn't support rowcount the same way, so we won't show count
                print(f"  Cleared records from {full_table_name}")
        else:
            # PostgreSQL/Supabase
            tables = ['transactions', 'topups', 'routes', 'stations', 'users']
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
                deleted_count = cursor.rowcount
                print(f"  Cleared {deleted_count} records from {table}")
        
        conn.commit()
        print("✓ All data cleared successfully\n")
    except Exception as e:
        print(f"Error clearing data: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()


def generate_users(count, conn, use_databricks=False):
    """Generate user records"""
    print(f"Generating {count} users...")
    cursor = conn.cursor()
    
    users = []
    card_numbers_used = set()
    user_ids = []
    
    for i in range(count):
        user_id = i + 1  # Generate sequential IDs starting from 1
        
        # Generate unique card number
        while True:
            card_number = f"SH{random.randint(100000000, 999999999)}"
            if card_number not in card_numbers_used:
                card_numbers_used.add(card_number)
                break
        
        card_type = random.choices(CARD_TYPES, weights=CARD_TYPE_WEIGHTS)[0]
        is_verified = random.choice([True, False]) if card_type == 'Regular' else True
        
        # Random creation date before 2025 (between 2022-01-01 and 2024-12-31)
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2024, 12, 31)
        days_range = (end_date - start_date).days
        days_offset = random.randint(0, days_range)
        created_at = start_date + timedelta(days=days_offset)
        
        if use_databricks:
            # Include user_id for Databricks
            users.append((user_id, card_number, card_type, is_verified, created_at, created_at))
        else:
            users.append((card_number, card_type, is_verified, created_at, created_at))
        
        user_ids.append(user_id)
    
    # Batch insert
    if use_databricks:
        table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_users"
        columns = ['user_id', 'card_number', 'card_type', 'is_verified', 'created_at', 'updated_at']
        batch_insert_databricks(cursor, table_name, columns, users, conn)
    else:
        insert_query = """
            INSERT INTO users (card_number, card_type, is_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (card_number) DO NOTHING
        """
        execute_batch(cursor, insert_query, users)
        conn.commit()
    
    cursor.close()
    print(f"✓ Generated {len(users)} users")
    
    # Return user IDs for later use
    if use_databricks:
        # For Databricks, return the IDs we generated
        return user_ids
    else:
        # For PostgreSQL, query the database for auto-generated IDs
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users ORDER BY user_id DESC LIMIT %s", (count,))
        result = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return result


def generate_stations(conn, use_databricks=False):
    """Generate station records from real Shanghai Metro stations"""
    print("Generating stations...")
    cursor = conn.cursor()
    
    stations = []
    station_ids = []
    station_id_map = {}  # Map (line, station_name) -> station_id
    
    station_id = 1
    for line_name, station_names in SHANGHAI_METRO_STATIONS.items():
        for station_name in station_names:
            # Generate realistic coordinates for Shanghai
            latitude = Decimal(str(31.1 + random.uniform(0, 0.3)))  # Shanghai latitude range
            longitude = Decimal(str(121.3 + random.uniform(0, 0.4)))  # Shanghai longitude range
            
            # Determine district (simplified)
            districts = ['Huangpu District', 'Xuhui District', 'Changning District', 'Jing\'an District', 
                        'Putuo District', 'Hongkou District', 'Yangpu District', 'Pudong New Area']
            district = random.choice(districts)
            
            if use_databricks:
                stations.append((
                    station_id,
                    station_name,
                    'Metro',
                    latitude,
                    longitude,
                    district,
                    datetime.now()
                ))
            else:
                stations.append((
                    station_name,
                    'Metro',
                    latitude,
                    longitude,
                    district,
                    datetime.now()
                ))
            
            station_id_map[(line_name, station_name)] = station_id
            station_ids.append(station_id)
            station_id += 1
    
    # Add some bus stops
    for i in range(50):
        if use_databricks:
            stations.append((
                station_id,
                f"Bus Stop {i+1}",
                'Bus',
                Decimal(str(31.1 + random.uniform(0, 0.3))),
                Decimal(str(121.3 + random.uniform(0, 0.4))),
                random.choice(['Huangpu District', 'Xuhui District', 'Changning District', 'Jing\'an District', 
                              'Putuo District', 'Hongkou District', 'Yangpu District', 'Pudong New Area']),
                datetime.now()
            ))
        else:
            stations.append((
                f"Bus Stop {i+1}",
                'Bus',
                Decimal(str(31.1 + random.uniform(0, 0.3))),
                Decimal(str(121.3 + random.uniform(0, 0.4))),
                random.choice(['Huangpu District', 'Xuhui District', 'Changning District', 'Jing\'an District', 
                              'Putuo District', 'Hongkou District', 'Yangpu District', 'Pudong New Area']),
                datetime.now()
            ))
        
        station_ids.append(station_id)
        station_id += 1
    
    # Batch insert
    if use_databricks:
        table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_stations"
        columns = ['station_id', 'station_name', 'station_type', 'latitude', 'longitude', 'district', 'created_at']
        batch_insert_databricks(cursor, table_name, columns, stations, conn)
    else:
        insert_query = """
            INSERT INTO stations (station_name, station_type, latitude, longitude, district, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """
        execute_batch(cursor, insert_query, stations)
        conn.commit()
    
    cursor.close()
    print(f"✓ Generated {len(stations)} stations")
    
    # Return station IDs
    if use_databricks:
        # For Databricks, return the IDs we generated
        return station_ids
    else:
        # For PostgreSQL, query the database for auto-generated IDs
        cursor = conn.cursor()
        cursor.execute("SELECT station_id FROM stations ORDER BY station_id")
        result = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return result


def generate_routes(station_ids, conn, use_databricks=False):
    """Generate route records"""
    print("Generating routes...")
    cursor = conn.cursor()
    
    routes = []
    route_ids = []
    route_id_map = {}
    
    # Generate Metro routes
    route_id = 1
    for line_name in SHANGHAI_METRO_STATIONS.keys():
        # Get stations for this line
        line_stations = SHANGHAI_METRO_STATIONS[line_name]
        if len(line_stations) >= 2:
            # Find station IDs (simplified - using first available stations)
            start_idx = (route_id - 1) * 2 % len(station_ids)
            end_idx = (start_idx + len(line_stations) - 1) % len(station_ids)
            
            if use_databricks:
                routes.append((
                    route_id,
                    line_name,
                    'Metro',
                    f"Line {line_name.split()[-1]}",
                    station_ids[start_idx] if start_idx < len(station_ids) else None,
                    station_ids[end_idx] if end_idx < len(station_ids) else None,
                    datetime.now()
                ))
            else:
                routes.append((
                    line_name,
                    'Metro',
                    f"Line {line_name.split()[-1]}",
                    station_ids[start_idx] if start_idx < len(station_ids) else None,
                    station_ids[end_idx] if end_idx < len(station_ids) else None,
                    datetime.now()
                ))
            
            route_id_map[line_name] = route_id
            route_ids.append(route_id)
            route_id += 1
    
    # Generate Bus routes
    for i in range(20):
        if use_databricks:
            routes.append((
                route_id,
                f"Bus {100 + i}",
                'Bus',
                f"Route {100 + i}",
                random.choice(station_ids) if station_ids else None,
                random.choice(station_ids) if station_ids else None,
                datetime.now()
            ))
        else:
            routes.append((
                f"Bus {100 + i}",
                'Bus',
                f"Route {100 + i}",
                random.choice(station_ids) if station_ids else None,
                random.choice(station_ids) if station_ids else None,
                datetime.now()
            ))
        
        route_ids.append(route_id)
        route_id += 1
    
    # Batch insert
    if use_databricks:
        table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_routes"
        columns = ['route_id', 'route_name', 'route_type', 'route_number', 'start_station_id', 'end_station_id', 'created_at']
        batch_insert_databricks(cursor, table_name, columns, routes, conn)
    else:
        insert_query = """
            INSERT INTO routes (route_name, route_type, route_number, start_station_id, end_station_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """
        execute_batch(cursor, insert_query, routes)
        conn.commit()
    
    cursor.close()
    print(f"✓ Generated {len(routes)} routes")
    
    # Return route IDs
    if use_databricks:
        # For Databricks, return the IDs we generated
        return route_ids
    else:
        # For PostgreSQL, query the database for auto-generated IDs
        cursor = conn.cursor()
        cursor.execute("SELECT route_id FROM routes ORDER BY route_id")
        result = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return result


def generate_transactions(user_ids, station_ids, route_ids, days, transactions_per_day, conn, use_databricks=False):
    """Generate transaction records for the entire year 2025 with realistic patterns"""
    print(f"Generating transactions for 2025 full year with realistic patterns...")
    cursor = conn.cursor()
    
    transactions = []
    # Fixed date range for 2025
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    days = (end_date - start_date).days + 1  # 365 days
    
    batch_size = 1000
    transaction_id = 1  # Start transaction_id counter
    
    # Rush hour definitions
    morning_rush_hours = list(range(7, 10))  # 7-9 AM
    evening_rush_hours = list(range(17, 20))  # 5-7 PM
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # Adjust transaction volume based on day of week
        is_weekend = current_date.weekday() >= 5  # Saturday=5, Sunday=6
        
        # Daily transactions with random fluctuation (800-1200 range)
        if is_weekend:
            # 60% volume on weekends (480-720 range)
            daily_transactions = random.randint(480, 720)
        else:
            # Full volume on weekdays (800-1200 range)
            daily_transactions = random.randint(800, 1200)
        
        for _ in range(daily_transactions):
            user_id = random.choice(user_ids)
            station_id = random.choice(station_ids)
            route_id = random.choice(route_ids) if route_ids and random.random() > 0.3 else None
            
            # Generate transaction time with rush hour bias
            if not is_weekend and random.random() < 0.5:
                # 50% chance during rush hours on weekdays
                if random.random() < 0.5:
                    hour = random.choice(morning_rush_hours)
                else:
                    hour = random.choice(evening_rush_hours)
            else:
                # Regular distribution during operating hours
                hour = random.randint(METRO_START_HOUR, METRO_END_HOUR)
            
            if hour == METRO_END_HOUR:
                minute = random.randint(0, METRO_END_MINUTE)
            else:
                minute = random.randint(0, 59)
            transaction_time = time(hour, minute)
            
            # Generate transaction amount (typical metro fare: 3-9 RMB)
            amount = Decimal(str(round(random.uniform(3.0, 9.0), 2)))
            
            transaction_type = random.choices(TRANSACTION_TYPES, weights=TRANSACTION_TYPE_WEIGHTS)[0]
            
            if use_databricks:
                transactions.append((
                    transaction_id,
                    user_id,
                    station_id,
                    route_id,
                    current_date.date(),
                    transaction_time,
                    amount,
                    transaction_type,
                    datetime.combine(current_date.date(), transaction_time)
                ))
            else:
                transactions.append((
                    user_id,
                    station_id,
                    route_id,
                    current_date.date(),
                    transaction_time,
                    amount,
                    transaction_type,
                    datetime.combine(current_date.date(), transaction_time)
                ))
            
            transaction_id += 1
            
            # Batch insert when reaching batch size
            if len(transactions) >= batch_size:
                if use_databricks:
                    table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_transactions"
                    columns = ['transaction_id', 'user_id', 'station_id', 'route_id', 'transaction_date', 'transaction_time', 'amount', 'transaction_type', 'created_at']
                    batch_insert_databricks(cursor, table_name, columns, transactions, conn)
                else:
                    insert_query = """
                        INSERT INTO transactions 
                        (user_id, station_id, route_id, transaction_date, transaction_time, amount, transaction_type, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    execute_batch(cursor, insert_query, transactions)
                    conn.commit()
                print(f"  Inserted {len(transactions)} transactions (day {day_offset + 1}/{days}, {current_date.strftime('%Y-%m-%d')})...")
                transactions = []
    
    # Insert remaining transactions
    if transactions:
        if use_databricks:
            table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_transactions"
            columns = ['transaction_id', 'user_id', 'station_id', 'route_id', 'transaction_date', 'transaction_time', 'amount', 'transaction_type', 'created_at']
            batch_insert_databricks(cursor, table_name, columns, transactions, conn)
        else:
            insert_query = """
                INSERT INTO transactions 
                (user_id, station_id, route_id, transaction_date, transaction_time, amount, transaction_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            execute_batch(cursor, insert_query, transactions)
            conn.commit()
    
    cursor.close()
    print(f"✓ Generated transactions for entire year 2025 (365 days)")


def generate_topups(user_ids, days, conn, use_databricks=False):
    """Generate top-up records for the entire year 2025"""
    print(f"Generating topups for 2025 full year...")
    cursor = conn.cursor()
    
    topups = []
    topup_id = 1  # Start topup_id counter
    # Fixed date range for 2025
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    days = (end_date - start_date).days + 1  # 365 days
    
    # Average 1.5 topups per user per month, spread across the year
    topups_per_day = max(1, int(len(user_ids) * 1.5 / 30))
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # More topups at beginning of month (payday effect)
        if current_date.day <= 5:
            daily_topups = int(topups_per_day * random.uniform(1.5, 2.0))
        elif current_date.day <= 10:
            daily_topups = int(topups_per_day * random.uniform(1.2, 1.5))
        else:
            daily_topups = random.randint(int(topups_per_day * 0.5), int(topups_per_day * 1.2))
        
        for _ in range(daily_topups):
            user_id = random.choice(user_ids)
            
            # Generate topup time (anytime during day, with peak during lunch and evening)
            if random.random() < 0.3:
                # 30% during lunch time (12-14)
                hour = random.randint(12, 14)
            elif random.random() < 0.5:
                # 20% during evening (18-21)
                hour = random.randint(18, 21)
            else:
                # 50% distributed throughout the day
                hour = random.randint(6, 22)
            
            minute = random.randint(0, 59)
            topup_time = time(hour, minute)
            
            # Generate topup amount (typical: 50, 100, 200, 500 RMB)
            amount_options = [50.00, 100.00, 200.00, 500.00]
            amount_weights = [0.4, 0.3, 0.2, 0.1]
            amount = Decimal(str(random.choices(amount_options, weights=amount_weights)[0]))
            
            payment_method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0]
            
            if use_databricks:
                topups.append((
                    topup_id,
                    user_id,
                    current_date.date(),
                    topup_time,
                    amount,
                    payment_method,
                    datetime.combine(current_date.date(), topup_time)
                ))
            else:
                topups.append((
                    user_id,
                    current_date.date(),
                    topup_time,
                    amount,
                    payment_method,
                    datetime.combine(current_date.date(), topup_time)
                ))
            
            topup_id += 1
    
    # Batch insert
    if use_databricks:
        table_name = f"{DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}.src_topups"
        columns = ['topup_id', 'user_id', 'topup_date', 'topup_time', 'amount', 'payment_method', 'created_at']
        batch_insert_databricks(cursor, table_name, columns, topups, conn)
    else:
        insert_query = """
            INSERT INTO topups 
            (user_id, topup_date, topup_time, amount, payment_method, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        execute_batch(cursor, insert_query, topups, page_size=500)
        conn.commit()
    
    cursor.close()
    print(f"✓ Generated {len(topups)} topups for entire year 2025")


def verify_data(conn, use_databricks=False):
    """Verify generated data"""
    print("\nVerifying generated data...")
    cursor = conn.cursor()
    
    if use_databricks:
        catalog = DATABRICKS_CONFIG['catalog']
        schema = DATABRICKS_CONFIG['schema']
        tables = ['src_users', 'src_stations', 'src_routes', 'src_transactions', 'src_topups']
        
        for table in tables:
            full_table_name = f"{catalog}.{schema}.{table}"
            cursor.execute(f"SELECT COUNT(*) FROM {full_table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} records")
    else:
        tables = ['users', 'stations', 'routes', 'transactions', 'topups']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} records")
    
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Generate mock data for Shanghai Transport Card database (2025 full year)')
    parser.add_argument('--users', type=int, default=100, help='Number of users to generate (default: 100)')
    parser.add_argument('--days', type=int, default=365, help='Number of days (DEPRECATED: now generates full year 2025)')
    parser.add_argument('--transactions-per-day', type=int, default=1000, 
                       help='This parameter is DEPRECATED. Daily transactions now range 800-1200 for weekdays, 480-720 for weekends')
    parser.add_argument('--databricks', action='store_true', help='Write data to Databricks src_* tables instead of Supabase')
    parser.add_argument('--skip-clear', action='store_true', help='Skip clearing existing data before generation')
    parser.add_argument('--skip-users', action='store_true', help='Skip user generation')
    parser.add_argument('--skip-stations', action='store_true', help='Skip station generation')
    parser.add_argument('--skip-routes', action='store_true', help='Skip route generation')
    parser.add_argument('--skip-transactions', action='store_true', help='Skip transaction generation')
    parser.add_argument('--skip-topups', action='store_true', help='Skip topup generation')
    
    args = parser.parse_args()
    
    # Validate database configuration
    if args.databricks:
        if not DATABRICKS_CONFIG['server_hostname'] or not DATABRICKS_CONFIG['access_token']:
            print("Error: Databricks configuration not set in .env file")
            print("Required: DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN")
            sys.exit(1)
    else:
        if not DB_CONFIG['password']:
            print("Error: SUPABASE_DB_PASSWORD not set in .env file")
            sys.exit(1)
    
    print("=" * 60)
    print("Shanghai Transport Card - Mock Data Generator")
    print("=" * 60)
    print(f"Configuration:")
    if args.databricks:
        print(f"  Target: Databricks")
        print(f"  Catalog.Schema: {DATABRICKS_CONFIG['catalog']}.{DATABRICKS_CONFIG['schema']}")
        print(f"  Tables: src_users, src_stations, src_routes, src_transactions, src_topups")
    else:
        print(f"  Target: Supabase/PostgreSQL")
        print(f"  Database Host: {DB_CONFIG['host']}")
        print(f"  Database Name: {DB_CONFIG['database']}")
    print(f"  Users: {args.users}")
    print(f"  Date Range: 2025-01-01 to 2025-12-31 (Full Year)")
    print(f"  Daily Transactions: 800-1200 (weekdays), 480-720 (weekends)")
    print(f"  Clear existing data: {not args.skip_clear}")
    print("=" * 60)
    
    conn = get_db_connection(use_databricks=args.databricks)
    
    try:
        # Clear existing data before generation
        if not args.skip_clear:
            clear_all_data(conn, use_databricks=args.databricks)
        
        user_ids = []
        station_ids = []
        route_ids = []
        
        if not args.skip_users:
            user_ids = generate_users(args.users, conn, use_databricks=args.databricks)
        
        if not args.skip_stations:
            station_ids = generate_stations(conn, use_databricks=args.databricks)
        
        if not args.skip_routes:
            route_ids = generate_routes(station_ids, conn, use_databricks=args.databricks)
        
        if not args.skip_transactions:
            if not user_ids or not station_ids:
                print("Error: Users and stations must be generated before transactions")
                sys.exit(1)
            generate_transactions(user_ids, station_ids, route_ids, args.days, 
                                1000, conn, use_databricks=args.databricks)  # transactions_per_day is deprecated, using fixed value
        
        if not args.skip_topups:
            if not user_ids:
                print("Error: Users must be generated before topups")
                sys.exit(1)
            generate_topups(user_ids, args.days, conn, use_databricks=args.databricks)
        
        verify_data(conn, use_databricks=args.databricks)
        
        print("\n" + "=" * 60)
        print("✓ Data generation completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        if not args.databricks:
            # Databricks doesn't support rollback
            conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()


