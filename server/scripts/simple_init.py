#!/usr/bin/env python3
"""
Simple database initialization script
"""

import sqlite3
import csv
from pathlib import Path

# Database configuration
# Adjust DATABASE_DIR to point to the data directory from the scripts directory
DATABASE_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_PATH = DATABASE_DIR / "smart.db"

def init_simple():
    """Simple database initialization."""
    print("Initializing database...")
    
    # Ensure directory exists
    DATABASE_DIR.mkdir(exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,
                stock_level INTEGER NOT NULL,
                last_updated DATETIME NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                sale_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity_sold INTEGER NOT NULL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                sale_date DATETIME NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        print("✓ Tables created")
        
        # Clear existing data
        cursor.execute("DELETE FROM sales")
        cursor.execute("DELETE FROM inventory") 
        cursor.execute("DELETE FROM products")
        
        # Import products
        products_csv = DATABASE_DIR / "products_data.csv"
        if products_csv.exists():
            print(f"Importing products from {products_csv}")
            with open(products_csv, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    cursor.execute('''
                        INSERT INTO products (product_id, product_name, category, unit_price)
                        VALUES (?, ?, ?, ?)
                    ''', (row['product_id'], row['product_name'], row['category'], float(row['unit_price'])))
                    count += 1
            print(f"✓ Imported {count} products")
        
        # Import inventory
        inventory_csv = DATABASE_DIR / "inventory_data.csv"
        if inventory_csv.exists():
            print(f"Importing inventory from {inventory_csv}")
            with open(inventory_csv, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    cursor.execute('''
                        INSERT INTO inventory (product_id, stock_level, last_updated)
                        VALUES (?, ?, ?)
                    ''', (row['product_id'], int(row['stock_level']), row['last_updated']))
                    count += 1
            print(f"✓ Imported {count} inventory records")
        
        # Import sales
        sales_csv = DATABASE_DIR / "sales_data.csv"
        if sales_csv.exists():
            print(f"Importing sales from {sales_csv}")
            with open(sales_csv, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    cursor.execute('''
                        INSERT INTO sales (sale_id, product_id, product_name, quantity_sold, 
                                         price_per_unit, total_amount, sale_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (row['sale_id'], row['product_id'], row['product_name'], 
                          int(row['quantity_sold']), float(row['price_per_unit']), 
                          float(row['total_amount']), row['sale_date']))
                    count += 1
            print(f"✓ Imported {count} sales records")
        
        conn.commit()
        print("✓ Database initialization completed successfully!")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM inventory")  
        inventory_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        print(f"Database contains: {products_count} products, {inventory_count} inventory records, {sales_count} sales records")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_simple() 