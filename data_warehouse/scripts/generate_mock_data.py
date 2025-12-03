#!/usr/bin/env python3
"""
Generate Mock Data for Shanghai Transport Card Database
生成上海交通卡数据库的模拟测试数据

This script generates realistic test data for:
- Users (with different card types)
- Stations (Metro and Bus stations in Shanghai)
- Routes (Metro lines and Bus routes)
- Transactions (card usage records)
- Topups (card recharge records)
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
fake = Faker('zh_CN')  # Use Chinese locale for realistic Chinese names/addresses

# Database connection configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('SUPABASE_DB_HOST', 'db.your-project.supabase.co'),
    'port': int(os.getenv('SUPABASE_DB_PORT', '5432')),
    'database': os.getenv('SUPABASE_DB_NAME', 'postgres'),
    'user': os.getenv('SUPABASE_DB_USER', 'postgres'),
    'password': os.getenv('SUPABASE_DB_PASSWORD')
}

# Shanghai Metro Lines (real station names)
SHANGHAI_METRO_STATIONS = {
    'Line 1': ['富锦路', '友谊西路', '宝安公路', '共富新村', '呼兰路', '通河新村', '共康路', '彭浦新村', '汶水路', '上海马戏城', '延长路', '中山北路', '上海火车站', '汉中路', '新闸路', '人民广场', '黄陂南路', '陕西南路', '常熟路', '衡山路', '徐家汇', '上海体育馆', '漕宝路', '上海南站', '锦江乐园', '莘庄'],
    'Line 2': ['徐泾东', '虹桥火车站', '虹桥2号航站楼', '淞虹路', '北新泾', '威宁路', '娄山关路', '中山公园', '江苏路', '静安寺', '南京西路', '人民广场', '南京东路', '陆家嘴', '东昌路', '世纪大道', '上海科技馆', '世纪公园', '龙阳路', '张江高科', '金科路', '广兰路', '唐镇', '创新中路', '华夏东路', '川沙', '凌空路', '远东大道', '海天三路', '浦东国际机场'],
    'Line 10': ['新江湾城', '殷高东路', '三门路', '江湾体育场', '五角场', '国权路', '同济大学', '四平路', '邮电新村', '海伦路', '四川北路', '天潼路', '南京东路', '豫园', '老西门', '新天地', '陕西南路', '上海图书馆', '交通大学', '虹桥路', '宋园路', '伊犁路', '水城路', '龙溪路', '上海动物园', '虹桥1号航站楼', '虹桥2号航站楼', '虹桥火车站']
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


def get_db_connection():
    """Establish database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def generate_users(count, conn):
    """Generate user records"""
    print(f"Generating {count} users...")
    cursor = conn.cursor()
    
    users = []
    card_numbers_used = set()
    
    for i in range(count):
        # Generate unique card number
        while True:
            card_number = f"SH{random.randint(100000000, 999999999)}"
            if card_number not in card_numbers_used:
                card_numbers_used.add(card_number)
                break
        
        card_type = random.choices(CARD_TYPES, weights=CARD_TYPE_WEIGHTS)[0]
        is_verified = random.choice([True, False]) if card_type == 'Regular' else True
        
        # Random creation date within last 2 years
        days_ago = random.randint(0, 730)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        users.append((card_number, card_type, is_verified, created_at, created_at))
    
    # Batch insert
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
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users ORDER BY user_id DESC LIMIT %s", (count,))
    return [row[0] for row in cursor.fetchall()]


