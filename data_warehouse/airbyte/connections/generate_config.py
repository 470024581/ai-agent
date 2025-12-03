#!/usr/bin/env python3
"""
Generate Airbyte Connection Configuration from Environment Variables
从环境变量生成 Airbyte 连接配置

This script reads environment variables and generates Airbyte source and destination
configuration JSON files.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def generate_source_config():
    """Generate Supabase PostgreSQL source configuration"""
    config = {
        "name": "Supabase Source",
        "sourceDefinitionId": "decd338e-5647-4c0b-adf4-da0e75f5d750",  # PostgreSQL source definition ID
        "connectionConfiguration": {
            "host": os.getenv('SUPABASE_DB_HOST', 'db.your-project.supabase.co'),
            "port": int(os.getenv('SUPABASE_DB_PORT', '5432')),
            "database": os.getenv('SUPABASE_DB_NAME', 'postgres'),
            "username": os.getenv('SUPABASE_DB_USER', 'postgres'),
            "password": os.getenv('SUPABASE_DB_PASSWORD', ''),
            "ssl": True,
            "ssl_mode": {
                "mode": "require"
            },
            "replication_method": {
                "method": "CDC",  # Change Data Capture for incremental sync
                "replication_slot": "airbyte_slot",
                "publication": "airbyte_publication"
            },
            "schemas": ["public"],
            "tunnel_method": {
                "tunnel_method": "NO_TUNNEL"
            }
        }
    }
    return config

def generate_destination_config():
    """Generate Databricks destination configuration"""
    config = {
        "name": "Databricks Destination",
        "destinationDefinitionId": "b4c4a739-5d5c-4b0b-9b3a-5c5c5c5c5c5c",  # Databricks destination definition ID
        "connectionConfiguration": {
            "databricks_server_hostname": os.getenv('DATABRICKS_SERVER_HOSTNAME', 'your-workspace.cloud.databricks.com'),
            "databricks_http_path": os.getenv('DATABRICKS_HTTP_PATH', '/sql/1.0/warehouses/your-warehouse-id'),
            "databricks_port": "443",
            "databricks_personal_access_token": os.getenv('DATABRICKS_TOKEN', ''),
            "database": os.getenv('DATABRICKS_DATABASE', 'hive_metastore'),
            "schema": os.getenv('DATABRICKS_SCHEMA', 'shanghai_transport')
        }
    }
    return config

def main():
    """Generate configuration files"""
    output_dir = Path(__file__).parent
    
    # Check required environment variables
    required_vars = {
        'source': ['SUPABASE_DB_HOST', 'SUPABASE_DB_NAME', 'SUPABASE_DB_USER', 'SUPABASE_DB_PASSWORD'],
        'destination': ['DATABRICKS_SERVER_HOSTNAME', 'DATABRICKS_HTTP_PATH', 'DATABRICKS_TOKEN']
    }
    
    missing_vars = []
    for var in required_vars['source']:
        if not os.getenv(var):
            missing_vars.append(var)
    for var in required_vars['destination']:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file")
        return 1
    
    # Generate source configuration
    source_config = generate_source_config()
    source_file = output_dir / 'supabase_source.json'
    with open(source_file, 'w', encoding='utf-8') as f:
        json.dump(source_config, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated source configuration: {source_file}")
    
    # Generate destination configuration
    dest_config = generate_destination_config()
    dest_file = output_dir / 'databricks_destination.json'
    with open(dest_file, 'w', encoding='utf-8') as f:
        json.dump(dest_config, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated destination configuration: {dest_file}")
    
    print("\nNote: These JSON files are templates. You'll need to:")
    print("1. Create Source and Destination in Airbyte Cloud UI")
    print("2. Use these configurations as reference when filling in the forms")
    print("3. Or use Airbyte API to create connections programmatically")
    
    return 0

if __name__ == '__main__':
    exit(main())


