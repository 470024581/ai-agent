import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import csv
import json
# Import DataSourceType to check the type of datasource being deleted
from ..models.data_models import DataSourceType # Updated import path

# Database configuration - Updated for new directory structure
DATABASE_DIR = Path(__file__).resolve().parent.parent.parent / "data" # Adjusted for src/database/db_operations.py
DATABASE_PATH = DATABASE_DIR / "smart.db"
CSV_DATA_DIR = DATABASE_DIR

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
SHORT_DATE_FORMAT = "%Y-%m-%d"

# Define UPLOAD_DIR at the module level if it's not already defined
# This is needed for deleting physical files.
# Ensure UPLOAD_DIR is correctly pointing to server/data/uploads/
if 'UPLOAD_DIR' not in globals():
    UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

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
        # Helper: ensure a column exists, if not then add it
        def ensure_column(table: str, column: str, add_sql: str):
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in cursor.fetchall()]
                if column not in cols:
                    cursor.execute(add_sql)
            except Exception as _e:
                print(f"[DB-SQLite] Warning ensuring column {table}.{column}: {_e}")

        # Create ERP business tables first
        # Customers table: Stores customer information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,           -- Customer unique identifier
                customer_name TEXT NOT NULL,            -- Customer company/person name
                contact_person TEXT,                    -- Primary contact person name
                phone TEXT,                             -- Contact phone number
                email TEXT,                             -- Contact email address
                address TEXT,                           -- Customer address
                customer_type TEXT NOT NULL DEFAULT 'regular', -- Customer type: VIP, regular, wholesale
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Customer registration date
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP  -- Last update timestamp
            )
        ''')

        # Backfill missing columns for legacy databases
        ensure_column("customers", "updated_at", "ALTER TABLE customers ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        
        # Products table: Stores product information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,            -- Product unique identifier
                product_name TEXT NOT NULL,             -- Product name
                category TEXT NOT NULL,                 -- Product category
                subcategory TEXT,                       -- Product subcategory
                unit_price REAL NOT NULL,               -- Unit price in currency
                cost_price REAL,                        -- Cost price for profit calculation
                description TEXT,                       -- Product description
                supplier TEXT,                          -- Product supplier
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Product creation date
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP  -- Last update timestamp
            )
        ''')
        
        # Orders table: Stores order information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,              -- Order unique identifier
                customer_id TEXT NOT NULL,              -- Customer ID (foreign key)
                order_date DATETIME NOT NULL,           -- Order placement date
                total_amount REAL NOT NULL,             -- Total order amount
                status TEXT NOT NULL DEFAULT 'pending', -- Order status: pending, confirmed, shipped, delivered, cancelled
                payment_method TEXT,                    -- Payment method: cash, card, transfer, etc.
                shipping_address TEXT,                 -- Shipping address
                notes TEXT,                             -- Order notes
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Order creation timestamp
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Last update timestamp
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            )
        ''')
        
        # Sales table: Stores sales transaction records (enhanced with order and customer links)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                sale_id TEXT PRIMARY KEY,               -- Sale unique identifier
                order_id TEXT,                          -- Order ID (foreign key)
                customer_id TEXT,                       -- Customer ID (foreign key)
                product_id TEXT NOT NULL,               -- Product ID (foreign key)
                product_name TEXT NOT NULL,             -- Product name (denormalized for performance)
                quantity_sold INTEGER NOT NULL,         -- Quantity sold
                price_per_unit REAL NOT NULL,           -- Price per unit at time of sale
                total_amount REAL NOT NULL,             -- Total amount for this sale line
                sale_date DATETIME NOT NULL,            -- Sale transaction date
                salesperson TEXT,                       -- Salesperson name
                discount_amount REAL DEFAULT 0,         -- Discount applied
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Sale creation timestamp
                FOREIGN KEY (order_id) REFERENCES orders (order_id),
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        # Inventory table: Stores current stock levels
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,            -- Product ID (foreign key)
                stock_level INTEGER NOT NULL DEFAULT 0, -- Current stock quantity
                min_stock_level INTEGER DEFAULT 10,     -- Minimum stock level for reorder
                max_stock_level INTEGER DEFAULT 1000,   -- Maximum stock level
                last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Last stock update
                last_restocked DATETIME,                -- Last restock date
                warehouse_location TEXT,                 -- Warehouse location
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

        # HITL tables (ensure create or backfill missing columns before creating indexes)
        
        # Create HITL tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitl_interrupts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL UNIQUE,
                user_input TEXT NOT NULL,
                datasource_id INTEGER,
                interrupt_node TEXT NOT NULL,
                interrupt_reason TEXT,
                state_data TEXT NOT NULL, -- JSON serialized complete state
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'interrupted', -- interrupted, resumed, cancelled
                FOREIGN KEY (datasource_id) REFERENCES datasources(id)
            )
        ''')

        # Backfill missing columns on legacy hitl_interrupts
        ensure_column("hitl_interrupts", "created_at", "ALTER TABLE hitl_interrupts ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("hitl_interrupts", "updated_at", "ALTER TABLE hitl_interrupts ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        ensure_column("hitl_interrupts", "status", "ALTER TABLE hitl_interrupts ADD COLUMN status TEXT NOT NULL DEFAULT 'interrupted'")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitl_parameter_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interrupt_id INTEGER NOT NULL,
                parameter_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                adjustment_reason TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interrupt_id) REFERENCES hitl_interrupts(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitl_execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                operation_type TEXT NOT NULL, -- pause, interrupt, resume, cancel
                node_name TEXT,
                parameters TEXT, -- JSON serialized parameters
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_action TEXT, -- user_initiated, system_initiated
                FOREIGN KEY (execution_id) REFERENCES hitl_interrupts(execution_id)
            )
        ''')
        
        # Create indexes for better performance (guarded)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_datasource_id ON files(datasource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vector_chunks_file_id ON vector_chunks(file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasources_is_active ON datasources(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasource_tables_datasource_id ON datasource_tables(datasource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_execution_id ON hitl_interrupts(execution_id)')
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_status ON hitl_interrupts(status)')
        except Exception as _e:
            print(f"[DB-SQLite] Warning creating index on hitl_interrupts.status: {_e}")
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_created_at ON hitl_interrupts(created_at)')
        except Exception as _e:
            print(f"[DB-SQLite] Warning creating index on hitl_interrupts.created_at: {_e}")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_parameter_adjustments_interrupt_id ON hitl_parameter_adjustments(interrupt_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_execution_history_execution_id ON hitl_execution_history(execution_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hitl_execution_history_timestamp ON hitl_execution_history(timestamp)')
        
        # Insert default datasource if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO datasources (id, name, description, type, is_active, file_count)
            VALUES (1, 'Default ERP System', 'Built-in ERP system with customers, products, orders, sales, and inventory data', 'default', 1, 0)
        ''')
        
        conn.commit()
        print("[DB-SQLite] Database schema initialized successfully")
        
    except Exception as e:
        print(f"[DB-SQLite] Error initializing database schema: {e}")
        conn.rollback()
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
        current_time = datetime.now().strftime(DATE_FORMAT)
        
        cursor.execute('''
            INSERT INTO datasources (name, description, type, db_table_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, ds_type, db_table_name, current_time, current_time))
        
        datasource_id = cursor.lastrowid
        conn.commit()
        
        # Return the created datasource
        return await get_datasource(datasource_id)
        
    except sqlite3.IntegrityError as e:
        print(f"[DB-SQLite] Integrity error creating datasource: {e}")
        return None
    except Exception as e:
        print(f"[DB-SQLite] Error creating datasource: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def update_datasource(datasource_id: int, name: str = None, description: str = None) -> Optional[Dict[str, Any]]:
    """Update a data source"""
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
            
        if not updates:
            return await get_datasource(datasource_id)
        
        updates.append("updated_at = ?")
        params.append(datetime.now().strftime(DATE_FORMAT))
        params.append(datasource_id)
        
        cursor.execute(f'''
            UPDATE datasources 
            SET {", ".join(updates)}
            WHERE id = ?
        ''', params)
        
        conn.commit()
        
        if cursor.rowcount > 0:
            return await get_datasource(datasource_id)
        return None
        
    except Exception as e:
        print(f"[DB-SQLite] Error updating datasource {datasource_id}: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def delete_datasource(datasource_id: int) -> bool:
    """Delete a data source and all its associated data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, get the datasource info before deletion to understand its type
        datasource = await get_datasource(datasource_id)
        if not datasource:
            print(f"[DB-SQLite] Datasource {datasource_id} not found for deletion")
            return False
        
        # Get all files associated with this datasource before deletion
        files = await get_files_by_datasource(datasource_id)
        
        # Delete physical files from the upload directory
        for file_info in files:
            file_path = UPLOAD_DIR / file_info['filename']
            try:
                if file_path.exists():
                    file_path.unlink()
                    print(f"[DB-SQLite] Deleted physical file: {file_path}")
            except Exception as e:
                print(f"[DB-SQLite] Error deleting physical file {file_path}: {e}")
        
        # Legacy support: if this was a SQL_TABLE_FROM_FILE datasource, drop its dynamic tables
        ds_type_str = str(datasource.get('type', '')).lower()
        if ds_type_str == 'sql_table_from_file':
            tables = await get_datasource_tables(datasource_id)
            for table_name in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    print(f"[DB-SQLite] Dropped table: {table_name}")
                except Exception as e:
                    print(f"[DB-SQLite] Error dropping table {table_name}: {e}")
        
        # Delete from datasources table (CASCADE will handle related records)
        cursor.execute('DELETE FROM datasources WHERE id = ?', (datasource_id,))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"[DB-SQLite] Successfully deleted datasource {datasource_id} and all associated data")
            return True
        else:
            print(f"[DB-SQLite] No datasource found with id {datasource_id}")
            return False
        
    except Exception as e:
        print(f"[DB-SQLite] Error deleting datasource {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def set_active_datasource(datasource_id: int) -> bool:
    """Set a data source as active (deactivate all others)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, deactivate all datasources
        cursor.execute('UPDATE datasources SET is_active = 0')
        
        # Then activate the specified one
        cursor.execute('UPDATE datasources SET is_active = 1 WHERE id = ?', (datasource_id,))
        
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error setting active datasource {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def get_active_datasource() -> Optional[Dict[str, Any]]:
    """Get the currently active data source"""
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
    """Set the table name for a datasource (used for SQL_TABLE_FROM_FILE type)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE datasources 
            SET db_table_name = ?, updated_at = ?
            WHERE id = ?
        ''', (db_table_name, datetime.now().strftime(DATE_FORMAT), datasource_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error setting table name for datasource {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def add_table_to_datasource(datasource_id: int, table_name: str) -> bool:
    """Add a table to a datasource and set it as the default table if none exists"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, check if this datasource already has a default table
        cursor.execute('SELECT db_table_name FROM datasources WHERE id = ?', (datasource_id,))
        row = cursor.fetchone()
        has_default_table = row['db_table_name'] is not None if row else False
        
        # Add the table to datasource_tables
        cursor.execute('''
            INSERT INTO datasource_tables (datasource_id, table_name)
            VALUES (?, ?)
        ''', (datasource_id, table_name))
        
        # If this is the first table, set it as the default table
        if not has_default_table:
            cursor.execute('''
                UPDATE datasources 
                SET db_table_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (table_name, datasource_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"[DB-SQLite] Error adding table {table_name} to datasource {datasource_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def get_datasource_tables(datasource_id: int) -> List[str]:
    """Get all table names associated with a datasource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT table_name 
            FROM datasource_tables 
            WHERE datasource_id = ?
            ORDER BY created_at ASC
        ''', (datasource_id,))
        rows = cursor.fetchall()
        
        return [row['table_name'] for row in rows]
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching tables for datasource {datasource_id}: {e}")
        return []
    finally:
        conn.close()

async def get_datasource_schema_info(datasource_id: int) -> Dict[str, List[Dict]]:
    """Get schema information for all tables associated with a datasource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        tables = await get_datasource_tables(datasource_id)
        schema_info = {}
        
        for table_name in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                schema_info[table_name] = [
                    {
                        'name': col['name'],
                        'type': col['type'],
                        'nullable': not bool(col['notnull']),
                        'default': col['dflt_value'],
                        'primary_key': bool(col['pk'])
                    }
                    for col in columns
                ]
            except Exception as e:
                print(f"[DB-SQLite] Error getting schema for table {table_name}: {e}")
                schema_info[table_name] = []
        
        return schema_info
        
    except Exception as e:
        print(f"[DB-SQLite] Error fetching schema info for datasource {datasource_id}: {e}")
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
            INSERT INTO files (filename, original_filename, file_type, file_size, datasource_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (filename, original_filename, file_type, file_size, datasource_id))
        
        file_id = cursor.lastrowid
        
        # Update file count for the datasource
        cursor.execute('''
            UPDATE datasources 
            SET file_count = file_count + 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.now().strftime(DATE_FORMAT), datasource_id))
        
        conn.commit()
        return file_id
        
    except Exception as e:
        print(f"[DB-SQLite] Error saving file info: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

async def get_files_by_datasource(datasource_id: int) -> List[Dict[str, Any]]:
    """Fetch all files associated with a specific data source"""
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
        print(f"[DB-SQLite] Error fetching files for datasource {datasource_id}: {e}")
        return []
    finally:
        conn.close()

async def update_file_processing_status(file_id: int, status: str, chunks: int = None, 
                                      error_message: str = None) -> bool:
    """Update file processing status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        updates = ["processing_status = ?"]
        params = [status]
        
        if chunks is not None:
            updates.append("processed_chunks = ?")
            params.append(chunks)
            
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
            
        if status == 'completed':
            updates.append("processed_at = ?")
            params.append(datetime.now().strftime(DATE_FORMAT))
        
        params.append(file_id)
        
        cursor.execute(f'''
            UPDATE files 
            SET {", ".join(updates)}
            WHERE id = ?
        ''', params)
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error updating file processing status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def delete_file_record_and_associated_data(file_id: int) -> bool:
    """Delete a file record and all its associated data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get file info before deletion
        cursor.execute('SELECT filename, datasource_id FROM files WHERE id = ?', (file_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"[DB-SQLite] File {file_id} not found for deletion")
            return False
            
        filename = row['filename']
        datasource_id = row['datasource_id']
        
        # Delete physical file
        file_path = UPLOAD_DIR / filename
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"[DB-SQLite] Deleted physical file: {file_path}")
        except Exception as e:
            print(f"[DB-SQLite] Error deleting physical file {file_path}: {e}")
        
        # Delete from files table (CASCADE will handle vector_chunks)
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        
        # Update file count for the datasource
        cursor.execute('''
            UPDATE datasources 
            SET file_count = file_count - 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.now().strftime(DATE_FORMAT), datasource_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"[DB-SQLite] Successfully deleted file {file_id} and associated data")
            return True
        else:
            print(f"[DB-SQLite] No file found with id {file_id}")
            return False
        
    except Exception as e:
        print(f"[DB-SQLite] Error deleting file {file_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ================== HITL (Human-in-the-Loop) Operations ==================

def create_hitl_interrupt(execution_id: str, user_input: str, datasource_id: Optional[int], 
                         interrupt_node: str, interrupt_reason: str, state_data: str) -> bool:
    """Create a new HITL interrupt record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO hitl_interrupts 
            (execution_id, user_input, datasource_id, interrupt_node, interrupt_reason, state_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (execution_id, user_input, datasource_id, interrupt_node, interrupt_reason, state_data, "interrupted"))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error creating HITL interrupt: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_hitl_interrupt(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get HITL interrupt record by execution_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, execution_id, user_input, datasource_id, interrupt_node, 
                   interrupt_reason, state_data, created_at, updated_at, status
            FROM hitl_interrupts WHERE execution_id = ?
        """, (execution_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
        
    except Exception as e:
        print(f"[DB-SQLite] Error getting HITL interrupt: {e}")
        return None
    finally:
        conn.close()

def update_hitl_interrupt_status(execution_id: str, status: str) -> bool:
    """Update HITL interrupt status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE hitl_interrupts 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE execution_id = ?
        """, (status, execution_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error updating HITL interrupt status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def list_hitl_interrupts(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """List HITL interrupts with optional status filter"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if status:
            cursor.execute("""
                SELECT id, execution_id, node_name, user_input, status,
                       interrupted_at, restored_at
                FROM hitl_interrupts 
                WHERE status = ?
                ORDER BY interrupted_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT id, execution_id, node_name, user_input, status,
                       interrupted_at, restored_at
                FROM hitl_interrupts 
                ORDER BY interrupted_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    except Exception as e:
        print(f"[DB-SQLite] Error listing HITL interrupts: {e}")
        return []
    finally:
        conn.close()

def create_hitl_parameter_adjustment(interrupt_id: int, parameter_name: str, 
                                    old_value: Optional[str], new_value: str, 
                                    adjustment_reason: str) -> bool:
    """Create a HITL parameter adjustment record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO hitl_parameter_adjustments 
            (interrupt_id, parameter_name, old_value, new_value, adjustment_reason)
            VALUES (?, ?, ?, ?, ?)
        """, (interrupt_id, parameter_name, old_value, new_value, adjustment_reason))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error creating HITL parameter adjustment: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_hitl_parameter_adjustments(interrupt_id: int) -> List[Dict[str, Any]]:
    """Get HITL parameter adjustments for an interrupt"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, parameter_name, old_value, new_value, adjustment_reason, created_at
            FROM hitl_parameter_adjustments 
            WHERE interrupt_id = ?
            ORDER BY created_at ASC
        """, (interrupt_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    except Exception as e:
        print(f"[DB-SQLite] Error getting HITL parameter adjustments: {e}")
        return []
    finally:
        conn.close()

def create_hitl_execution_history(execution_id: str, operation_type: str, 
                                 node_name: Optional[str] = None, 
                                 parameters: Optional[str] = None,
                                 user_action: str = "user_initiated") -> bool:
    """Create a HITL execution history record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO hitl_execution_history 
            (execution_id, operation_type, node_name, parameters, user_action)
            VALUES (?, ?, ?, ?, ?)
        """, (execution_id, operation_type, node_name, parameters, user_action))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"[DB-SQLite] Error creating HITL execution history: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_hitl_execution_history(execution_id: str) -> List[Dict[str, Any]]:
    """Get HITL execution history for an execution"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, operation_type, node_name, parameters, timestamp, user_action
            FROM hitl_execution_history 
            WHERE execution_id = ?
            ORDER BY timestamp ASC
        """, (execution_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    except Exception as e:
        print(f"[DB-SQLite] Error getting HITL execution history: {e}")
        return []
    finally:
        conn.close()

def cleanup_old_hitl_data(max_age_hours: int = 24) -> int:
    """Clean up old HITL data (cancelled interrupts older than max_age_hours)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Delete old cancelled interrupts and their related data
        cursor.execute("""
            DELETE FROM hitl_interrupts 
            WHERE status = 'cancelled' 
            AND created_at < datetime('now', '-{} hours')
        """.format(max_age_hours))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            print(f"[DB-SQLite] Cleaned up {deleted_count} old HITL interrupts")
        
        return deleted_count
        
    except Exception as e:
        print(f"[DB-SQLite] Error cleaning up old HITL data: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

# ================== Initialization Function ==================

def initialize_database():
    """Initialize the database with schema and demo data."""
    print("[DB-SQLite] Starting database initialization...")
    
    # Initialize schema first
    initialize_database_schema()
    
    # Check if demo data already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if customers table has data
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        
        if customer_count == 0:
            print("[DB-SQLite] No demo data found, generating demo data...")
            
            # Import and run the demo data generation script
            import subprocess
            import sys
            from pathlib import Path
            
            # Get the path to the demo data generation script
            script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "generate_demo_data.py"
            
            if script_path.exists():
                try:
                    # Run the demo data generation script
                    result = subprocess.run([sys.executable, str(script_path)], 
                                         capture_output=True, text=True, cwd=str(script_path.parent.parent))
                    
                    if result.returncode == 0:
                        print("[DB-SQLite] Demo data generated successfully")
                        print(result.stdout)
                    else:
                        print(f"[DB-SQLite] Error generating demo data: {result.stderr}")
                        # Fallback: create minimal demo data
                        create_minimal_demo_data(cursor)
                except Exception as e:
                    print(f"[DB-SQLite] Error running demo data script: {e}")
                    # Fallback: create minimal demo data
                    create_minimal_demo_data(cursor)
            else:
                print("[DB-SQLite] Demo data script not found, creating minimal demo data...")
                create_minimal_demo_data(cursor)
        else:
            print(f"[DB-SQLite] Demo data already exists ({customer_count} customers)")
        
        conn.commit()
        print("[DB-SQLite] Database initialization completed successfully")
        
    except Exception as e:
        print(f"[DB-SQLite] Error during database initialization: {e}")
        conn.rollback()
    finally:
        conn.close()

def create_minimal_demo_data(cursor):
    """Create minimal demo data as fallback."""
    print("[DB-SQLite] Creating minimal demo data...")
    
    # Insert sample customers
    customers = [
        ('CUST_001', 'ABC Corporation', 'John Smith', '+1-555-0101', 'john@abc.com', '123 Main St, New York, NY', 'VIP'),
        ('CUST_002', 'XYZ Ltd', 'Jane Doe', '+1-555-0102', 'jane@xyz.com', '456 Oak Ave, Los Angeles, CA', 'regular'),
        ('CUST_003', 'Tech Solutions Inc', 'Bob Johnson', '+1-555-0103', 'bob@tech.com', '789 Pine St, Chicago, IL', 'wholesale')
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO customers 
        (customer_id, customer_name, contact_person, phone, email, address, customer_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(c[0], c[1], c[2], c[3], c[4], c[5], c[6], '2022-01-01 00:00:00') for c in customers])
    
    # Insert sample products
    products = [
        ('PROD_001', 'iPhone Pro', 'Electronics', 'Smartphones', 999.99, 600.00, 'Latest iPhone model', 'Apple Inc'),
        ('PROD_002', 'MacBook Pro', 'Electronics', 'Laptops', 1999.99, 1200.00, 'Professional laptop', 'Apple Inc'),
        ('PROD_003', 'Windows 11 Pro', 'Software', 'Operating Systems', 199.99, 50.00, 'Professional OS', 'Microsoft Corp')
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO products 
        (product_id, product_name, category, subcategory, unit_price, cost_price, description, supplier, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], '2022-01-01 00:00:00') for p in products])
    
    # Insert sample orders
    orders = [
        ('ORD_001', 'CUST_001', '2022-06-15 10:30:00', 2999.98, 'delivered', 'Credit Card', '123 Main St, New York, NY', 'Priority shipping'),
        ('ORD_002', 'CUST_002', '2022-07-20 14:15:00', 199.99, 'shipped', 'Bank Transfer', '456 Oak Ave, Los Angeles, CA', 'Standard shipping'),
        ('ORD_003', 'CUST_003', '2022-08-10 09:45:00', 999.99, 'confirmed', 'Check', '789 Pine St, Chicago, IL', 'Bulk order')
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO orders 
        (order_id, customer_id, order_date, total_amount, status, payment_method, shipping_address, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(o[0], o[1], o[2], o[3], o[4], o[5], o[6], o[7], o[2], o[2]) for o in orders])
    
    # Insert sample sales
    sales = [
        ('SALE_001', 'ORD_001', 'CUST_001', 'PROD_001', 'iPhone Pro', 1, 999.99, 999.99, '2022-06-15 10:30:00', 'Alice Johnson', 0.00),
        ('SALE_002', 'ORD_001', 'CUST_001', 'PROD_002', 'MacBook Pro', 1, 1999.99, 1999.99, '2022-06-15 10:30:00', 'Alice Johnson', 0.00),
        ('SALE_003', 'ORD_002', 'CUST_002', 'PROD_003', 'Windows 11 Pro', 1, 199.99, 199.99, '2022-07-20 14:15:00', 'Bob Smith', 0.00),
        ('SALE_004', 'ORD_003', 'CUST_003', 'PROD_001', 'iPhone Pro', 1, 999.99, 999.99, '2022-08-10 09:45:00', 'Carol Davis', 0.00)
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO sales 
        (sale_id, order_id, customer_id, product_id, product_name, quantity_sold, price_per_unit, total_amount, sale_date, salesperson, discount_amount, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [(s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9], s[10], s[8]) for s in sales])
    
    # Insert sample inventory
    inventory = [
        ('PROD_001', 50, 10, 100, '2022-01-01 00:00:00', '2022-01-01 00:00:00', 'Warehouse 1'),
        ('PROD_002', 25, 5, 50, '2022-01-01 00:00:00', '2022-01-01 00:00:00', 'Warehouse 1'),
        ('PROD_003', 1000, 100, 2000, '2022-01-01 00:00:00', '2022-01-01 00:00:00', 'Warehouse 2')
    ]
    
    cursor.executemany('''
        INSERT OR REPLACE INTO inventory 
        (product_id, stock_level, min_stock_level, max_stock_level, last_updated, last_restocked, warehouse_location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', inventory)
    
    print("[DB-SQLite] Minimal demo data created successfully") 