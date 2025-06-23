import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import csv
import json
# Import DataSourceType to check the type of datasource being deleted
from .models import DataSourceType # Ensure this is imported

# Database configuration - Updated for root directory structure
DATABASE_DIR = Path(__file__).resolve().parent.parent / "data" # Adjusted for app/db.py
DATABASE_PATH = DATABASE_DIR / "smart.db"
CSV_DATA_DIR = DATABASE_DIR

# CSV files paths
PRODUCTS_CSV = CSV_DATA_DIR / "products_data.csv"
INVENTORY_CSV = CSV_DATA_DIR / "inventory_data.csv"
SALES_CSV = CSV_DATA_DIR / "sales_data.csv"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
SHORT_DATE_FORMAT = "%Y-%m-%d"

# Define UPLOAD_DIR at the module level if it's not already defined
# This is needed for deleting physical files.
# Ensure UPLOAD_DIR is correctly pointing to server/data/uploads/
if 'UPLOAD_DIR' not in globals():
    UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"

def get_db_connection():
    """Get a database connection."""
    # Ensure the data directory exists when first connecting
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def initialize_database_schema():
    """Initialize the database schema with all necessary tables."""
    print(f"[DB-SQLite] Initializing database schema at: {DATABASE_PATH}")
    
    conn = get_db_connection() # Ensures directory exists
    cursor = conn.cursor()
    
    try:
        # Create products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            )
        ''')
        
        # Create inventory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,
                stock_level INTEGER NOT NULL,
                last_updated DATETIME NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        # Create sales table
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
        
        # Create datasources table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datasources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                type TEXT NOT NULL DEFAULT 'knowledge_base',
                is_active BOOLEAN NOT NULL DEFAULT 0,
                file_count INTEGER NOT NULL DEFAULT 0,
                db_table_name TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                datasource_id INTEGER NOT NULL,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                processed_chunks INTEGER DEFAULT 0,
                error_message TEXT,
                uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at DATETIME,
                FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE
            )
        ''')
        
        # Create vector_chunks table for RAG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vector_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
            )
        ''')
        
        # Create datasource_tables table to support multiple tables per datasource
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datasource_tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datasource_id INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE,
                UNIQUE(datasource_id, table_name)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_datasource_id ON files(datasource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vector_chunks_file_id ON vector_chunks(file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasources_is_active ON datasources(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasource_tables_datasource_id ON datasource_tables(datasource_id)')
        
        # Insert default  datasource if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO datasources (id, name, description, type, is_active, file_count)
            VALUES (1, 'Default ', 'Default  system data (products, inventory, sales)', 'default', 1, 0)
        ''')
        
        conn.commit()
        print("[DB-SQLite] Database schema initialized successfully")
        
    except Exception as e:
        print(f"[DB-SQLite] Error initializing database schema: {e}")
        conn.rollback()
    finally:
        conn.close()

