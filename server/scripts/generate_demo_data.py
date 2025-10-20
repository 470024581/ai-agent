#!/usr/bin/env python3
"""
Demo Data Generation Script for AI Agent ERP System
Generates realistic business data for 2022-2024 (3 years)
Creates customers, products, orders, sales, and inventory data with proper relationships
"""

import sqlite3
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database path - Use the same path as db_operations.py
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "smart.db"

# Data generation parameters (scaled up)
NUM_CUSTOMERS = 200          # was 80
NUM_PRODUCTS = 80            # was 35
ORDERS_PER_YEAR = 2000       # was 800
SALES_PER_YEAR = 8000        # was 3000

# Business data templates
CUSTOMER_TYPES = ['VIP', 'regular', 'wholesale']
CUSTOMER_NAMES = [
    'ABC Corporation', 'XYZ Ltd', 'Tech Solutions Inc', 'Global Trading Co',
    'Modern Electronics', 'Smart Systems', 'Digital Innovations', 'Future Tech',
    'Advanced Solutions', 'Innovation Hub', 'Tech Partners', 'Digital Dynamics',
    'NextGen Systems', 'Cyber Solutions', 'Data Analytics Co', 'Cloud Services',
    'AI Technologies', 'Machine Learning Corp', 'Big Data Systems', 'Analytics Pro',
    'Business Intelligence', 'Data Science Co', 'Predictive Analytics', 'Smart Analytics',
    'Enterprise Solutions', 'Corporate Systems', 'Business Systems', 'Enterprise Tech',
    'Corporate Solutions', 'Business Intelligence', 'Data Insights', 'Analytics Plus',
    'Tech Enterprise', 'Digital Enterprise', 'Smart Business', 'Intelligent Systems',
    'Automated Solutions', 'Process Automation', 'Workflow Systems', 'Efficiency Pro',
    'Productivity Solutions', 'Performance Systems', 'Optimization Co', 'Efficiency Plus',
    'Streamlined Solutions', 'Process Optimization', 'Workflow Automation', 'Smart Processes',
    'Intelligent Automation', 'Automated Workflows', 'Process Intelligence', 'Smart Automation',
    'Digital Transformation', 'Business Transformation', 'Digital Evolution', 'Tech Evolution',
    'Innovation Systems', 'Creative Solutions', 'Design Systems', 'Creative Tech',
    'Design Solutions', 'Creative Analytics', 'Design Intelligence', 'Creative Data',
    'Visual Analytics', 'Design Analytics', 'Creative Intelligence', 'Visual Intelligence',
    'Design Intelligence', 'Creative Systems', 'Visual Systems', 'Design Tech',
    'Creative Tech', 'Visual Tech', 'Design Tech', 'Creative Solutions',
    'Visual Solutions', 'Design Solutions', 'Creative Systems', 'Visual Systems'
]

PRODUCT_CATEGORIES = {
    'Electronics': ['Smartphones', 'Laptops', 'Tablets', 'Accessories', 'Gadgets'],
    'Software': ['Operating Systems', 'Applications', 'Security', 'Development Tools', 'Analytics'],
    'Services': ['Consulting', 'Support', 'Training', 'Implementation', 'Maintenance'],
    'Hardware': ['Servers', 'Networking', 'Storage', 'Peripherals', 'Components'],
    'Cloud': ['Infrastructure', 'Platform', 'Software', 'Storage', 'Computing']
}

PRODUCT_NAMES = {
    'Electronics': [
        'iPhone Pro', 'Samsung Galaxy', 'MacBook Pro', 'iPad Air', 'AirPods Pro',
        'Wireless Charger', 'Bluetooth Speaker', 'Smart Watch', 'Tablet Stand', 'USB Hub'
    ],
    'Software': [
        'Windows 11 Pro', 'Office 365', 'Adobe Creative Suite', 'Visual Studio', 'IntelliJ IDEA',
        'Antivirus Pro', 'Firewall Suite', 'VPN Client', 'Data Analytics Tool', 'BI Dashboard'
    ],
    'Services': [
        'IT Consulting', 'System Integration', 'Technical Support', 'Training Program', '24/7 Support',
        'Implementation Service', 'Migration Service', 'Custom Development', 'Security Audit', 'Performance Optimization'
    ],
    'Hardware': [
        'Dell Server', 'Cisco Router', 'HP Switch', 'NAS Storage', 'RAID Controller',
        'Network Card', 'Memory Module', 'SSD Drive', 'Power Supply', 'Cooling Fan'
    ],
    'Cloud': [
        'AWS EC2 Instance', 'Azure VM', 'Google Cloud Storage', 'Docker Container', 'Kubernetes Cluster',
        'Cloud Database', 'CDN Service', 'Load Balancer', 'Auto Scaling', 'Backup Service'
    ]
}

