#!/usr/bin/env python3
"""
Debug CSV import issues

This script is intended to be run from the project root directory.
Example: python scripts/debug_csv.py
"""

import csv
from pathlib import Path

def debug_csv_files():
    """Debug CSV file content and structure."""
    # Assumes script is run from project root, so 'data' is a subdirectory
    data_dir = Path("data")
    
    # Check products CSV
    products_csv = data_dir / "products_data.csv"
    if products_csv.exists():
        print(f"=== Checking {products_csv} ===")
        with open(products_csv, 'r', encoding='utf-8-sig') as f:
            # Read first few lines as text
            lines = f.readlines()[:5]
            for i, line in enumerate(lines):
                print(f"Line {i+1}: {repr(line)}")
        
        print("\n--- CSV Reader Test ---")
        with open(products_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            print(f"Fieldnames: {reader.fieldnames}")
            for i, row in enumerate(reader):
                if i < 3:
                    print(f"Row {i+1}: {dict(row)}")
                    # Test type conversion
                    try:
                        price = float(row['unit_price'])
                        print(f"  unit_price converted: {price}")
                    except (ValueError, KeyError) as e:
                        print(f"  ERROR converting unit_price: {e}")
                else:
                    break
    else:
        print(f"❌ {products_csv} not found")

if __name__ == "__main__":
    debug_csv_files() 