def generate_stations(conn):
    """Generate station records from real Shanghai Metro stations"""
    print("Generating stations...")
    cursor = conn.cursor()
    
    stations = []
    station_id_map = {}  # Map (line, station_name) -> station_id
    
    station_id = 1
    for line_name, station_names in SHANGHAI_METRO_STATIONS.items():
        for station_name in station_names:
            # Generate realistic coordinates for Shanghai
            latitude = Decimal(str(31.1 + random.uniform(0, 0.3)))  # Shanghai latitude range
            longitude = Decimal(str(121.3 + random.uniform(0, 0.4)))  # Shanghai longitude range
            
            # Determine district (simplified)
            districts = ['黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '浦东新区']
            district = random.choice(districts)
            
            stations.append((
                station_name,
                'Metro',
                latitude,
                longitude,
                district,
                datetime.now()
            ))
            station_id_map[(line_name, station_name)] = station_id
            station_id += 1
    
    # Add some bus stops
    for i in range(50):
        stations.append((
            f"公交站{i+1}",
            'Bus',
            Decimal(str(31.1 + random.uniform(0, 0.3))),
            Decimal(str(121.3 + random.uniform(0, 0.4))),
            random.choice(['黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '浦东新区']),
            datetime.now()
        ))
    
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
    cursor = conn.cursor()
    cursor.execute("SELECT station_id FROM stations ORDER BY station_id")
    return [row[0] for row in cursor.fetchall()]


def generate_routes(station_ids, conn):
    """Generate route records"""
    print("Generating routes...")
    cursor = conn.cursor()
    
    routes = []
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
            
            routes.append((
                line_name,
                'Metro',
                f"Line {line_name.split()[-1]}",
                station_ids[start_idx] if start_idx < len(station_ids) else None,
                station_ids[end_idx] if end_idx < len(station_ids) else None,
                datetime.now()
            ))
            route_id_map[line_name] = route_id
            route_id += 1
    
    # Generate Bus routes
    for i in range(20):
        routes.append((
            f"Bus {100 + i}",
            'Bus',
            f"Route {100 + i}",
            random.choice(station_ids) if station_ids else None,
            random.choice(station_ids) if station_ids else None,
            datetime.now()
        ))
    
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
    cursor = conn.cursor()
    cursor.execute("SELECT route_id FROM routes ORDER BY route_id")
    return [row[0] for row in cursor.fetchall()]


def generate_transactions(user_ids, station_ids, route_ids, days, transactions_per_day, conn):
    """Generate transaction records"""
    print(f"Generating transactions for {days} days ({transactions_per_day} per day)...")
    cursor = conn.cursor()
    
    transactions = []
    start_date = datetime.now() - timedelta(days=days)
    
    total_transactions = days * transactions_per_day
    batch_size = 1000
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        for _ in range(transactions_per_day):
            user_id = random.choice(user_ids)
            station_id = random.choice(station_ids)
            route_id = random.choice(route_ids) if route_ids and random.random() > 0.3 else None
            
            # Generate transaction time within metro operating hours
            hour = random.randint(METRO_START_HOUR, METRO_END_HOUR)
            if hour == METRO_END_HOUR:
                minute = random.randint(0, METRO_END_MINUTE)
            else:
                minute = random.randint(0, 59)
            transaction_time = time(hour, minute)
            
            # Generate transaction amount (typical metro fare: 3-9 RMB)
            amount = Decimal(str(round(random.uniform(3.0, 9.0), 2)))
            
            transaction_type = random.choices(TRANSACTION_TYPES, weights=TRANSACTION_TYPE_WEIGHTS)[0]
            
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
            
            # Batch insert when reaching batch size
            if len(transactions) >= batch_size:
                insert_query = """
                    INSERT INTO transactions 
                    (user_id, station_id, route_id, transaction_date, transaction_time, amount, transaction_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_batch(cursor, insert_query, transactions)
                conn.commit()
                print(f"  Inserted {len(transactions)} transactions (day {day_offset + 1}/{days})...")
                transactions = []
    
    # Insert remaining transactions
    if transactions:
        insert_query = """
            INSERT INTO transactions 
            (user_id, station_id, route_id, transaction_date, transaction_time, amount, transaction_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        execute_batch(cursor, insert_query, transactions)
        conn.commit()
    
    cursor.close()
    print(f"✓ Generated transactions for {days} days")


def generate_topups(user_ids, days, conn):
    """Generate top-up records"""
    print(f"Generating topups for {days} days...")
    cursor = conn.cursor()
    
    topups = []
    start_date = datetime.now() - timedelta(days=days)
    
    # Average 1-2 topups per user per month
    topups_per_day = max(1, len(user_ids) // 30)
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # Generate topups for this day
        daily_topups = random.randint(int(topups_per_day * 0.5), int(topups_per_day * 1.5))
        
        for _ in range(daily_topups):
            user_id = random.choice(user_ids)
            
            # Generate topup time (anytime during day)
            hour = random.randint(6, 22)
            minute = random.randint(0, 59)
            topup_time = time(hour, minute)
            
            # Generate topup amount (typical: 50, 100, 200, 500 RMB)
            amount_options = [50.00, 100.00, 200.00, 500.00]
            amount_weights = [0.4, 0.3, 0.2, 0.1]
            amount = Decimal(str(random.choices(amount_options, weights=amount_weights)[0]))
            
            payment_method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0]
            
            topups.append((
                user_id,
                current_date.date(),
                topup_time,
                amount,
                payment_method,
                datetime.combine(current_date.date(), topup_time)
            ))
    
    # Batch insert
    insert_query = """
        INSERT INTO topups 
        (user_id, topup_date, topup_time, amount, payment_method, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    execute_batch(cursor, insert_query, topups, page_size=500)
    conn.commit()
    cursor.close()
    print(f"✓ Generated {len(topups)} topups")


def verify_data(conn):
    """Verify generated data"""
    print("\nVerifying generated data...")
    cursor = conn.cursor()
    
    tables = ['users', 'stations', 'routes', 'transactions', 'topups']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} records")
    
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Generate mock data for Shanghai Transport Card database')
    parser.add_argument('--users', type=int, default=1000, help='Number of users to generate (default: 1000)')
    parser.add_argument('--days', type=int, default=30, help='Number of days of transaction data (default: 30)')
    parser.add_argument('--transactions-per-day', type=int, default=5000, 
                       help='Number of transactions per day (default: 5000)')
    parser.add_argument('--skip-users', action='store_true', help='Skip user generation')
    parser.add_argument('--skip-stations', action='store_true', help='Skip station generation')
    parser.add_argument('--skip-routes', action='store_true', help='Skip route generation')
    parser.add_argument('--skip-transactions', action='store_true', help='Skip transaction generation')
    parser.add_argument('--skip-topups', action='store_true', help='Skip topup generation')
    
    args = parser.parse_args()
    
    # Validate database password
    if not DB_CONFIG['password']:
        print("Error: SUPABASE_DB_PASSWORD not set in .env file")
        sys.exit(1)
    
    print("=" * 60)
    print("Shanghai Transport Card - Mock Data Generator")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Database Host: {DB_CONFIG['host']}")
    print(f"  Database Name: {DB_CONFIG['database']}")
    print(f"  Users: {args.users}")
    print(f"  Days: {args.days}")
    print(f"  Transactions per day: {args.transactions_per_day}")
    print("=" * 60)
    
    conn = get_db_connection()
    
    try:
        user_ids = []
        station_ids = []
        route_ids = []
        
        if not args.skip_users:
            user_ids = generate_users(args.users, conn)
        
        if not args.skip_stations:
            station_ids = generate_stations(conn)
        
        if not args.skip_routes:
            route_ids = generate_routes(station_ids, conn)
        
        if not args.skip_transactions:
            if not user_ids or not station_ids:
                print("Error: Users and stations must be generated before transactions")
                sys.exit(1)
            generate_transactions(user_ids, station_ids, route_ids, args.days, 
                                args.transactions_per_day, conn)
        
        if not args.skip_topups:
            if not user_ids:
                print("Error: Users must be generated before topups")
                sys.exit(1)
            generate_topups(user_ids, args.days, conn)
        
        verify_data(conn)
        
        print("\n" + "=" * 60)
        print("✓ Data generation completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()