PAYMENT_METHODS = ['Credit Card', 'Bank Transfer', 'Cash', 'Check', 'PayPal', 'Cryptocurrency']
ORDER_STATUSES = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
SALESPEOPLE = ['Alice Johnson', 'Bob Smith', 'Carol Davis', 'David Wilson', 'Eva Brown', 'Frank Miller']

def generate_customer_id():
    """Generate a unique customer ID"""
    return f"CUST_{uuid.uuid4().hex[:8].upper()}"

def generate_product_id():
    """Generate a unique product ID"""
    return f"PROD_{uuid.uuid4().hex[:8].upper()}"

def generate_order_id():
    """Generate a unique order ID"""
    return f"ORD_{uuid.uuid4().hex[:8].upper()}"

def generate_sale_id():
    """Generate a unique sale ID"""
    return f"SALE_{uuid.uuid4().hex[:8].upper()}"

def generate_customers(cursor, num_customers):
    """Generate customer data"""
    logger.info(f"Generating {num_customers} customers...")
    
    customers = []
    for i in range(num_customers):
        customer_id = generate_customer_id()
        customer_name = random.choice(CUSTOMER_NAMES)
        if i < 10:  # First 10 customers are VIP
            customer_type = 'VIP'
        elif i < 30:  # Next 20 are wholesale
            customer_type = 'wholesale'
        else:
            customer_type = 'regular'
        
        customer = {
            'customer_id': customer_id,
            'customer_name': customer_name,
            'contact_person': f"Contact Person {i+1}",
            'phone': f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            'email': f"contact{i+1}@{customer_name.lower().replace(' ', '')}.com",
            'address': f"{random.randint(100, 9999)} Main St, City {i+1}, State {random.randint(1, 50)}",
            'customer_type': customer_type,
            'created_at': datetime(2022, 1, 1) + timedelta(days=random.randint(0, 365))
        }
        customers.append(customer)
    
    # Insert customers
    cursor.executemany('''
        INSERT OR REPLACE INTO customers 
        (customer_id, customer_name, contact_person, phone, email, address, customer_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(c['customer_id'], c['customer_name'], c['contact_person'], c['phone'], 
           c['email'], c['address'], c['customer_type'], c['created_at']) for c in customers])
    
    logger.info(f"Generated {len(customers)} customers")
    return customers

def generate_products(cursor, num_products):
    """Generate product data"""
    logger.info(f"Generating {num_products} products...")
    
    products = []
    product_count = 0
    
    for category, subcategories in PRODUCT_CATEGORIES.items():
        for subcategory in subcategories:
            if product_count >= num_products:
                break
            
            # Generate 1-3 products per subcategory
            num_subcategory_products = min(random.randint(1, 3), num_products - product_count)
            
            for i in range(num_subcategory_products):
                product_id = generate_product_id()
                product_name = random.choice(PRODUCT_NAMES[category])
                
                # Price ranges based on category
                if category == 'Electronics':
                    unit_price = random.uniform(50, 2000)
                    cost_price = unit_price * random.uniform(0.6, 0.8)
                elif category == 'Software':
                    unit_price = random.uniform(100, 5000)
                    cost_price = unit_price * random.uniform(0.3, 0.6)
                elif category == 'Services':
                    unit_price = random.uniform(500, 10000)
                    cost_price = unit_price * random.uniform(0.7, 0.9)
                elif category == 'Hardware':
                    unit_price = random.uniform(200, 5000)
                    cost_price = unit_price * random.uniform(0.6, 0.8)
                else:  # Cloud
                    unit_price = random.uniform(100, 2000)
                    cost_price = unit_price * random.uniform(0.4, 0.7)
                
                product = {
                    'product_id': product_id,
                    'product_name': f"{product_name} {subcategory}",
                    'category': category,
                    'subcategory': subcategory,
                    'unit_price': round(unit_price, 2),
                    'cost_price': round(cost_price, 2),
                    'description': f"High-quality {subcategory.lower()} for {category.lower()} applications",
                    'supplier': f"Supplier {random.randint(1, 20)}",
                    'created_at': datetime(2022, 1, 1) + timedelta(days=random.randint(0, 365))
                }
                products.append(product)
                product_count += 1
            
            if product_count >= num_products:
                break
    
    # Insert products
    cursor.executemany('''
        INSERT OR REPLACE INTO products 
        (product_id, product_name, category, subcategory, unit_price, cost_price, description, supplier, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(p['product_id'], p['product_name'], p['category'], p['subcategory'], 
           p['unit_price'], p['cost_price'], p['description'], p['supplier'], p['created_at']) for p in products])
    
    logger.info(f"Generated {len(products)} products")
    return products

