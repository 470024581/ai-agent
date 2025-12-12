"""
Databricks SQLAlchemy Dialect Adapter for LangChain SQLDatabase

This module provides a smart factory that creates SQLDatabase instances for Databricks.
It uses SQLAlchemy dialect approach (using databricks-sqlalchemy) which is the
recommended method for SQL-Agent ReAct mode.

Implementation follows the same pattern as test_databricks_connection.py:
- Only supports databricks:// format (not databricks+connector://)
- Catalog is passed as query parameter, not in URL path
- Uses databricks-sqlalchemy dialect registration
"""
import os
import logging
from typing import List, Optional, Any, Dict

# Import databricks-sqlalchemy to register SQLAlchemy dialect
# This must be imported before sqlalchemy.create_engine is called
# The dialect is registered when databricks.sqlalchemy.base is imported
logger = logging.getLogger(__name__)
databricks_sqlalchemy_available = False
try:
    from databricks.sqlalchemy import base  # noqa: F401
    databricks_sqlalchemy_available = True
    logger.info("✅ databricks.sqlalchemy.base imported - dialect should be registered")
except ImportError as e:
    logger.warning(f"⚠️  Failed to import databricks.sqlalchemy.base: {e}")
    logger.warning("databricks-sqlalchemy is required for SQLAlchemy dialect connection")
    logger.warning("Please install: pip install databricks-sqlalchemy")

# Import SQLDatabase to inherit from it
try:
    from langchain_community.utilities import SQLDatabase
except ImportError:
    SQLDatabase = object  # Fallback if not available


