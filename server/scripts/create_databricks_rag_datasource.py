"""
Script to create a RAG datasource named "Databricks" and import all files from data_warehouse/dbt/rag_docs
This script mimics the behavior of uploading files through the web interface.
"""
import asyncio
import sys
import uuid
from pathlib import Path
import shutil
import logging

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db_operations import (
    create_datasource,
    get_datasource,
    save_file_info,
    update_file_processing_status,
    get_datasources
)
from src.document_loaders.file_processor import process_uploaded_file
from src.models.data_models import DataSourceType, FileType, ProcessingStatus
from src.config.config import DATA_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directories
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Source directory for RAG docs
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAG_DOCS_DIR = PROJECT_ROOT / "data_warehouse" / "dbt" / "rag_docs"


def get_file_type(file_path: Path) -> FileType:
    """Determine file type from extension"""
    extension = file_path.suffix.lower()
    file_type_mapping = {
        '.pdf': FileType.PDF,
        '.docx': FileType.DOCX,
        '.doc': FileType.DOCX,
        '.txt': FileType.TEXT,
        '.md': FileType.MD,
    }
    return file_type_mapping.get(extension, FileType.UNKNOWN)


async def import_file_to_datasource(
    file_path: Path,
    datasource_id: int,
    original_filename: str
) -> bool:
    """
    Import a single file to the datasource.
    This mimics the behavior of the upload_file API endpoint.
    """
    try:
        # Generate unique filename
        file_extension = file_path.suffix.lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        target_path = UPLOAD_DIR / unique_filename

        # Copy file to upload directory
        shutil.copy2(file_path, target_path)
        logger.info(f"Copied file: {original_filename} -> {unique_filename}")

        # Get file size
        file_size = target_path.stat().st_size

        # Determine file type
        file_type = get_file_type(file_path)
        if file_type == FileType.UNKNOWN:
            logger.warning(f"Unknown file type for {original_filename}, skipping")
            return False

        # Save file information to database
        file_id = await save_file_info(
            filename=unique_filename,
            original_filename=original_filename,
            file_type=file_type.value,
            file_size=file_size,
            datasource_id=datasource_id
        )

        if not file_id:
            logger.error(f"Failed to save file info for {original_filename}")
            # Cleanup copied file
            if target_path.exists():
                target_path.unlink()
            return False

        logger.info(f"Saved file info: {original_filename} (ID: {file_id})")

        # Process file (extract text, chunk, generate embeddings)
        # Note: process_uploaded_file will update the status internally
        try:
            await process_uploaded_file(
                file_id=file_id,
                datasource_id=datasource_id,
                file_path=target_path,
                original_filename=original_filename,
                file_type=file_type.value
            )
            logger.info(f"Successfully processed file: {original_filename}")
            return True
        except Exception as processing_error:
            logger.error(f"Error processing file {original_filename}: {processing_error}", exc_info=True)
            # process_uploaded_file should have updated status, but ensure it's failed
            await update_file_processing_status(
                file_id,
                ProcessingStatus.FAILED.value,
                error_message=str(processing_error)
            )
            return False

    except Exception as e:
        logger.error(f"Error importing file {original_filename}: {e}", exc_info=True)
        return False


async def create_and_import_databricks_datasource():
    """
    Main function to create Databricks datasource and import all files from rag_docs directory
    """
    logger.info("Starting Databricks RAG datasource creation and import process")

    # Check if RAG docs directory exists
    if not RAG_DOCS_DIR.exists():
        logger.error(f"RAG docs directory not found: {RAG_DOCS_DIR}")
        return False

    # Check if datasource already exists
    existing_datasources = await get_datasources()
    databricks_datasource = None
    for ds in existing_datasources:
        if ds['name'] == 'Databricks':
            databricks_datasource = ds
            logger.info(f"Found existing Databricks datasource (ID: {ds['id']})")
            break

    # Create datasource if it doesn't exist
    if not databricks_datasource:
        logger.info("Creating new Databricks datasource...")
        databricks_datasource = await create_datasource(
            name="Databricks",
            description="Databricks data warehouse documentation and schema information from dbt RAG docs",
            ds_type=DataSourceType.KNOWLEDGE_BASE.value
        )

        if not databricks_datasource:
            logger.error("Failed to create Databricks datasource")
            return False

        logger.info(f"Created Databricks datasource (ID: {databricks_datasource['id']})")
    else:
        logger.info(f"Using existing Databricks datasource (ID: {databricks_datasource['id']})")

    datasource_id = databricks_datasource['id']

    # Get all markdown files from rag_docs directory
    md_files = list(RAG_DOCS_DIR.glob("*.md"))
    logger.info(f"Found {len(md_files)} markdown files in {RAG_DOCS_DIR}")

    if not md_files:
        logger.warning("No markdown files found to import")
        return False

    # Import each file
    success_count = 0
    fail_count = 0

    for file_path in sorted(md_files):
        original_filename = file_path.name
        logger.info(f"Importing file: {original_filename}")

        success = await import_file_to_datasource(
            file_path=file_path,
            datasource_id=datasource_id,
            original_filename=original_filename
        )

        if success:
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"Import completed: {success_count} succeeded, {fail_count} failed")
    logger.info(f"Databricks datasource (ID: {datasource_id}) is ready for use in the web interface")

    return True


async def main():
    """Entry point"""
    try:
        success = await create_and_import_databricks_datasource()
        if success:
            logger.info("Script completed successfully")
            sys.exit(0)
        else:
            logger.error("Script completed with errors")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

