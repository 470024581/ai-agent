-- AI Agent Database Schema
-- This file contains all the table structures and initial data for the AI Agent application
-- Created: 2024

-- ============================================================================
-- CORE BUSINESS TABLES (ERP System) - Enhanced 5-Table Schema
-- ============================================================================

-- Customers table: Stores customer information
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
);

-- Products table: Stores product information
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
);

-- Orders table: Stores order information
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
);

-- Sales table: Stores sales transaction records (enhanced with order and customer links)
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
);

-- Inventory table: Stores current stock levels
CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,            -- Product ID (foreign key)
    stock_level INTEGER NOT NULL DEFAULT 0, -- Current stock quantity
    min_stock_level INTEGER DEFAULT 10,     -- Minimum stock level for reorder
    max_stock_level INTEGER DEFAULT 1000,   -- Maximum stock level
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Last stock update
    last_restocked DATETIME,                -- Last restock date
    warehouse_location TEXT,                 -- Warehouse location
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

-- ============================================================================
-- DATA SOURCE MANAGEMENT TABLES
-- ============================================================================

-- Datasources table: Manages different data sources (Default, Knowledge Base, SQL, Hybrid)
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
);

-- Files table: Stores uploaded file metadata and processing status
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
);

-- Vector chunks table: Stores document chunks for RAG (Retrieval-Augmented Generation)
CREATE TABLE IF NOT EXISTS vector_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
);

-- Datasource tables: Maps multiple tables to datasources (supports multi-table datasources)
CREATE TABLE IF NOT EXISTS datasource_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datasource_id INTEGER NOT NULL,
    table_name TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE,
    UNIQUE(datasource_id, table_name)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================================

-- File-related indexes
CREATE INDEX IF NOT EXISTS idx_files_datasource_id ON files(datasource_id);
CREATE INDEX IF NOT EXISTS idx_vector_chunks_file_id ON vector_chunks(file_id);

-- Datasource-related indexes
CREATE INDEX IF NOT EXISTS idx_datasources_is_active ON datasources(is_active);
CREATE INDEX IF NOT EXISTS idx_datasource_tables_datasource_id ON datasource_tables(datasource_id);

-- ============================================================================
-- INITIAL DATA SETUP
-- ============================================================================

-- Insert default ERP system datasource
-- This represents the core business data (products, inventory, sales)
INSERT OR IGNORE INTO datasources (
    id, 
    name, 
    description, 
    type, 
    is_active, 
    file_count
) VALUES (
    1, 
    'Default ERP System', 
    'Default ERP system data (products, inventory, sales)', 
    'default', 
    1, 
    0
);

-- ============================================================================
-- DATA TYPES SUPPORTED
-- ============================================================================

-- The system supports the following data source types:
-- 1. 'default'            - Core ERP system tables (products, inventory, sales)
-- 2. 'knowledge_base'     - Document collections for RAG processing
-- 3. 'sql_table_from_file'- SQL tables created from uploaded files (CSV, Excel)
-- 4. 'hybrid'             - Combined structured and unstructured data processing

-- File types supported for upload:
-- - CSV files: Automatically parsed and converted to SQL tables
-- - PDF files: Text extracted and stored in vector chunks for RAG
-- - Word documents (.docx): Text extracted and stored in vector chunks
-- - Excel files (.xlsx): Data converted to SQL tables
-- - Text files (.txt): Content stored in vector chunks for RAG

-- ============================================================================
-- HITL (HUMAN-IN-THE-LOOP) TABLES
-- ============================================================================

-- HITL interrupts table: Stores interrupted workflow executions
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
);

-- HITL parameter adjustments table: Records parameter changes during HITL
CREATE TABLE IF NOT EXISTS hitl_parameter_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interrupt_id INTEGER NOT NULL,
    parameter_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    adjustment_reason TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interrupt_id) REFERENCES hitl_interrupts(id) ON DELETE CASCADE
);

-- HITL execution history table: Tracks all HITL operations
CREATE TABLE IF NOT EXISTS hitl_execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- pause, interrupt, resume, cancel
    node_name TEXT,
    parameters TEXT, -- JSON serialized parameters
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_action TEXT, -- user_initiated, system_initiated
    FOREIGN KEY (execution_id) REFERENCES hitl_interrupts(execution_id)
);

-- ============================================================================
-- HITL INDEXES FOR PERFORMANCE
-- ============================================================================

-- HITL-related indexes
CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_execution_id ON hitl_interrupts(execution_id);
CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_status ON hitl_interrupts(status);
CREATE INDEX IF NOT EXISTS idx_hitl_interrupts_created_at ON hitl_interrupts(created_at);
CREATE INDEX IF NOT EXISTS idx_hitl_parameter_adjustments_interrupt_id ON hitl_parameter_adjustments(interrupt_id);
CREATE INDEX IF NOT EXISTS idx_hitl_execution_history_execution_id ON hitl_execution_history(execution_id);
CREATE INDEX IF NOT EXISTS idx_hitl_execution_history_timestamp ON hitl_execution_history(timestamp);

-- ============================================================================
-- WORKFLOW INTEGRATION
-- ============================================================================

-- This database schema supports the LangGraph workflow system with:
-- - Real-time processing status tracking
-- - Multiple data source type handling
-- - Automatic file processing and chunking
-- - Vector storage for semantic search
-- - Hybrid query routing between SQL and RAG
-- - Multi-table support per datasource
-- - Error handling and retry mechanisms
-- - Human-in-the-loop (HITL) workflow control
-- - Pause/Resume and Interrupt/Resume capabilities
-- - Parameter adjustment during workflow execution 