def create_sql_database(
    database_uri: str,
    include_tables: Optional[List[str]] = None,
    sample_rows_in_table_info: int = 0,
    **kwargs
):
    """
    Smart factory function that creates SQLDatabase for Databricks using SQLAlchemy dialect.
    
    This function uses SQLAlchemy dialect approach (using databricks-sqlalchemy)
    which is the recommended method for SQL-Agent ReAct mode.
    
    Implementation follows the same pattern as test_databricks_connection.py:
    - Only supports databricks:// format (not databricks+connector://)
    - Catalog is passed as query parameter, not in URL path
    - Uses databricks-sqlalchemy dialect registration
    
    Args:
        database_uri: Database connection URI (databricks:// format only)
        include_tables: Optional list of table names to include
        sample_rows_in_table_info: Number of sample rows to include in table info
        **kwargs: Additional arguments passed to SQLDatabase
        
    Returns:
        SQLDatabase instance (using SQLAlchemy dialect)
    """
    # Check if this is a Databricks URI
    is_databricks = database_uri.startswith("databricks://") or database_uri.startswith("databricks+connector://")
    
    if is_databricks:
        # Use SQLAlchemy dialect approach (required for ReAct mode)
        logger.info("Detected Databricks URI, attempting SQLAlchemy dialect connection...")
        try:
            from langchain_community.utilities import SQLDatabase
            
            # Ensure databricks SQLAlchemy dialect is imported to register dialect
            if not databricks_sqlalchemy_available:
                try:
                    from databricks.sqlalchemy import base  # noqa: F401
                    logger.info("✅ databricks.sqlalchemy.base imported - dialect should be registered")
                except ImportError as e:
                    logger.error(f"❌ databricks SQLAlchemy dialect not found: {e}")
                    logger.error("Cannot use SQLAlchemy dialect without databricks-sqlalchemy")
                    logger.error("Please install: pip install databricks-sqlalchemy")
                    raise ImportError("databricks SQLAlchemy dialect is required for SQLAlchemy dialect connection")
            
            # Normalize URI: databricks+connector:// -> databricks://
            # databricks-sqlalchemy ONLY supports databricks:// format (not databricks+connector://)
            normalized_uri = database_uri
            if database_uri.startswith("databricks+connector://"):
                normalized_uri = database_uri.replace("databricks+connector://", "databricks://", 1)
                logger.info("Normalized URI from databricks+connector:// to databricks://")
                logger.info("Note: databricks-sqlalchemy only supports databricks:// format")
            
            # Parse URL to ensure catalog is properly set as query parameter
            # databricks-sqlalchemy requires catalog as a query parameter, not in path
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(normalized_uri)
            query_params = parse_qs(parsed.query)
            
            # Get catalog from environment variable (DATABRICKS_DATABASE) or from URL path
            catalog = os.getenv("DATABRICKS_DATABASE") or os.getenv("DATABRICKS_CATALOG")
            catalog_from_path = None
            if parsed.path and len(parsed.path) > 1:
                catalog_from_path = parsed.path.strip('/')
            
            # Use environment variable catalog if available, otherwise use path catalog
            final_catalog = catalog or catalog_from_path
            
            # Ensure catalog is in query params (databricks-sqlalchemy requires this)
            if final_catalog and 'catalog' not in query_params:
                query_params['catalog'] = [final_catalog]
                # Rebuild URL with catalog in query params and remove from path
                new_query = urlencode(query_params, doseq=True)
                normalized_uri = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    '',  # Remove catalog from path, put it in query
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                logger.info(f"Added catalog '{final_catalog}' to query parameters (from {'env' if catalog else 'URL path'})")
            
            # Handle schema parameter for SQLDatabase initialization
            # If no schema is specified in URL, SQLDatabase needs a default schema for table discovery
            # However, we can still query across schemas using schema.table format
            schema_in_url = query_params.get('schema', [None])[0] if query_params.get('schema') else None
            
            # If no schema in URL and no include_tables with schema prefix, use a default schema for initialization
            # This allows SQLDatabase to discover tables, but queries can still use schema.table format
            if not schema_in_url and not include_tables:
                # Try to use 'public' as default schema for table discovery
                # But queries can still use schema.table format
                default_schema = os.getenv("DATABRICKS_SCHEMA", "public")
                if default_schema:
                    query_params['schema'] = [default_schema]
                    new_query = urlencode(query_params, doseq=True)
                    normalized_uri = urlunparse((
                        parsed.scheme,
                        parsed.netloc,
                        '',
                        parsed.params,
                        new_query,
                        parsed.fragment
                    ))
                    logger.info(f"Using default schema '{default_schema}' for SQLDatabase initialization (table discovery)")
                    logger.info("  Note: You can still query other schemas using schema.table format (e.g., staging.stg_stations)")
            elif not schema_in_url and include_tables:
                # If include_tables is specified, check if any have schema prefix
                has_schema_prefix = any('.' in table for table in include_tables)
                if not has_schema_prefix:
                    # No schema prefix in table names, use default schema
                    default_schema = os.getenv("DATABRICKS_SCHEMA", "public")
                    if default_schema:
                        query_params['schema'] = [default_schema]
                        new_query = urlencode(query_params, doseq=True)
                        normalized_uri = urlunparse((
                            parsed.scheme,
                            parsed.netloc,
                            '',
                            parsed.params,
                            new_query,
                            parsed.fragment
                        ))
                        logger.info(f"Using default schema '{default_schema}' for SQLDatabase initialization")
            
            # Create SQLDatabase using SQLAlchemy dialect
            # This is the same approach as test_databricks_connection.py
            db = SQLDatabase.from_uri(
                normalized_uri,
                include_tables=include_tables,
                sample_rows_in_table_info=sample_rows_in_table_info,
                **kwargs
            )
            
            logger.info("✅ Using SQLAlchemy dialect connection (databricks-sqlalchemy)")
            logger.info("   This matches the implementation in test_databricks_connection.py")
            return db
            
        except Exception as e:
            logger.error(f"❌ SQLAlchemy dialect connection failed: {e}")
            logger.error("Cannot proceed without SQLAlchemy dialect")
            logger.error("Please ensure databricks-sqlalchemy is installed: pip install databricks-sqlalchemy")
            raise
    
    # For non-Databricks URIs, use standard SQLDatabase
    try:
        from langchain_community.utilities import SQLDatabase
        logger.info("Using standard SQLDatabase (SQLAlchemy)")
        return SQLDatabase.from_uri(
            database_uri,
            include_tables=include_tables,
            sample_rows_in_table_info=sample_rows_in_table_info,
            **kwargs
        )
    except Exception as e:
        logger.error(f"❌ Failed to create SQLDatabase: {e}", exc_info=True)
        raise
