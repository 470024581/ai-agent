#!/usr/bin/env python3
"""
Augments existing CSV data with new records.
- Adds 500 new products.
- Adds inventory for new products.
- Adds 500 new sales records for recent months (March-May 2024).
"""
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products_data.csv"
INVENTORY_FILE = DATA_DIR / "inventory_data.csv"
SALES_FILE = DATA_DIR / "sales_data.csv"

CATEGORIES = ["Electronics", "Accessories", "Office Furniture", "Home Automation", "Storage", 
              "Lifestyle", "Audio", "Sports & Outdoors", "Wearables", "Home Goods", 
              "Kitchenware", "Outdoor", "Software", "Home Appliances", "Gaming", 
              "Office Supplies", "Travel", "Health & Wellness", "Eyewear", "Crafting", 
              "Decor", "Pet Supplies", "Garden", "Automotive", "Comfort", "Groceries", 
              "Art Supplies", "Security", "Tools", "Bedding", "Stationery"]

PRODUCT_NAME_PREFIXES = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Omega", "Nova", "Orion", "Stellar",
                         "Quantum", "Aura", "Terra", "Hydro", "Zenith", "Cosmo", "Flexi", "Chrono", "Giga", "Silent",
                         "Aqua", "Aero", "Culinary", "Solar", "Robo", "Data", "Vision", "Power", "Eco", "Gamer"]
PRODUCT_NAME_SUFFIXES = ["Pro", "Max", "Ultra", "Mini", "Plus", "X1", "Z200", "Series 9", "Flow", "Wave", "Byte",
                         "Glow", "Stream", "Desk", "Fit", "Guard", "Core", "Key", "Pure", "Speed", "Master",
                         "Flare", "Vac", "Safe", "Print", "Grip", "Mate", "Beam", "Drill", "Cast"]

def get_last_id(filepath, id_column_name, prefix):
    """Gets the last ID from a CSV file and determines the next numerical part."""
    last_num = 0
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        num_part = int(row[id_column_name].replace(prefix, ''))
                        if num_part > last_num:
                            last_num = num_part
                    except ValueError:
                        continue # Skip rows with non-conforming IDs
    except FileNotFoundError:
        print(f"Warning: File {filepath} not found. Starting IDs from 1.")
    return last_num

def generate_new_products(num_products=500):
    """Generates new product data."""
    print(f"Generating {num_products} new products...")
    existing_products = []
    if PRODUCTS_FILE.exists():
        with open(PRODUCTS_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_products.append(dict(row))
    
    last_product_num = get_last_id(PRODUCTS_FILE, 'product_id', 'P')
    new_products_data = []
    
    for i in range(num_products):
        new_id_num = last_product_num + 1 + i
        product_id = f"P{str(new_id_num).zfill(4)}"
        product_name = f"{random.choice(PRODUCT_NAME_PREFIXES)}{random.choice(PRODUCT_NAME_SUFFIXES)} {random.randint(100, 999)}"
        category = random.choice(CATEGORIES)
        unit_price = round(random.uniform(5.0, 1500.0), 2)
        new_products_data.append({
            'product_id': product_id,
            'product_name': product_name,
            'category': category,
            'unit_price': unit_price
        })
    print(f"Generated {len(new_products_data)} products.")
    return new_products_data, existing_products + new_products_data

def generate_new_inventory(products_data):
    """Generates new inventory data for the given products."""
    print(f"Generating inventory for {len(products_data)} products...")
    new_inventory_data = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get existing product IDs from inventory to avoid duplicates if script is run multiple times on products
    # but not on inventory.
    existing_inventory_product_ids = set()
    if INVENTORY_FILE.exists():
        with open(INVENTORY_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_inventory_product_ids.add(row['product_id'])

    for product in products_data:
        if product['product_id'] in existing_inventory_product_ids:
            continue # Skip if inventory for this product already exists
        stock_level = random.randint(5, 500)
        new_inventory_data.append({
            'product_id': product['product_id'],
            'stock_level': stock_level,
            'last_updated': now_str 
        })
    print(f"Generated {len(new_inventory_data)} new inventory records.")
    return new_inventory_data

def generate_new_sales(all_products_list, num_sales=500):
    """Generates new sales data."""
    print(f"Generating {num_sales} new sales records...")
    if not all_products_list:
        print("Error: No products available to generate sales. Aborting sales generation.")
        return []

    last_sale_num = get_last_id(SALES_FILE, 'sale_id', 'S')
    new_sales_data = []
    
    # Define date range: March 1, 2024 to May 28, 2024
    start_date = datetime(2024, 3, 1)
    end_date = datetime(2024, 5, 28, 23, 59, 59)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    
    for i in range(num_sales):
        new_id_num = last_sale_num + 1 + i
        sale_id = f"S{str(new_id_num).zfill(5)}"
        
        product = random.choice(all_products_list)
        product_id = product['product_id']
        product_name = product['product_name']
        try:
            price_per_unit = float(product['unit_price'])
        except ValueError:
            print(f"Warning: Could not parse unit_price for product {product_id}. Using default 10.0")
            price_per_unit = 10.0

        quantity_sold = random.randint(1, 5)
        total_amount = round(quantity_sold * price_per_unit, 2)
        
        random_number_of_days = random.randrange(days_between_dates + 1)
        random_date = start_date + timedelta(days=random_number_of_days, 
                                             hours=random.randint(0,23), 
                                             minutes=random.randint(0,59), 
                                             seconds=random.randint(0,59))
        sale_date_str = random_date.strftime("%Y-%m-%d %H:%M:%S")
        
        new_sales_data.append({
            'sale_id': sale_id,
            'product_id': product_id,
            'product_name': product_name,
            'quantity_sold': quantity_sold,
            'price_per_unit': price_per_unit,
            'total_amount': total_amount,
            'sale_date': sale_date_str
        })
    print(f"Generated {len(new_sales_data)} sales records.")
    return new_sales_data

def append_to_csv(filepath, data_to_append, fieldnames):
    """Appends data to a CSV file. Creates the file if it doesn't exist."""
    file_exists = filepath.exists()
    try:
        with open(filepath, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists or filepath.stat().st_size == 0: # Check if file is empty
                writer.writeheader()
            writer.writerows(data_to_append)
        print(f"Appended {len(data_to_append)} records to {filepath}")
    except Exception as e:
        print(f"Error appending to {filepath}: {e}")

def main():
    """Main function to augment data."""
    print("Starting data augmentation...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Products
    generated_products, all_products_list = generate_new_products(500)
    if generated_products:
        product_fieldnames = ['product_id', 'product_name', 'category', 'unit_price']
        append_to_csv(PRODUCTS_FILE, generated_products, product_fieldnames)

    # 2. Inventory for new products
    # We only want to generate inventory for the *newly generated* products
    new_inventory_items = generate_new_inventory(generated_products)
    if new_inventory_items:
        inventory_fieldnames = ['product_id', 'stock_level', 'last_updated']
        append_to_csv(INVENTORY_FILE, new_inventory_items, inventory_fieldnames)

    # 3. Sales
    # Use all_products_list (existing + newly generated) for sales
    new_sales = generate_new_sales(all_products_list, 500)
    if new_sales:
        sales_fieldnames = ['sale_id', 'product_id', 'product_name', 'quantity_sold', 'price_per_unit', 'total_amount', 'sale_date']
        append_to_csv(SALES_FILE, new_sales, sales_fieldnames)
    
    print("\nData augmentation complete.")
    print(f"Please check the files in {DATA_DIR}")
    print("Remember to re-initialize the database using 'python scripts/init_database.py' to see changes.")

if __name__ == "__main__":
    main() 