def generate_orders(cursor, customers, years=[2022, 2023, 2024]):
    """Generate order data for specified years"""
    logger.info(f"Generating orders for years {years}...")
    
    orders = []
    orders_per_year = ORDERS_PER_YEAR // len(years)
    
    for year in years:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        
        for i in range(orders_per_year):
            order_id = generate_order_id()
            customer = random.choice(customers)
            
            # Order date within the year
            order_date = start_date + timedelta(days=random.randint(0, 364))
            
            # Order amount based on customer type
            if customer['customer_type'] == 'VIP':
                base_amount = random.uniform(1000, 50000)
            elif customer['customer_type'] == 'wholesale':
                base_amount = random.uniform(5000, 100000)
            else:
                base_amount = random.uniform(100, 10000)
            
            order = {
                'order_id': order_id,
                'customer_id': customer['customer_id'],
                'order_date': order_date,
                'total_amount': round(base_amount, 2),
                'status': random.choice(ORDER_STATUSES),
                'payment_method': random.choice(PAYMENT_METHODS),
                'shipping_address': customer['address'],
                'notes': f"Order notes for {customer['customer_name']}",
                'created_at': order_date,
                'updated_at': order_date
            }
            orders.append(order)
    
    # Insert orders
    cursor.executemany('''
        INSERT OR REPLACE INTO orders 
        (order_id, customer_id, order_date, total_amount, status, payment_method, shipping_address, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(o['order_id'], o['customer_id'], o['order_date'], o['total_amount'], 
           o['status'], o['payment_method'], o['shipping_address'], o['notes'], 
           o['created_at'], o['updated_at']) for o in orders])
    
    logger.info(f"Generated {len(orders)} orders")
    return orders

def generate_sales(cursor, customers, products, orders, years=[2022, 2023, 2024]):
    """Generate sales data for specified years"""
    logger.info(f"Generating sales for years {years}...")
    
    sales = []
    sales_per_year = SALES_PER_YEAR // len(years)
    
    for year in years:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        
        for i in range(sales_per_year):
            sale_id = generate_sale_id()
            customer = random.choice(customers)
            product = random.choice(products)
            
            # Find a random order for this customer (or create a standalone sale)
            customer_orders = [o for o in orders if o['customer_id'] == customer['customer_id']]
            order = random.choice(customer_orders) if customer_orders else None
            
            # Sale date within the year
            sale_date = start_date + timedelta(days=random.randint(0, 364))
            
            # Quantity based on product category
            if product['category'] == 'Services':
                quantity = random.randint(1, 5)
            elif product['category'] == 'Software':
                quantity = random.randint(1, 10)
            else:
                quantity = random.randint(1, 50)
            
            # Price per unit (may have discounts)
            base_price = product['unit_price']
            discount_rate = random.uniform(0, 0.3) if customer['customer_type'] == 'VIP' else random.uniform(0, 0.15)
            price_per_unit = base_price * (1 - discount_rate)
            total_amount = price_per_unit * quantity
            discount_amount = (base_price - price_per_unit) * quantity
            
            sale = {
                'sale_id': sale_id,
                'order_id': order['order_id'] if order else None,
                'customer_id': customer['customer_id'],
                'product_id': product['product_id'],
                'product_name': product['product_name'],
                'quantity_sold': quantity,
                'price_per_unit': round(price_per_unit, 2),
                'total_amount': round(total_amount, 2),
                'sale_date': sale_date,
                'salesperson': random.choice(SALESPEOPLE),
                'discount_amount': round(discount_amount, 2),
                'created_at': sale_date
            }
            sales.append(sale)
    
    # Insert sales
    cursor.executemany('''
        INSERT OR REPLACE INTO sales 
        (sale_id, order_id, customer_id, product_id, product_name, quantity_sold, price_per_unit, 
         total_amount, sale_date, salesperson, discount_amount, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(s['sale_id'], s['order_id'], s['customer_id'], s['product_id'], s['product_name'], 
           s['quantity_sold'], s['price_per_unit'], s['total_amount'], s['sale_date'], 
           s['salesperson'], s['discount_amount'], s['created_at']) for s in sales])
    
    logger.info(f"Generated {len(sales)} sales records")
    return sales

