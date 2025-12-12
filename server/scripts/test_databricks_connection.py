"""
Script to test Databricks database connection using SQLAlchemy dialect
This script tests the connection to Databricks using SQLAlchemy dialect approach.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from urllib.parse import quote
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# IMPORTANT: Import databricks-sqlalchemy FIRST to register SQLAlchemy dialect
# This must happen before sqlalchemy.create_engine is called
try:
    import databricks.sql
    logger.info("✅ databricks.sql imported")
except ImportError as e:
    logger.error(f"❌ Failed to import databricks.sql: {e}")
    logger.error("Please ensure databricks-sql-connector is properly installed")
    logger.error("  pip install 'databricks-sql-connector[sqlalchemy]'")
    sys.exit(1)

# Import databricks SQLAlchemy dialect to register it
# The dialect is registered when databricks.sqlalchemy.base is imported
try:
    from databricks.sqlalchemy import base  # noqa: F401
    logger.info("✅ databricks.sqlalchemy.base imported - dialect should be registered")
except ImportError as e:
    logger.warning(f"⚠️  Failed to import databricks.sqlalchemy.base: {e}")
    logger.warning("Will use databricks.sql dialect registration instead")

# Load environment variables
SERVER_ROOT = Path(__file__).resolve().parent.parent
env_file = SERVER_ROOT / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    logger.info(f"Loaded environment variables from: {env_file}")
    
# For testing cross-schema queries, remove DATABRICKS_SCHEMA if set
# This allows SQLDatabase to discover all schemas
if os.getenv("DATABRICKS_SCHEMA"):
    logger.info("⚠️  DATABRICKS_SCHEMA is set in .env file")
    logger.info("   For cross-schema testing, consider commenting it out or removing it")
    logger.info("   Current value will be used. To test without schema, unset this variable.")
else:
    logger.warning(f"Environment file not found: {env_file}")

def build_databricks_url():
    """Build Databricks connection URL from environment variables"""
    server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    token = os.getenv("DATABRICKS_TOKEN")
    # Use DATABRICKS_DATABASE for catalog, fallback to DATABRICKS_CATALOG
    catalog = os.getenv("DATABRICKS_DATABASE") or os.getenv("DATABRICKS_CATALOG")
    # Schema is optional - if not specified, SQLDatabase will discover all schemas
    schema = os.getenv("DATABRICKS_SCHEMA")  # Remove default value to allow cross-schema queries
    
    logger.info("=" * 60)
    logger.info("Databricks Connection Configuration:")
    logger.info(f"  Server Hostname: {server_hostname}")
    logger.info(f"  HTTP Path: {http_path}")
    logger.info(f"  Token: {'*' * 10 if token else 'NOT SET'}")
    logger.info(f"  Catalog: {catalog or '(not set)'}")
    logger.info(f"  Schema: {schema or '(not set - will discover all schemas)'}")
    logger.info("=" * 60)
    
    if not server_hostname:
        logger.error("DATABRICKS_SERVER_HOSTNAME is not set")
        return None, None
    if not http_path:
        logger.error("DATABRICKS_HTTP_PATH is not set")
        return None, None
    if not token:
        logger.error("DATABRICKS_TOKEN is not set")
        return None, None
    
    # Build Databricks connection string - use catalog as query parameter
    # IMPORTANT: databricks-sqlalchemy ONLY supports databricks:// format
    # databricks+connector:// format is NOT supported by databricks-sqlalchemy
    # Note: urlencode will automatically encode values, so don't pre-encode http_path
    from urllib.parse import urlencode
    
    # Build base URL - only use databricks:// format (databricks-sqlalchemy standard)
    base_url = f"databricks://token:{token}@{server_hostname}:443"
    
    # Add query parameters - urlencode will handle encoding automatically
    query_params = {'http_path': http_path}
    if catalog:
        query_params['catalog'] = catalog
    # Only add schema if explicitly specified (allows cross-schema queries)
    if schema:
        query_params['schema'] = schema
        logger.info(f"Using specified schema: {schema}")
    else:
        logger.info("No schema specified - SQLDatabase will discover all schemas in catalog")
        logger.info("  Tables can be accessed using schema.table format (e.g., public.src_stations, staging.stg_stations)")
    
    query_string = urlencode(query_params, doseq=True)
    
    # Only use databricks:// format (databricks-sqlalchemy doesn't support databricks+connector://)
    db_url = f"{base_url}?{query_string}"
    
    logger.info(f"Generated connection URL: databricks://token:***@{server_hostname}:443?{query_string}")
    logger.info("Note: databricks-sqlalchemy only supports databricks:// format (not databricks+connector://)")
    
    # Return same URL for both (databricks+connector:// is not supported by databricks-sqlalchemy)
    return db_url, db_url


def test_sqlalchemy_connection(db_url):
    """Test SQLAlchemy connection to Databricks using dialect"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing SQLAlchemy Dialect Connection...")
    logger.info("=" * 60)
    
    try:
        # Check if databricks-sql-connector version supports SQLAlchemy
        try:
            import databricks.sql
            # Check version
            try:
                import pkg_resources
                version = pkg_resources.get_distribution("databricks-sql-connector").version
                logger.info(f"databricks-sql-connector version: {version}")
                # SQLAlchemy support requires version 3.0.0+
                major_version = int(version.split('.')[0])
                if major_version < 3:
                    logger.error(f"❌ SQLAlchemy support requires databricks-sql-connector >= 3.0.0, but found {version}")
                    logger.error("Please upgrade: pip install --upgrade 'databricks-sql-connector[sqlalchemy]'")
                    return False
            except Exception:
                logger.warning("Could not determine databricks-sql-connector version")
        except ImportError as e:
            logger.error(f"❌ Failed to import databricks.sql: {e}")
            logger.error("Please install: pip install 'databricks-sql-connector[sqlalchemy]'")
            return False
        
        # Check SQLAlchemy dialect registry
        from sqlalchemy.dialects import registry
        logger.info("Checking SQLAlchemy dialect registry...")
        
        # Check if databricks dialect is registered
        # Note: databricks-sqlalchemy only registers 'databricks' dialect, not 'databricks+connector'
        dialect_found = False
        try:
            dialect = registry.load("databricks")
            logger.info(f"✅ Dialect 'databricks' is registered: {dialect}")
            dialect_found = True
        except Exception as e:
            logger.warning(f"⚠️  databricks dialect not found: {e}")
            logger.warning("   The dialect might be registered lazily when create_engine is called")
            logger.warning("   Make sure databricks-sqlalchemy is installed: pip install databricks-sqlalchemy")
        
        # Import SQLAlchemy
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.exc import SQLAlchemyError
        
        logger.info("Creating SQLAlchemy engine...")
        logger.info(f"Connection URL format: {db_url.split('://')[0]}://...")
        
        # Try to create engine - this should trigger dialect registration
        # Use echo=False to reduce output
        engine = create_engine(db_url, echo=False)
        
        logger.info(f"✅ Engine created successfully!")
        logger.info(f"   Engine dialect: {engine.dialect.name if hasattr(engine, 'dialect') else 'unknown'}")
        
        logger.info("Connecting to database...")
        with engine.connect() as conn:
            logger.info("✅ Connection successful!")
            
            # Get inspector
            inspector = inspect(engine)
            
            # List catalogs
            logger.info("\n" + "-" * 60)
            logger.info("Listing Catalogs:")
            logger.info("-" * 60)
            try:
                catalogs = inspector.get_schema_names()
                for catalog_name in catalogs:
                    logger.info(f"  - {catalog_name}")
            except Exception as e:
                logger.warning(f"Could not list catalogs: {e}")
            
            # List schemas
            logger.info("\n" + "-" * 60)
            logger.info("Listing Schemas:")
            logger.info("-" * 60)
            try:
                schemas = inspector.get_schema_names()
                for schema_name in schemas[:10]:  # Limit to first 10
                    logger.info(f"  - {schema_name}")
            except Exception as e:
                logger.warning(f"Could not list schemas: {e}")
            
            # List tables
            logger.info("\n" + "-" * 60)
            logger.info("Listing Tables:")
            logger.info("-" * 60)
            try:
                tables = inspector.get_table_names()
                if tables:
                    logger.info(f"Found {len(tables)} tables:")
                    for table_name in tables[:20]:  # Limit to first 20
                        logger.info(f"  - {table_name}")
                    if len(tables) > 20:
                        logger.info(f"  ... and {len(tables) - 20} more tables")
                else:
                    logger.warning("No tables found")
            except Exception as e:
                logger.warning(f"Could not list tables: {e}")
            
            # Test a simple query
            logger.info("\n" + "-" * 60)
            logger.info("Testing Simple Query (SELECT 1):")
            logger.info("-" * 60)
            try:
                result = conn.execute(text("SELECT 1 as test_value"))
                row = result.fetchone()
                logger.info(f"✅ Query successful! Result: {row}")
            except Exception as e:
                logger.error(f"❌ Query failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # Test cross-schema query if schema is not specified
            if not os.getenv("DATABRICKS_SCHEMA"):
                logger.info("\n" + "-" * 60)
                logger.info("Testing Cross-Schema Query:")
                logger.info("-" * 60)
                logger.info("Attempting to query tables from different schemas...")
                
                # Try to find tables in different schemas
                cross_schema_queries = [
                    # Query from public schema
                    "SELECT COUNT(*) as count FROM public.src_stations",
                    # Query from staging schema  
                    "SELECT COUNT(*) as count FROM staging.stg_stations",
                    # Cross-schema JOIN (if both tables exist)
                    """SELECT 
                        s.station_id, 
                        s.station_name as src_name,
                        st.station_name as stg_name
                    FROM public.src_stations s
                    LEFT JOIN staging.stg_stations st ON s.station_id = st.station_id
                    LIMIT 5"""
                ]
                
                for i, query in enumerate(cross_schema_queries, 1):
                    try:
                        logger.info(f"\nQuery {i}: {query[:80]}...")
                        result = conn.execute(text(query))
                        rows = result.fetchall()
                        logger.info(f"✅ Cross-schema query {i} successful! Rows: {len(rows)}")
                        if rows:
                            logger.info(f"   Sample result: {rows[0]}")
                    except Exception as e:
                        logger.warning(f"⚠️  Cross-schema query {i} failed: {e}")
                        logger.warning(f"   This is expected if tables don't exist in those schemas")
            
            return True
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Please install required packages:")
        logger.error("  pip install databricks-sql-connector sqlalchemy")
        return False
    except SQLAlchemyError as e:
        logger.error(f"❌ SQLAlchemy error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_langchain_connection(db_url):
    """Test LangChain SQLDatabase connection to Databricks using SQLAlchemy dialect"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing LangChain SQLDatabase Connection (SQLAlchemy Dialect)...")
    logger.info("=" * 60)
    
    try:
        # Use the smart factory function that handles catalog parsing correctly
        # This is the same function used by SQL-Agent
        # Add parent directory to path
        parent_dir = Path(__file__).resolve().parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        from src.utils.databricks_adapter import create_sql_database
        
        logger.info("Creating LangChain SQLDatabase using create_sql_database factory...")
        logger.info(f"Using connection URL: {db_url.split('://')[0]}://...")
        
        # Ensure databricks SQLAlchemy dialect is imported to register dialect
        try:
            from databricks.sqlalchemy import base  # noqa: F401
            logger.info("✅ databricks.sqlalchemy.base imported - dialect should be registered")
        except ImportError:
            logger.warning("⚠️  databricks.sqlalchemy.base not found, will try databricks.sql")
            try:
                import databricks.sql  # noqa: F401
                logger.info("✅ databricks.sql imported - dialect should be registered")
            except ImportError as e:
                logger.error(f"❌ Failed to import databricks modules: {e}")
                return False
        
        # Use the smart factory that handles catalog parsing
        db = create_sql_database(
            db_url,
            sample_rows_in_table_info=0
        )
        
        logger.info("✅ LangChain SQLDatabase created successfully!")
        logger.info(f"   Database type: {type(db).__name__}")
        
        # Get table names
        logger.info("\n" + "-" * 60)
        logger.info("Getting Table Names:")
        logger.info("-" * 60)
        try:
            table_names = db.get_usable_table_names()
            logger.info(f"Found {len(table_names)} tables:")
            for table_name in table_names[:20]:  # Limit to first 20
                logger.info(f"  - {table_name}")
            if len(table_names) > 20:
                logger.info(f"  ... and {len(table_names) - 20} more tables")
        except Exception as e:
            logger.warning(f"Could not get table names: {e}")
        
        # Get table info
        logger.info("\n" + "-" * 60)
        logger.info("Getting Table Info (first table):")
        logger.info("-" * 60)
        try:
            table_info = db.get_table_info()
            # Limit output to first 1000 characters
            info_preview = table_info[:1000]
            logger.info(f"Table info preview:\n{info_preview}")
            if len(table_info) > 1000:
                logger.info(f"... ({len(table_info) - 1000} more characters)")
        except Exception as e:
            logger.warning(f"Could not get table info: {e}")
        
        # Test a simple query
        logger.info("\n" + "-" * 60)
        logger.info("Testing Simple Query via LangChain:")
        logger.info("-" * 60)
        try:
            result = db.run("SELECT 1 as test_value")
            logger.info(f"✅ Query successful! Result: {result}")
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
        
        # Test cross-schema query if schema is not specified
        if not os.getenv("DATABRICKS_SCHEMA"):
            logger.info("\n" + "-" * 60)
            logger.info("Testing Cross-Schema Query via LangChain:")
            logger.info("-" * 60)
            logger.info("Attempting to query tables from different schemas using schema.table format...")
            
            cross_schema_queries = [
                # Query from public schema
                ("SELECT COUNT(*) as count FROM public.src_stations", "Query public.src_stations"),
                # Query from staging schema
                ("SELECT COUNT(*) as count FROM staging.stg_stations", "Query staging.stg_stations"),
                # Cross-schema JOIN
                ("""SELECT 
                    s.station_id, 
                    s.station_name as src_name,
                    st.station_name as stg_name
                FROM public.src_stations s
                LEFT JOIN staging.stg_stations st ON s.station_id = st.station_id
                LIMIT 5""", "Cross-schema JOIN query")
            ]
            
            for query, description in cross_schema_queries:
                try:
                    logger.info(f"\n{description}: {query[:80]}...")
                    result = db.run(query)
                    logger.info(f"✅ {description} successful!")
                    logger.info(f"   Result: {str(result)[:200]}")
                except Exception as e:
                    logger.warning(f"⚠️  {description} failed: {e}")
                    logger.warning(f"   This is expected if tables don't exist in those schemas")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Please install required packages:")
        logger.error("  pip install langchain-community databricks-sql-connector")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    logger.info("\n" + "=" * 60)
    logger.info("Checking Dependencies...")
    logger.info("=" * 60)
    
    dependencies = {
        'sqlalchemy': 'SQLAlchemy',
        'databricks.sql': 'databricks-sql-connector',
        'langchain_community': 'langchain-community'
    }
    
    missing = []
    for module_name, package_name in dependencies.items():
        try:
            module = __import__(module_name)
            logger.info(f"✅ {package_name} is installed")
            # Try to get version if available
            try:
                version = getattr(module, '__version__', 'unknown')
                logger.info(f"   Version: {version}")
            except:
                pass
        except ImportError:
            logger.error(f"❌ {package_name} is NOT installed")
            missing.append(package_name)
    
    # Additional check: verify databricks.sql can be imported and check for dialect registration
    try:
        import databricks.sql
        logger.info("✅ databricks.sql module can be imported")
        
        # Check SQLAlchemy dialect registry
        from sqlalchemy.dialects import registry
        logger.info("Checking SQLAlchemy dialect registry...")
        
        # Try to check if databricks dialect is available by attempting to load it
        # Note: databricks-sqlalchemy only registers 'databricks' dialect, not 'databricks+connector'
        try:
            dialect = registry.load("databricks")
            logger.info("✅ Databricks dialect is registered")
        except Exception as e:
            logger.warning(f"⚠️  databricks dialect not found: {e}")
        except Exception as e:
            logger.warning(f"Could not check dialect registry: {e}")
            
    except ImportError as e:
        logger.error(f"❌ Cannot import databricks.sql: {e}")
        missing.append('databricks-sql-connector')
    
    if missing:
        logger.error("\n" + "=" * 60)
        logger.error("Missing dependencies. Please install:")
        logger.error(f"  pip install {' '.join(missing)}")
        logger.error("=" * 60)
        return False
    
    return True

def main():
    """Main test function - Testing SQLAlchemy Dialect Approach"""
    logger.info("=" * 60)
    logger.info("Databricks Connection Test Script (SQLAlchemy Dialect Mode)")
    logger.info("Testing without schema specification for cross-schema queries")
    logger.info("=" * 60)
    
    # Temporarily unset DATABRICKS_SCHEMA for cross-schema testing
    original_schema = os.environ.pop('DATABRICKS_SCHEMA', None)
    if original_schema:
        logger.info(f"⚠️  Temporarily unsetting DATABRICKS_SCHEMA={original_schema} for cross-schema testing")
        logger.info("   This allows SQLDatabase to discover all schemas in the catalog")
    else:
        logger.info("✅ DATABRICKS_SCHEMA is not set - will test cross-schema queries")
    
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Build connection URL
    db_url_connector, db_url_standard = build_databricks_url()
    if not db_url_connector:
        logger.error("Failed to build connection URL. Please check your .env file.")
        sys.exit(1)
    
    # Step 1: Test SQLAlchemy Dialect Connection (Primary Method)
    logger.info("\n" + "=" * 60)
    logger.info("Step 1: Testing SQLAlchemy Dialect Connection")
    logger.info("This is the primary method for SQL-Agent integration")
    logger.info("=" * 60)
    
    # Use databricks:// format (databricks-sqlalchemy only supports this format)
    # databricks+connector:// is not supported by databricks-sqlalchemy
    db_url = db_url_standard  # Use standard format only
    sqlalchemy_success = test_sqlalchemy_connection(db_url)
    
    # Step 2: Test LangChain SQLDatabase Connection
    langchain_success = False
    if sqlalchemy_success:
        logger.info("\n" + "=" * 60)
        logger.info("Step 2: Testing LangChain SQLDatabase Connection")
        logger.info("This is required for SQL-Agent to work")
        logger.info("=" * 60)
        langchain_success = test_langchain_connection(db_url)
    else:
        # Try LangChain even if SQLAlchemy failed (use standard format only)
        logger.info("\n" + "=" * 60)
        logger.info("Step 2: Testing LangChain SQLDatabase Connection (Fallback)")
        logger.info("=" * 60)
        langchain_success = test_langchain_connection(db_url_standard)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary:")
    logger.info("=" * 60)
    logger.info(f"SQLAlchemy Dialect Connection: {'✅ PASSED' if sqlalchemy_success else '❌ FAILED'}")
    logger.info(f"LangChain SQLDatabase Connection: {'✅ PASSED' if langchain_success else '❌ FAILED'}")
    logger.info("=" * 60)
    
    if sqlalchemy_success and langchain_success:
        logger.info("\n✅ SQLAlchemy Dialect connection works!")
        logger.info("   This is the method used by SQL-Agent (LangChain).")
        logger.info("   ReAct mode should work correctly with this setup.")
        
        logger.info("\n✅ All SQL-Agent required connections verified successfully!")
        sys.exit(0)
    elif sqlalchemy_success:
        logger.warning("\n⚠️  SQLAlchemy connection works, but LangChain connection failed.")
        logger.warning("   This may cause issues with SQL-Agent.")
        logger.warning("   Please check LangChain SQLDatabase compatibility.")
        logger.warning("   Issue: Catalog may not be properly parsed from URL.")
        sys.exit(1)
    else:
        logger.error("\n❌ SQLAlchemy Dialect connection failed.")
        logger.error("   This is required for SQL-Agent ReAct mode to work.")
        logger.error("   Please check:")
        logger.error("   1. Install: pip install 'databricks-sql-connector[sqlalchemy]'")
        logger.error("   2. Environment variables are set correctly")
        logger.error("   3. Network connectivity to Databricks")
        logger.error("   4. Token and permissions are valid")
        logger.error("   5. Catalog/Schema configuration (use DATABRICKS_DATABASE=workspace)")
        
        sys.exit(1)
    
    # Restore original DATABRICKS_SCHEMA if it was unset
    if 'original_schema' in locals() and original_schema:
        os.environ['DATABRICKS_SCHEMA'] = original_schema
        logger.info(f"\n✅ Restored DATABRICKS_SCHEMA={original_schema}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

