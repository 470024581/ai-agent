#!/usr/bin/env python3
"""
Database Initialization Script for Smart  Agent

This script initializes the SQLite database and imports data from CSV files.
Run this script to set up or reset the database.

Usage:
    python scripts/init_database.py
"""

import sys
import os
from pathlib import Path

# Adjust import path to access app.db
# Assuming scripts/ is at the same level as app/
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db import (
    initialize_database_schema,
    import_csv_data_to_db,
    check_database_exists,
    DATABASE_PATH,
    PRODUCTS_CSV,
    INVENTORY_CSV,
    SALES_CSV
)

def main():
    """Main function to initialize the database."""
    print("=" * 60)
    print("Smart  Agent - Database Initialization")
    print("=" * 60)
    print()
    
    # Check if CSV files exist
    missing_files = []
    csv_files = [
        ("Products CSV", PRODUCTS_CSV),
        ("Inventory CSV", INVENTORY_CSV),
        ("Sales CSV", SALES_CSV)
    ]
    
    for name, filepath in csv_files:
        if not filepath.exists():
            missing_files.append(f"{name}: {filepath}")
    
    if missing_files:
        print("ERROR: Missing CSV data files:")
        for missing in missing_files:
            print(f"  - {missing}")
        print()
        print("Please ensure all CSV files are present in the data/ directory.")
        return 1
    
    print("✓ All required CSV files found")
    print(f"✓ Database will be created at: {DATABASE_PATH}")
    print()
    
    # Check if database already exists
    if DATABASE_PATH.exists():
        print("⚠️  Database already exists!")
        response = input("Do you want to recreate the database? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Database initialization cancelled.")
            return 0
        print()
    
    try:
        # Initialize schema
        print("Initializing database schema...")
        initialize_database_schema()
        print("✓ Database schema created successfully")
        
        # Import data from CSV
        print("Importing data from CSV files...")
        import_csv_data_to_db()
        print("✓ Data import completed successfully")
        
        # Verify the import
        print("Verifying database...")
        if check_database_exists():
            print("✓ Database verification successful")
            print()
            print("=" * 60)
            print("Database initialization completed successfully!")
            print("=" * 60)
            print()
            print("You can now start the FastAPI server with:")
            # Adjusted instruction for starting the server from root
            print("  python start.py") 
            print()
            return 0
        else:
            print("❌ Database verification failed")
            return 1
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 