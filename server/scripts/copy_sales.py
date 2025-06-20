#!/usr/bin/env python3
"""
Copy sales data from backend to new data directory

This script is intended to be run from the project root directory.
Example: python scripts/copy_sales.py
"""

import shutil
from pathlib import Path

def copy_sales_data():
    """Copy complete sales data."""
    # Source path might be from an old structure, assumes script is run from project root.
    source = Path("backend/data/sales_data.csv") 
    # Destination path is relative to project root.
    dest_dir = Path("data")
    dest_dir.mkdir(parents=True, exist_ok=True) # Ensure data directory exists
    dest_file = dest_dir / "sales_data.csv"
    
    if source.exists():
        shutil.copy2(source, dest_file)
        print(f"✓ Copied {source} to {dest_file}")
        
        # Verify
        try:
            with open(dest_file, 'r', encoding='utf-8-sig') as f: # Added encoding for robustness
                lines = f.readlines()
                print(f"✓ Sales data contains {len(lines)-1} records (plus header)")
        except Exception as e:
            print(f"⚠️  Could not verify copied file: {e}")
    else:
        print(f"❌ Source file {source} not found. This script might be outdated or needs adjustment if the 'backend' directory structure has changed.")

if __name__ == "__main__":
    copy_sales_data() 