def generate_inventory(cursor, products):
    """Generate inventory data"""
    logger.info(f"Generating inventory for {len(products)} products...")
    
    inventory_records = []
    
    for product in products:
        # Stock level based on product category and sales frequency
        if product['category'] == 'Services':
            stock_level = random.randint(0, 10)  # Services have low/no stock
        elif product['category'] == 'Software':
            stock_level = random.randint(50, 500)  # Software can have high stock
        else:
            stock_level = random.randint(10, 200)  # Physical products
        
        min_stock = max(5, stock_level // 10)
        max_stock = stock_level * 2
        
        inventory = {
            'product_id': product['product_id'],
            'stock_level': stock_level,
            'min_stock_level': min_stock,
            'max_stock_level': max_stock,
            'last_updated': datetime.now() - timedelta(days=random.randint(1, 30)),
            'last_restocked': datetime.now() - timedelta(days=random.randint(30, 180)),
            'warehouse_location': f"Warehouse {random.randint(1, 5)}"
        }
        inventory_records.append(inventory)
    
    # Insert inventory
    cursor.executemany('''
        INSERT OR REPLACE INTO inventory 
        (product_id, stock_level, min_stock_level, max_stock_level, last_updated, last_restocked, warehouse_location)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [(i['product_id'], i['stock_level'], i['min_stock_level'], i['max_stock_level'], 
           i['last_updated'], i['last_restocked'], i['warehouse_location']) for i in inventory_records])
    
    logger.info(f"Generated {len(inventory_records)} inventory records")
    return inventory_records

def main():
    """Main function to generate all demo data"""
    logger.info("Starting demo data generation...")
    
    # Ensure database directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Test connection and verify database path
    cursor.execute("SELECT 1")
    test_result = cursor.fetchone()
    logger.info(f"Database connection test: {test_result}")
    logger.info(f"Database path: {DB_PATH}")
    logger.info(f"Database exists: {DB_PATH.exists()}")
    
    try:
        # Ensure schema exists before deleting data (idempotent)
        logger.info("Ensuring ERP tables exist before clearing...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                customer_type TEXT NOT NULL DEFAULT 'regular',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                unit_price REAL NOT NULL,
                cost_price REAL,
                description TEXT,
                supplier TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                order_date DATETIME NOT NULL,
                total_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payment_method TEXT,
                shipping_address TEXT,
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                sale_id TEXT PRIMARY KEY,
                order_id TEXT,
                customer_id TEXT,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity_sold INTEGER NOT NULL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                sale_date DATETIME NOT NULL,
                salesperson TEXT,
                discount_amount REAL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders (order_id),
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,
                stock_level INTEGER NOT NULL DEFAULT 0,
                min_stock_level INTEGER DEFAULT 10,
                max_stock_level INTEGER DEFAULT 1000,
                last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_restocked DATETIME,
                warehouse_location TEXT,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')

        # Clear existing data (optional - comment out if you want to keep existing data)
        logger.info("Clearing existing demo data...")
        cursor.execute("DELETE FROM sales")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM inventory")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM customers")
        
        # Generate data in dependency order
        logger.info("Starting data generation...")
        customers = generate_customers(cursor, NUM_CUSTOMERS)
        logger.info("Customers generated, checking count...")
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        logger.info(f"Customer count after generation: {customer_count}")
        
        products = generate_products(cursor, NUM_PRODUCTS)
        logger.info("Products generated, checking count...")
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        logger.info(f"Product count after generation: {product_count}")
        
        orders = generate_orders(cursor, customers)
        logger.info("Orders generated, checking count...")
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]
        logger.info(f"Order count after generation: {order_count}")
        
        sales = generate_sales(cursor, customers, products, orders)
        logger.info("Sales generated, checking count...")
        cursor.execute("SELECT COUNT(*) FROM sales")
        sale_count = cursor.fetchone()[0]
        logger.info(f"Sale count after generation: {sale_count}")
        
        inventory = generate_inventory(cursor, products)
        logger.info("Inventory generated, checking count...")
        cursor.execute("SELECT COUNT(*) FROM inventory")
        inventory_count = cursor.fetchone()[0]
        logger.info(f"Inventory count after generation: {inventory_count}")
        
        # Commit all changes
        conn.commit()
        logger.info("Changes committed to database")
        
        # Verify data was actually saved
        cursor.execute("SELECT COUNT(*) FROM customers")
        post_commit_count = cursor.fetchone()[0]
        logger.info(f"Post-commit customer count: {post_commit_count}")
        
        # Print summary
        logger.info("Demo data generation completed successfully!")
        logger.info(f"Generated:")
        logger.info(f"  - {len(customers)} customers")
        logger.info(f"  - {len(products)} products")
        logger.info(f"  - {len(orders)} orders")
        logger.info(f"  - {len(sales)} sales records")
        logger.info(f"  - {len(inventory)} inventory records")
        
        # Verify data integrity
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sales")
        sale_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM inventory")
        inventory_count = cursor.fetchone()[0]
        
        logger.info(f"Verification - Records in database:")
        logger.info(f"  - Customers: {customer_count}")
        logger.info(f"  - Products: {product_count}")
        logger.info(f"  - Orders: {order_count}")
        logger.info(f"  - Sales: {sale_count}")
        logger.info(f"  - Inventory: {inventory_count}")
        
    except Exception as e:
        logger.error(f"Error generating demo data: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
