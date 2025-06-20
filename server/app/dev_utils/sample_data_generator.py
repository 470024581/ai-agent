import csv
import random
import datetime
import os
from pathlib import Path

# Define a list of sample products with categories and realistic price ranges
PRODUCTS = [
    {"id_start": 1, "name": "Laptop Pro 13\"", "category": "Electronics", "price_min": 900, "price_max": 1500},
    {"id_start": 2, "name": "Wireless Mouse", "category": "Electronics", "price_min": 20, "price_max": 50},
    {"id_start": 3, "name": "Mechanical Keyboard", "category": "Electronics", "price_min": 70, "price_max": 200},
    {"id_start": 4, "name": "4K UHD Monitor 27\"", "category": "Electronics", "price_min": 250, "price_max": 500},
    {"id_start": 5, "name": "USB-C Hub", "category": "Accessories", "price_min": 30, "price_max": 80},
    {"id_start": 6, "name": "Office Chair Ergonomic", "category": "Furniture", "price_min": 150, "price_max": 400},
    {"id_start": 7, "name": "Standing Desk (Electric)", "category": "Furniture", "price_min": 300, "price_max": 700},
    {"id_start": 8, "name": "Python Programming Book", "category": "Books", "price_min": 25, "price_max": 70},
    {"id_start": 9, "name": "Cloud Computing Textbook", "category": "Books", "price_min": 40, "price_max": 90},
    {"id_start": 10, "name": "Noise Cancelling Headphones", "category": "Electronics", "price_min": 100, "price_max": 350},
    {"id_start": 11, "name": "Webcam HD 1080p", "category": "Electronics", "price_min": 40, "price_max": 120},
    {"id_start": 12, "name": "Smartphone X", "category": "Electronics", "price_min": 600, "price_max": 1200},
    {"id_start": 13, "name": "Tablet S", "category": "Electronics", "price_min": 300, "price_max": 800},
    {"id_start": 14, "name": "Printer All-in-One", "category": "Office Supplies", "price_min": 80, "price_max": 250},
    {"id_start": 15, "name": "A4 Printing Paper (Ream)", "category": "Office Supplies", "price_min": 5, "price_max": 15},
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_sales"
RECORDS_PER_FILE = 500
YEARS = [2021, 2022, 2023, 2024, 2025]

def generate_random_date(year):
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + datetime.timedelta(days=random_number_of_days)
    return random_date.strftime("%Y-%m-%d")

def generate_sales_record(sale_id_counter, year):
    product_data = random.choice(PRODUCTS)
    product_id = product_data["id_start"] # Simple Product ID mapping
    product_name = product_data["name"]
    category = product_data["category"]
    
    quantity_sold = random.randint(1, 10)
    price_per_unit = round(random.uniform(product_data["price_min"], product_data["price_max"]), 2)
    total_amount = round(quantity_sold * price_per_unit, 2)
    sale_date = generate_random_date(year)
    
    return [
        sale_id_counter,
        product_id,
        product_name,
        category,
        quantity_sold,
        price_per_unit,
        total_amount,
        sale_date
    ]

def main():
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
        print(f"Created directory: {OUTPUT_DIR}")

    headers = ["SaleID", "ProductID", "ProductName", "Category", "QuantitySold", "PricePerUnit", "TotalAmount", "SaleDate"]
    
    for year in YEARS:
        file_path = OUTPUT_DIR / f"sample_sales_{year}.csv"
        sale_id_counter = 1 # Reset counter for each file/year
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for _ in range(RECORDS_PER_FILE):
                record = generate_sales_record(sale_id_counter, year)
                writer.writerow(record)
                sale_id_counter += 1
        print(f"Generated {RECORDS_PER_FILE} records for {year} at {file_path}")

    print("Sample data generation complete.")

if __name__ == "__main__":
    main() 