def import_csv_data_to_db():
    """Import data from CSV files into SQLite database."""
    print("[DB-SQLite] Starting CSV data import...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute("DELETE FROM sales")
        cursor.execute("DELETE FROM inventory")
        cursor.execute("DELETE FROM products")
        
        # Import products data
        if PRODUCTS_CSV.exists():
            print(f"[DB-SQLite] Importing products from {PRODUCTS_CSV}")
            with open(PRODUCTS_CSV, 'r', encoding='utf-8-sig') as csvfile:  # utf-8-sig handles BOM
                reader = csv.DictReader(csvfile)
                product_count = 0
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Debug: print first few rows
                        if row_num <= 3:
                            print(f"[DEBUG] Row {row_num}: {dict(row)}")
                        
                        # Clean up any extra None keys (CSV parsing artifacts)
                        clean_row = {k: v for k, v in row.items() if k is not None and v is not None}
                        
                        # Validate required fields
                        required_fields = ['product_id', 'product_name', 'category', 'unit_price']
                        if not all(field in clean_row for field in required_fields):
                            print(f"[DB-SQLite] Missing required fields in product row {row_num}: {clean_row}")
                            continue
                            
                        cursor.execute('''
                            INSERT INTO products (product_id, product_name, category, unit_price)
                            VALUES (?, ?, ?, ?)
                        ''', (clean_row['product_id'], clean_row['product_name'], 
                              clean_row['category'], float(clean_row['unit_price'])))
                        product_count += 1
                    except (ValueError, KeyError) as e:
                        print(f"[DB-SQLite] Error processing product row {row_num}: {e}. Data: {dict(row)}")
                        continue
            print(f"[DB-SQLite] Imported {product_count} products")
        
        # Import inventory data
        if INVENTORY_CSV.exists():
            print(f"[DB-SQLite] Importing inventory from {INVENTORY_CSV}")
            with open(INVENTORY_CSV, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                inventory_count = 0
                for row_num, row in enumerate(reader, 1):
                    try:
                        cursor.execute('''
                            INSERT INTO inventory (product_id, stock_level, last_updated)
                            VALUES (?, ?, ?)
                        ''', (row['product_id'], int(row['stock_level']), row['last_updated']))
                        inventory_count += 1
                    except (ValueError, KeyError) as e:
                        print(f"[DB-SQLite] Error processing inventory row {row_num}: {e}. Data: {dict(row)}")
                        continue
            print(f"[DB-SQLite] Imported {inventory_count} inventory records")
        
        # Import sales data
        if SALES_CSV.exists():
            print(f"[DB-SQLite] Importing sales from {SALES_CSV}")
            with open(SALES_CSV, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                sales_count = 0
                for row_num, row in enumerate(reader, 1):
                    try:
                        cursor.execute('''
                            INSERT INTO sales (sale_id, product_id, product_name, quantity_sold, 
                                             price_per_unit, total_amount, sale_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (row['sale_id'], row['product_id'], row['product_name'], 
                              int(row['quantity_sold']), float(row['price_per_unit']), 
                              float(row['total_amount']), row['sale_date']))
                        sales_count += 1
                    except (ValueError, KeyError) as e:
                        print(f"[DB-SQLite] Error processing sales row {row_num}: {e}. Data: {dict(row)}")
                        continue
            print(f"[DB-SQLite] Imported {sales_count} sales records")
        
        conn.commit()
        print("[DB-SQLite] CSV data import completed successfully")
        
    except Exception as e:
        print(f"[DB-SQLite] Error importing CSV data: {e}")
        conn.rollback()
    finally:
        conn.close()

def check_database_exists() -> bool:
    """Check if database exists and has data."""
    if not DATABASE_PATH.exists():
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if tables exist and have data
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventory")
        inventory_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        print(f"[DB-SQLite] Database contains: {products_count} products, {inventory_count} inventory records, {sales_count} sales records")
        
        return products_count > 0 and inventory_count > 0 and sales_count > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error checking database: {e}")
        return False
    finally:
        conn.close()

# ================== Data Source Management Functions ==================

async def get_datasources() -> List[Dict[str, Any]]:
    """Fetch a list of all data sources"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, name, description, type, is_active, file_count, 
                   db_table_name, created_at, updated_at 
            FROM datasources 
            ORDER BY is_active DESC, created_at ASC
        ''')
        rows = cursor.fetchall()
        
        datasources = []
        for row in rows:
            datasources.append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'type': row['type'],
                'is_active': bool(row['is_active']),
                'file_count': row['file_count'],
                'db_table_name': row['db_table_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        return datasources
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching datasources: {e}")
        return []
    finally:
        conn.close()

async def get_datasource(datasource_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a specific data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, name, description, type, is_active, file_count, 
                   db_table_name, created_at, updated_at 
            FROM datasources 
            WHERE id = ?
        ''', (datasource_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'type': row['type'],
                'is_active': bool(row['is_active']),
                'file_count': row['file_count'],
                'db_table_name': row['db_table_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching datasource {datasource_id}: {e}")
        return None
    finally:
        conn.close()

async def create_datasource(name: str, description: str = None, ds_type: str = "knowledge_base", db_table_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # For SQL_TABLE_FROM_FILE type, db_table_name can initially be None, filled later during file processing
        # But if provided at call time, use it
        cursor.execute('''
            INSERT INTO datasources (name, description, type, db_table_name, is_active, file_count)
            VALUES (?, ?, ?, ?, 0, 0)
        ''', (name, description, ds_type, db_table_name))
        
        datasource_id = cursor.lastrowid
        conn.commit()
        
        return await get_datasource(datasource_id)
        
    except sqlite3.IntegrityError:
        print(f"[DB-SQLite] Datasource with name '{name}' already exists")
        return None
    except Exception as e:
        print(f"[DB-SQLite] Error creating datasource: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def update_datasource(datasource_id: int, name: str = None, description: str = None) -> Optional[Dict[str, Any]]:
    """Update data source information"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(datasource_id)
            
            query = f"UPDATE datasources SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        return await get_datasource(datasource_id)
        
    except sqlite3.IntegrityError:
        print(f"[DB-SQLite] Datasource name already exists")
        return None
    except Exception as e:
        print(f"[DB-SQLite] Error updating datasource: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def delete_datasource(datasource_id: int) -> bool:
    """Delete a data source and clean up associated dynamic SQL tables (if applicable)"""
    if datasource_id == 1:  # Default data source cannot be deleted
        print("[DB-SQLite] Cannot delete default datasource (ID: 1)")
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First get the data source details, especially type and db_table_name
        cursor.execute("SELECT type, db_table_name, is_active FROM datasources WHERE id = ?", (datasource_id,))
        ds_to_delete = cursor.fetchone()
        
        if not ds_to_delete:
            print(f"[DB-SQLite] Datasource with ID {datasource_id} not found for deletion.")
            return False
        
        ds_type = ds_to_delete['type']
        db_table_name_to_drop = ds_to_delete['db_table_name']
        was_active = ds_to_delete['is_active']
        
        # If it's SQL_TABLE_FROM_FILE type and has associated table, drop the table first
        if ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value and db_table_name_to_drop:
            try:
                # Ensure table name is safe, although it comes from database, just in case
                # Usually SQLite table names with special characters are wrapped in double quotes, but we use them directly here
                # DROP TABLE IF EXISTS "{table_name}" syntax is safe
                drop_table_sql = f'DROP TABLE IF EXISTS "{db_table_name_to_drop}"'
                print(f"[DB-SQLite] Attempting to drop table: {drop_table_sql}")
                cursor.execute(drop_table_sql)
                print(f"[DB-SQLite] Successfully dropped table '{db_table_name_to_drop}' for datasource ID {datasource_id}.")
            except Exception as table_drop_error:
                # If table drop fails, log error but continue with datasource record deletion (table might not exist or permission issue)
                print(f"[DB-SQLite] Error dropping table '{db_table_name_to_drop}': {table_drop_error}. Proceeding with datasource record deletion.")

        # Delete datasource record (will cascade delete related files and chunks)
        cursor.execute("DELETE FROM datasources WHERE id = ?", (datasource_id,))
        print(f"[DB-SQLite] Deleted datasource record with ID {datasource_id}.")
        
        # If deleted datasource was active, activate default datasource
        if was_active:
            cursor.execute("UPDATE datasources SET is_active = 1 WHERE id = 1")
            print("[DB-SQLite] Reactivated default datasource (ID: 1) as the deleted one was active.")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"[DB-SQLite] Error deleting datasource ID {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def set_active_datasource(datasource_id: int) -> bool:
    """Set the active data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if datasource exists
        cursor.execute("SELECT id FROM datasources WHERE id = ?", (datasource_id,))
        if not cursor.fetchone():
            return False
        
        # Deactivate all datasources
        cursor.execute("UPDATE datasources SET is_active = 0")
        
        # Activate specified datasource
        cursor.execute("UPDATE datasources SET is_active = 1 WHERE id = ?", (datasource_id,))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"[DB-SQLite] Error setting active datasource: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def get_active_datasource() -> Optional[Dict[str, Any]]:
    """Fetch the currently active data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, name, description, type, is_active, file_count, 
                   db_table_name, created_at, updated_at 
            FROM datasources 
            WHERE is_active = 1
            LIMIT 1
        ''')
        row = cursor.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'type': row['type'],
                'is_active': bool(row['is_active']),
                'file_count': row['file_count'],
                'db_table_name': row['db_table_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching active datasource: {e}")
        return None
    finally:
        conn.close()

async def set_datasource_table_name(datasource_id: int, db_table_name: str) -> bool:
    """Set or update the database table name associated with a data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE datasources
            SET db_table_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (db_table_name, datasource_id))
        conn.commit()
        return cursor.rowcount > 0 # True if a row was updated
    except Exception as e:
        print(f"[DB-SQLite] Error setting db_table_name for datasource {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def add_table_to_datasource(datasource_id: int, table_name: str) -> bool:
    """Add a table to a datasource (supports multiple tables per datasource)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Insert into datasource_tables
        cursor.execute('''
            INSERT OR IGNORE INTO datasource_tables (datasource_id, table_name)
            VALUES (?, ?)
        ''', (datasource_id, table_name))
        
        # Also update the main table name field for backward compatibility
        # (Use the first/latest table as the primary table)
        cursor.execute('''
            UPDATE datasources 
            SET db_table_name = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (table_name, datasource_id))
        
        conn.commit()
        
        print(f"[DB-SQLite] Successfully added table '{table_name}' to datasource {datasource_id}")
        return True
        
    except Exception as e:
        print(f"[DB-SQLite] Error adding table to datasource: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def get_datasource_tables(datasource_id: int) -> List[str]:
    """Get all tables associated with a datasource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT table_name FROM datasource_tables 
            WHERE datasource_id = ?
            ORDER BY created_at ASC
        ''', (datasource_id,))
        
        rows = cursor.fetchall()
        tables = [row[0] for row in rows]
        
        # If no tables in the new system, check the old db_table_name field
        if not tables:
            cursor.execute('SELECT db_table_name FROM datasources WHERE id = ?', (datasource_id,))
            row = cursor.fetchone()
            if row and row[0]:
                tables = [row[0]]
        
        return tables
        
    except Exception as e:
        print(f"[DB-SQLite] Error getting datasource tables: {e}")
        return []
    finally:
        conn.close()

async def get_datasource_schema_info(datasource_id: int) -> Dict[str, List[Dict]]:
    """Get schema information for all tables in a datasource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        tables = await get_datasource_tables(datasource_id)
        schema_info = {}
        
        for table_name in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            schema_info[table_name] = []
            for col in columns:
                schema_info[table_name].append({
                    'name': col[1],
                    'type': col[2],
                    'not_null': bool(col[3]),
                    'default_value': col[4],
                    'primary_key': bool(col[5])
                })
        
        return schema_info
        
    except Exception as e:
        print(f"[DB-SQLite] Error getting datasource schema info: {e}")
        return {}
    finally:
        conn.close()

# ================== File Management Functions ==================

async def save_file_info(filename: str, original_filename: str, file_type: str, 
                        file_size: int, datasource_id: int) -> Optional[int]:
    """Save file information to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO files (filename, original_filename, file_type, file_size, 
                              datasource_id, processing_status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (filename, original_filename, file_type, file_size, datasource_id))
        
        file_id = cursor.lastrowid
        
        # Update datasource file count
        cursor.execute('''
            UPDATE datasources 
            SET file_count = file_count + 1, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (datasource_id,))
        
        conn.commit()
        return file_id
        
    except Exception as e:
        print(f"[DB-SQLite] Error saving file info: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def get_files_by_datasource(datasource_id: int) -> List[Dict[str, Any]]:
    """Fetch all files for a specific data source"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, filename, original_filename, file_type, file_size, 
                   datasource_id, processing_status, processed_chunks, 
                   error_message, uploaded_at, processed_at
            FROM files 
            WHERE datasource_id = ?
            ORDER BY uploaded_at DESC
        ''', (datasource_id,))
        rows = cursor.fetchall()
        
        files = []
        for row in rows:
            files.append({
                'id': row['id'],
                'filename': row['filename'],
                'original_filename': row['original_filename'],
                'file_type': row['file_type'],
                'file_size': row['file_size'],
                'datasource_id': row['datasource_id'],
                'processing_status': row['processing_status'],
                'processed_chunks': row['processed_chunks'],
                'error_message': row['error_message'],
                'uploaded_at': row['uploaded_at'],
                'processed_at': row['processed_at']
            })
        
        return files
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching files: {e}")
        return []
    finally:
        conn.close()

async def update_file_processing_status(file_id: int, status: str, chunks: int = None, 
                                      error_message: str = None) -> bool:
    """Update file processing status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        params = [status]
        updates = ["processing_status = ?"]
        
        if chunks is not None:
            updates.append("processed_chunks = ?")
            params.append(chunks)
        
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        
        if status == "completed":
            updates.append("processed_at = CURRENT_TIMESTAMP")
        
        params.append(file_id)
        
        query = f"UPDATE files SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f"[DB-SQLite] Error updating file status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def delete_file_record_and_associated_data(file_id: int) -> bool:
    """Delete a file record and its associated data (including physical file and possible dynamic SQL table)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Get file information (filename, datasource_id)
        cursor.execute("SELECT filename, datasource_id FROM files WHERE id = ?", (file_id,))
        file_info = cursor.fetchone()
        if not file_info:
            print(f"[DB-SQLite] File with ID {file_id} not found. Cannot delete.")
            return False
        
        stored_filename = file_info['filename']
        datasource_id = file_info['datasource_id']

        # 2. Get datasource information (type, db_table_name, file_count)
        cursor.execute("SELECT type, db_table_name, file_count FROM datasources WHERE id = ?", (datasource_id,))
        ds_info = cursor.fetchone()
        if not ds_info:
            # This case should ideally not happen if file_info was found due to foreign key, but good practice.
            print(f"[DB-SQLite] Associated datasource ID {datasource_id} for file ID {file_id} not found. Inconsistent data?")
            # Proceed to delete file record and physical file, but log this anomaly.
            ds_type = None
            db_table_name_to_check = None
            current_file_count = 0 # Assume 0 if datasource missing, to avoid issues
        else:
            ds_type = ds_info['type']
            db_table_name_to_check = ds_info['db_table_name']
            current_file_count = ds_info['file_count']

        # 3. Delete physical file
        physical_file_path = UPLOAD_DIR / stored_filename
        if physical_file_path.exists():
            try:
                physical_file_path.unlink()
                print(f"[DB-SQLite] Successfully deleted physical file: {physical_file_path}")
            except Exception as e_phys_delete:
                print(f"[DB-SQLite] Error deleting physical file {physical_file_path}: {e_phys_delete}. Continuing with DB record deletion.")
        else:
            print(f"[DB-SQLite] Physical file not found, skipping deletion: {physical_file_path}")

        # 4. Delete file database record (files table) - vector_chunks will be cascade deleted
        cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
        if cursor.rowcount == 0:
            # Should not happen if file_info was fetched successfully, means record was deleted by another process
            print(f"[DB-SQLite] File record ID {file_id} was not found during deletion, possibly already deleted.")
            # If ds_info was fetched, we might still need to update its file_count if it wasn't already.
            # However, this state is ambiguous. For now, we'll assume if rowcount is 0, our job for this file is done.
            conn.rollback() # Rollback if no file record was deleted, as file_count update might be wrong
            return False # Indicate that the primary target (file record) wasn't deleted by this op.

        print(f"[DB-SQLite] Successfully deleted file record ID {file_id} from 'files' table.")

        # 5. Update datasource file_count and handle specific logic (e.g., SQL_TABLE_FROM_FILE)
        if ds_info: # Only proceed if datasource info was successfully fetched
            new_file_count = max(0, current_file_count - 1)
            
            if ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value:
                if new_file_count == 0 and db_table_name_to_check:
                    # This was the last file for this SQL table datasource, drop the table and clear db_table_name
                    try:
                        drop_table_sql = f'DROP TABLE IF EXISTS "{db_table_name_to_check}"'
                        print(f"[DB-SQLite] SQL_TABLE_FROM_FILE: Last file. Dropping table: {drop_table_sql}")
                        cursor.execute(drop_table_sql)
                        print(f"[DB-SQLite] Successfully dropped table '{db_table_name_to_check}'.")
                        # Clear db_table_name and update file_count
                        cursor.execute("UPDATE datasources SET file_count = ?, db_table_name = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                       (new_file_count, datasource_id))
                        print(f"[DB-SQLite] Datasource ID {datasource_id} updated: file_count={new_file_count}, db_table_name cleared.")
                    except Exception as e_drop_sql_table:
                        print(f"[DB-SQLite] Error dropping table '{db_table_name_to_check}': {e_drop_sql_table}. File count still updated.")
                        # Still update file_count even if table drop fails, but db_table_name remains (problematic state)
                        # Potentially log this as a critical issue for manual review
                        cursor.execute("UPDATE datasources SET file_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                       (new_file_count, datasource_id))
                else:
                    # Not the last file, or no db_table_name was set (e.g. still pending processing)
                    # Just update file_count
                    cursor.execute("UPDATE datasources SET file_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                   (new_file_count, datasource_id))
                    print(f"[DB-SQLite] Datasource ID {datasource_id} (SQL_TABLE_FROM_FILE) updated: file_count={new_file_count}.")
            else:
                # For other datasource types (default, knowledge_base, etc.)
                cursor.execute("UPDATE datasources SET file_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (new_file_count, datasource_id))
                print(f"[DB-SQLite] Datasource ID {datasource_id} (Type: {ds_type}) updated: file_count={new_file_count}.")
        
        conn.commit()
        return True

    except Exception as e:
        print(f"[DB-SQLite] Error deleting file ID {file_id} and associated data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ================== Original Data Query Functions ==================

async def fetch_all_products() -> List[Dict[str, Any]]:
    """Fetches all products from the database."""
    print("[DB-SQLite] Fetching all products")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM products ORDER BY product_id")
        rows = cursor.fetchall()
        
        products = []
        for row in rows:
            products.append({
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'category': row['category'],
                'unit_price': row['unit_price']
            })
        
        return products
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching products: {e}")
        return []
    finally:
        conn.close()

async def get_product_details(product_id: str) -> Optional[Dict[str, Any]]:
    """Fetches details for a specific product_id from the database."""
    print(f"[DB-SQLite] Fetching product details for: {product_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'category': row['category'],
                'unit_price': row['unit_price']
            }
        
        return None
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching product {product_id}: {e}")
        return None
    finally:
        conn.close()

async def fetch_sales_data_for_query(natural_language_query: str) -> List[Dict[str, Any]]:
    """Use LLM semantic analysis to retrieve sales data"""
    print(f"[DB-SQLite] Processing sales query with LLM: {natural_language_query}")
    
    # Import LLM (avoid circular import)
    try:
        from .llm_factory import llm
    except ImportError:
        from .agent import llm
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get database table structure
        cursor.execute("PRAGMA table_info(sales)")
        sales_schema = cursor.fetchall()
        cursor.execute("PRAGMA table_info(products)")
        products_schema = cursor.fetchall()
        
        schema_info = f"Sales table fields: {[col[1] for col in sales_schema]}, Products table fields: {[col[1] for col in products_schema]}"
        
        if llm:
            # Use LLM to generate SQL query
            sql_generation_prompt = f"""
            User query: "{natural_language_query}"
            
            Database table structure:
            - sales table: sale_id, product_id, product_name, quantity_sold, price_per_unit, total_amount, sale_date
            - products table: product_id, product_name, category, unit_price
            
            Please generate appropriate SQLite query statement to retrieve sales data. Requirements:
            1. Return only SQL statement, no other explanation
            2. Use sales table as main table, LEFT JOIN products table to get category information
            3. Add appropriate time and product filter conditions based on user query
            4. Database is SQLite, use SQLite syntax (e.g., date('now') instead of CURDATE())
            5. Fields may be TEXT type, need CAST conversion to numeric types for calculations
            6. Order by date in descending order
            7. Limit to within 50 records
            8. SQL statement must be complete and executable
            9. For trend queries, use strftime('%Y-%m', sale_date) to group by month
            
            SQL query statement:
            """
            
            try:
                response = llm.invoke(sql_generation_prompt)
                
                # Handle LLM response
                if hasattr(response, 'content'):
                    llm_sql = response.content
                elif isinstance(response, str):
                    llm_sql = response
                else:
                    llm_sql = str(response)
                
                # Clean SQL statement
                import re
                sql_match = re.search(r'SELECT.*?(?:;|$)', llm_sql, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group().rstrip(';').strip()
                else:
                    sql_query = llm_sql.strip().rstrip(';')
                
                print(f"[DB-SQLite] LLM generated SQL: {sql_query}")
                
            except Exception as llm_error:
                print(f"[DB-SQLite] LLM SQL generation failed: {llm_error}, using fallback")
                # Use simple fallback query
                sql_query = """
                    SELECT s.*, p.category 
                    FROM sales s
                    LEFT JOIN products p ON s.product_id = p.product_id
                    ORDER BY s.sale_date DESC
                    LIMIT 30
                """
        else:
            print("[DB-SQLite] LLM not available, using fallback query")
            sql_query = """
                SELECT s.*, p.category 
                FROM sales s
                LEFT JOIN products p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC
                LIMIT 30
            """
        
        # Execute SQL query
        print(f"[DB-SQLite] Executing query: {sql_query}")
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        sales_data = []
        for row in rows:
            sales_data.append({
                'sale_id': row['sale_id'],
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'quantity_sold': row['quantity_sold'],
                'price_per_unit': row['price_per_unit'],
                'total_amount': row['total_amount'],
                'sale_date': row['sale_date'],
                'category': dict(row).get('category', 'Unknown')
            })
        
        print(f"[DB-SQLite] Found {len(sales_data)} sales records")
        return sales_data
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching sales data: {e}")
        return []
    finally:
        conn.close()

async def fetch_low_stock_products(threshold: int = 50) -> List[Dict[str, Any]]:
    """Fetch products with stock levels below the specified threshold."""
    print(f"[DB-SQLite] Fetching products with stock below {threshold}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p.product_id, p.product_name, p.category, p.unit_price,
                   i.stock_level, i.last_updated
            FROM products p
            INNER JOIN inventory i ON p.product_id = i.product_id
            WHERE i.stock_level < ?
            ORDER BY i.stock_level ASC
        ''', (threshold,))
        
        rows = cursor.fetchall()
        
        low_stock_products = []
        for row in rows:
            low_stock_products.append({
                'product_id': row['product_id'], 
                'product_name': row['product_name'],
                'category': row['category'],
                'unit_price': row['unit_price'],
                'stock_level': row['stock_level'],
                'last_updated': row['last_updated']
            })
        
        print(f"[DB-SQLite] Found {len(low_stock_products)} low stock products")
        return low_stock_products
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching low stock products: {e}")
        return []
    finally:
        conn.close()

async def fetch_sales_for_day(target_date: datetime) -> List[Dict[str, Any]]:
    """Fetch sales data for a specific day."""
    date_str = target_date.strftime(SHORT_DATE_FORMAT)
    print(f"[DB-SQLite] Fetching sales for {date_str}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT s.*, p.category 
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.product_id
            WHERE DATE(s.sale_date) = ?
            ORDER BY s.sale_date DESC
        ''', (date_str,))
        
        rows = cursor.fetchall()
        
        sales_data = []
        for row in rows:
            sales_data.append({
                'sale_id': row['sale_id'], 
                'product_id': row['product_id'],
                'product_name': row['product_name'], 
                'quantity_sold': row['quantity_sold'], 
                'price_per_unit': row['price_per_unit'], 
                'total_amount': row['total_amount'],
                'sale_date': row['sale_date'],
                'category': row.get('category', 'Unknown')
            })
        
        print(f"[DB-SQLite] Found {len(sales_data)} sales for {date_str}")
        return sales_data
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching sales for {date_str}: {e}")
        return []
    finally:
        conn.close()

def initialize_database():
    """Initialize the application database (schema and initial data)."""
    print("[DB-SQLite] Initializing application database (schema and initial data)...")
    
    # Initialize schema
    initialize_database_schema()
    
    # Check if data exists
    if not check_database_exists():
        print("[DB-SQLite] No data found, importing from CSV files...")
        import_csv_data_to_db()
    else:
        print("[DB-SQLite] Database already contains data")
    
    print("[DB-SQLite] Application database initialization complete") 