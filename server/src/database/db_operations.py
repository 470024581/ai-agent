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
        
        # Insert default datasource if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO datasources (id, name, description, type, is_active, file_count)
            VALUES (1, 'Default', 'Default system data (products, inventory, sales)', 'default', 1, 0)
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
        
        # If this is a SQL_TABLE_FROM_FILE datasource, we should also drop the dynamically created table(s)
        if datasource['type'] == DataSourceType.SQL_TABLE_FROM_FILE:
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
                SELECT id, execution_id, user_input, datasource_id, interrupt_node, 
                       interrupt_reason, created_at, updated_at, status
                FROM hitl_interrupts 
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT id, execution_id, user_input, datasource_id, interrupt_node, 
                       interrupt_reason, created_at, updated_at, status
                FROM hitl_interrupts 
                ORDER BY created_at DESC
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
    """Main database initialization function"""
    try:
        print("[DB-SQLite] Starting database initialization...")
        initialize_database_schema()
        print("[DB-SQLite] Database initialization completed successfully")
    except Exception as e:
        print(f"[DB-SQLite] Error during database initialization: {e}")
        raise 