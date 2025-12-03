#!/usr/bin/env python3
"""
Create Databricks Schemas for dbt Models
创建 Databricks Schemas 用于 dbt 模型

This script creates the required schemas in Databricks for dbt models.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from databricks import sql

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Databricks connection configuration
CONNECTION_CONFIG = {
    'server_hostname': os.getenv('DATABRICKS_SERVER_HOSTNAME'),
    'http_path': os.getenv('DATABRICKS_HTTP_PATH'),
    'access_token': os.getenv('DATABRICKS_TOKEN')
}

# Schemas to create
SCHEMAS = [
    'staging',
    'dimensions',
    'facts',
    'marts'
]

CATALOG = 'workspace'


def create_schemas():
    """Create schemas in Databricks"""
    # Validate configuration
    if not all([CONNECTION_CONFIG['server_hostname'], 
                CONNECTION_CONFIG['http_path'], 
                CONNECTION_CONFIG['access_token']]):
        print("Error: Missing required environment variables:")
        print("  - DATABRICKS_SERVER_HOSTNAME")
        print("  - DATABRICKS_HTTP_PATH")
        print("  - DATABRICKS_TOKEN")
        print("\nPlease set these in your .env file")
        return 1
    
    print("=" * 60)
    print("Creating Databricks Schemas for dbt Models")
    print("=" * 60)
    print(f"Catalog: {CATALOG}")
    print(f"Schemas to create: {', '.join(SCHEMAS)}")
    print("=" * 60)
    
    try:
        # Connect to Databricks
        with sql.connect(**CONNECTION_CONFIG) as conn:
            with conn.cursor() as cursor:
                # Create each schema
                for schema in SCHEMAS:
                    schema_name = f"{CATALOG}.{schema}"
                    print(f"\nCreating schema: {schema_name}...")
                    
                    try:
                        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
                        print(f"  ✓ Schema '{schema_name}' created successfully")
                    except Exception as e:
                        print(f"  ✗ Error creating schema '{schema_name}': {e}")
                        return 1
                
                # Verify schemas
                print("\n" + "=" * 60)
                print("Verifying schemas...")
                print("=" * 60)
                
                cursor.execute(f"SHOW SCHEMAS IN {CATALOG}")
                schemas = [row[0] for row in cursor.fetchall()]
                
                for schema in SCHEMAS:
                    if schema in schemas:
                        print(f"  ✓ {CATALOG}.{schema} exists")
                    else:
                        print(f"  ✗ {CATALOG}.{schema} not found")
                        return 1
                
                print("\n" + "=" * 60)
                print("✓ All schemas created successfully!")
                print("=" * 60)
                return 0
                
    except Exception as e:
        print(f"\nError connecting to Databricks: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify DATABRICKS_SERVER_HOSTNAME is correct")
        print("  2. Verify DATABRICKS_HTTP_PATH is correct")
        print("  3. Verify DATABRICKS_TOKEN is valid and not expired")
        print("  4. Ensure SQL Warehouse is running")
        return 1


if __name__ == '__main__':
    exit(create_schemas())

