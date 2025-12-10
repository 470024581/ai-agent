#!/usr/bin/env python3
"""
Fetch UUIDs from Preset API and update dashboard configuration files
从Preset API获取UUID并更新dashboard配置文件
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Optional

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✅ Loaded environment variables from {env_path}")
else:
    print(f"⚠️  Warning: .env file not found at {env_path}")
    print("   Trying to load from process environment...")

# Get configuration from environment
PRESET_API = os.getenv("PRESET_API")
PRESET_TOKEN = os.getenv("PRESET_TOKEN")
PRESET_SECRET = os.getenv("PRESET_SECRET")
WORKSPACE = "BI_Report"

# Validate configuration
if not PRESET_API:
    print("❌ Error: PRESET_API not found in environment variables")
    sys.exit(1)

if not PRESET_TOKEN:
    print("❌ Error: PRESET_TOKEN not found in environment variables")
    sys.exit(1)

if not PRESET_SECRET:
    print("❌ Error: PRESET_SECRET not found in environment variables")
    sys.exit(1)

print(f"\n📋 Configuration:")
print(f"   API Base: {PRESET_API}")
print(f"   Workspace: {WORKSPACE}")
print(f"   Token: {PRESET_TOKEN[:20]}...")
print(f"   Secret: {PRESET_SECRET[:20]}...")

# API base URL
API_BASE = f"{PRESET_API.rstrip('/')}/api/v1"

# Request headers - Try different authentication methods
# Preset API may require different auth formats
HEADERS = {
    "Authorization": f"Bearer {PRESET_TOKEN}:{PRESET_SECRET}",
    "X-Preset-Workspace-Name": WORKSPACE,
    "Content-Type": "application/json"
}

# Alternative headers if above doesn't work
HEADERS_ALT1 = {
    "Authorization": f"Token {PRESET_TOKEN}",
    "X-Preset-Workspace-Name": WORKSPACE,
    "X-Preset-Secret": PRESET_SECRET,
    "Content-Type": "application/json"
}

HEADERS_ALT2 = {
    "Authorization": f"Bearer {PRESET_TOKEN}",
    "X-Preset-Workspace-Name": WORKSPACE,
    "X-Preset-Api-Secret": PRESET_SECRET,
    "Content-Type": "application/json"
}

def fetch_database_uuid() -> Optional[str]:
    """Fetch databricks database UUID from Preset API"""
    print(f"\n🔍 Fetching database UUID for 'databricks'...")
    
    # Try different URL formats
    urls_to_try = [
        f"{API_BASE}/database/",
        f"{API_BASE}/database",
        f"{API_BASE}/database?q=(filters:!((col:database_name,opr:eq,value:databricks)))",
    ]
    
    headers_list = [
        ("Bearer TOKEN:SECRET", HEADERS),
        ("Token + X-Preset-Secret", HEADERS_ALT1),
        ("Bearer + X-Preset-Api-Secret", HEADERS_ALT2),
    ]
    
    for url in urls_to_try:
        for method_name, headers in headers_list:
            try:
                print(f"   Trying: {url} with {method_name}...")
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    print(f"   ✅ Authentication successful with {method_name}")
                    data = response.json()
                    databases = data.get("result", [])
                    
                    for db in databases:
                        if db.get("database_name") == "databricks":
                            uuid = db.get("uuid")
                            print(f"   ✅ Found database 'databricks': {uuid}")
                            return uuid
                    
                    print(f"   ⚠️  Database 'databricks' not found")
                    print(f"   Available databases: {[db.get('database_name') for db in databases]}")
                    return None
                else:
                    print(f"   ❌ Status {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Error with {method_name}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response: {e.response.text[:200]}")
                continue
    
    print(f"   ❌ All authentication methods failed")
    return None

def fetch_dataset_uuids() -> Dict[str, Dict[str, str]]:
    """Fetch UUIDs for all 5 datasets from Preset API"""
    print(f"\n🔍 Fetching dataset UUIDs for marts schema...")
    
    datasets_to_find = [
        "daily_active_users",
        "daily_topup_summary",
        "route_usage_summary",
        "station_flow_daily",
        "user_card_type_summary"
    ]
    
    # Try different URL formats
    urls_to_try = [
        f"{API_BASE}/dataset/",
        f"{API_BASE}/dataset",
        f"{API_BASE}/dataset?q=(filters:!((col:schema,opr:eq,value:marts)))",
    ]
    
    headers_list = [
        ("Bearer TOKEN:SECRET", HEADERS),
        ("Token + X-Preset-Secret", HEADERS_ALT1),
        ("Bearer + X-Preset-Api-Secret", HEADERS_ALT2),
    ]
    
    for url in urls_to_try:
        for method_name, headers in headers_list:
            try:
                print(f"   Trying: {url} with {method_name}...")
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    print(f"   ✅ Authentication successful with {method_name}")
                    data = response.json()
                    all_datasets = data.get("result", [])
                    
                    # Filter datasets by database_name=databricks and schema=marts
                    marts_datasets = [
                        ds for ds in all_datasets
                        if ds.get("database", {}).get("database_name") == "databricks"
                        and ds.get("schema") == "marts"
                    ]
                    
                    print(f"   Found {len(marts_datasets)} datasets in marts schema")
                    
                    result = {}
                    for table_name in datasets_to_find:
                        found = False
                        for ds in marts_datasets:
                            if ds.get("table_name") == table_name:
                                result[table_name] = {
                                    "uuid": ds.get("uuid"),
                                    "id": str(ds.get("id", "")),
                                    "table_name": table_name
                                }
                                print(f"   ✅ Found dataset '{table_name}': {ds.get('uuid')} (id: {ds.get('id')})")
                                found = True
                                break
                        
                        if not found:
                            print(f"   ❌ Dataset '{table_name}' not found")
                    
                    return result
                else:
                    print(f"   ❌ Status {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Error with {method_name}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response: {e.response.text[:200]}")
                continue
    
    print(f"   ❌ All authentication methods failed")
    return {}

def main():
    """Main function to fetch UUIDs"""
    print("=" * 60)
    print("Preset UUID Fetcher")
    print("=" * 60)
    
    # Fetch database UUID
    db_uuid = fetch_database_uuid()
    
    # Fetch dataset UUIDs
    dataset_uuids = fetch_dataset_uuids()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print("=" * 60)
    
    if db_uuid:
        print(f"✅ Database UUID: {db_uuid}")
    else:
        print("❌ Database UUID: Not found")
    
    print(f"\n📦 Datasets found: {len(dataset_uuids)}/5")
    for table_name, info in dataset_uuids.items():
        print(f"   ✅ {table_name}: {info['uuid']}")
    
    # Save results to JSON file for next step
    results = {
        "database_uuid": db_uuid,
        "datasets": dataset_uuids
    }
    
    output_file = Path(__file__).parent / "preset_uuids.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    if db_uuid and len(dataset_uuids) == 5:
        print("\n✅ All UUIDs fetched successfully! Ready for next step.")
        return 0
    else:
        print("\n⚠️  Some UUIDs are missing. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

