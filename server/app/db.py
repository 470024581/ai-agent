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
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_datasource_id ON files(datasource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vector_chunks_file_id ON vector_chunks(file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasources_is_active ON datasources(is_active)')
        
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
        # 对于 SQL_TABLE_FROM_FILE 类型，db_table_name 初始可以为 None，后续文件处理时填充
        # 但如果调用时提供了，就使用它
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
        # 首先获取数据源的详细信息，特别是 type 和 db_table_name
        cursor.execute("SELECT type, db_table_name, is_active FROM datasources WHERE id = ?", (datasource_id,))
        ds_to_delete = cursor.fetchone()
        
        if not ds_to_delete:
            print(f"[DB-SQLite] Datasource with ID {datasource_id} not found for deletion.")
            return False
        
        ds_type = ds_to_delete['type']
        db_table_name_to_drop = ds_to_delete['db_table_name']
        was_active = ds_to_delete['is_active']
        
        # 如果是 SQL_TABLE_FROM_FILE 类型且有关联的表，则先删除该表
        if ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value and db_table_name_to_drop:
            try:
                # 确保表名是安全的，尽管它来自数据库，但以防万一
                # 通常SQLite表名如果包含特殊字符会被双引号包围，但这里我们直接使用
                # DROP TABLE IF EXISTS "{table_name}" 语法是安全的
                drop_table_sql = f'DROP TABLE IF EXISTS "{db_table_name_to_drop}"'
                print(f"[DB-SQLite] Attempting to drop table: {drop_table_sql}")
                cursor.execute(drop_table_sql)
                print(f"[DB-SQLite] Successfully dropped table '{db_table_name_to_drop}' for datasource ID {datasource_id}.")
            except Exception as table_drop_error:
                # 如果删表失败，记录错误但继续删除数据源记录（可能表已不存在或权限问题）
                print(f"[DB-SQLite] Error dropping table '{db_table_name_to_drop}': {table_drop_error}. Proceeding with datasource record deletion.")

        # 删除数据源记录（会级联删除相关文件和chunks）
        cursor.execute("DELETE FROM datasources WHERE id = ?", (datasource_id,))
        print(f"[DB-SQLite] Deleted datasource record with ID {datasource_id}.")
        
        # 如果删除的是激活数据源，激活默认数据源
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
        # 检查数据源是否存在
        cursor.execute("SELECT id FROM datasources WHERE id = ?", (datasource_id,))
        if not cursor.fetchone():
            return False
        
        # 取消所有数据源的激活状态
        cursor.execute("UPDATE datasources SET is_active = 0")
        
        # 激活指定数据源
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
        
        # 更新数据源的文件计数
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
        # 1. 获取文件信息 (filename, datasource_id)
        cursor.execute("SELECT filename, datasource_id FROM files WHERE id = ?", (file_id,))
        file_info = cursor.fetchone()
        if not file_info:
            print(f"[DB-SQLite] File with ID {file_id} not found. Cannot delete.")
            return False
        
        stored_filename = file_info['filename']
        datasource_id = file_info['datasource_id']

        # 2. 获取数据源信息 (type, db_table_name, file_count)
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

        # 3. 删除物理文件
        physical_file_path = UPLOAD_DIR / stored_filename
        if physical_file_path.exists():
            try:
                physical_file_path.unlink()
                print(f"[DB-SQLite] Successfully deleted physical file: {physical_file_path}")
            except Exception as e_phys_delete:
                print(f"[DB-SQLite] Error deleting physical file {physical_file_path}: {e_phys_delete}. Continuing with DB record deletion.")
        else:
            print(f"[DB-SQLite] Physical file not found, skipping deletion: {physical_file_path}")

        # 4. 删除文件数据库记录 (files table) - vector_chunks will be cascade deleted
        cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
        if cursor.rowcount == 0:
            # Should not happen if file_info was fetched successfully, means record was deleted by another process
            print(f"[DB-SQLite] File record ID {file_id} was not found during deletion, possibly already deleted.")
            # If ds_info was fetched, we might still need to update its file_count if it wasn't already.
            # However, this state is ambiguous. For now, we'll assume if rowcount is 0, our job for this file is done.
            conn.rollback() # Rollback if no file record was deleted, as file_count update might be wrong
            return False # Indicate that the primary target (file record) wasn't deleted by this op.

        print(f"[DB-SQLite] Successfully deleted file record ID {file_id} from 'files' table.")

        # 5. 更新数据源的 file_count 及处理特定逻辑 (如 SQL_TABLE_FROM_FILE)
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
    """Fetch sales data based on natural language query interpretation."""
    print(f"[DB-SQLite] Processing sales query: {natural_language_query}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Parse the query to determine time range and other filters
        query_lower = natural_language_query.lower()
        
        # Determine date range
        if 'today' in query_lower:
            date_filter = "DATE(sale_date) = DATE('now')"
        elif 'yesterday' in query_lower:
            date_filter = "DATE(sale_date) = DATE('now', '-1 day')"
        elif 'this week' in query_lower:
            date_filter = "DATE(sale_date) >= DATE('now', 'weekday 0', '-7 days')"
        elif 'last week' in query_lower:
            date_filter = "DATE(sale_date) >= DATE('now', 'weekday 0', '-14 days') AND DATE(sale_date) < DATE('now', 'weekday 0', '-7 days')"
        elif 'this month' in query_lower:
            date_filter = "DATE(sale_date) >= DATE('now', 'start of month')"
        elif 'last month' in query_lower:
            date_filter = "DATE(sale_date) >= DATE('now', 'start of month', '-1 month') AND DATE(sale_date) < DATE('now', 'start of month')"
        elif any(term in query_lower for term in ['past 7 days', 'last 7 days']):
            date_filter = "DATE(sale_date) >= DATE('now', '-7 days')"
        elif any(term in query_lower for term in ['past 30 days', 'last 30 days']):
            date_filter = "DATE(sale_date) >= DATE('now', '-30 days')"
        else:
            # Default to last 30 days if no specific time range is mentioned
            date_filter = "DATE(sale_date) >= DATE('now', '-30 days')"
        
        # Base query
        base_query = f"""
            SELECT s.*, p.category 
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.product_id
            WHERE {date_filter}
        """
        
        # Check for specific product or category filters
        if any(term in query_lower for term in ['laptop', 'laptop pro']):
            base_query += " AND (LOWER(s.product_name) LIKE '%laptop%' OR LOWER(p.category) LIKE '%laptop%')"
        elif 'mouse' in query_lower:
            base_query += " AND (LOWER(s.product_name) LIKE '%mouse%' OR LOWER(p.category) LIKE '%mouse%')"
        elif 'keyboard' in query_lower:
            base_query += " AND (LOWER(s.product_name) LIKE '%keyboard%' OR LOWER(p.category) LIKE '%keyboard%')"
        elif 'monitor' in query_lower:
            base_query += " AND (LOWER(s.product_name) LIKE '%monitor%' OR LOWER(p.category) LIKE '%monitor%')"
        
        # Add ordering
        base_query += " ORDER BY s.sale_date DESC"
        
        print(f"[DB-SQLite] Executing query: {base_query}")
        cursor.execute(base_query)
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