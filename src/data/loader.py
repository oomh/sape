"""
Generic PDF data loader using Docling.

handling loading table data from PDF files.
It's now generic and can load any PDF with tables - statement-specific
filtering (e.g., M-Pesa columns) is handled in cleaner.py.

Using Docling instead of tabula-py (no Java needed!).
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Union
from docling.document_converter import DocumentConverter
from io import BytesIO
import pikepdf
import tempfile
import os

from configs import get_logger
from .exceptions import PDFLoadError, PDFPasswordError, PDFParsingError

# Get logger for this module
logger = get_logger(__name__)


def load_pdf_data(
    pdf_path: Union[str, Path], password: Optional[str] = None
) -> pd.DataFrame:
    """
    loading table data from a PDF file (generic loader).

    This function:
    1. Opens the PDF using Docling
    2. Extracts all tables
    3. Combines them into one DataFrame

    Note: Column filtering for specific statement types (e.g., M-Pesa)
    is done in cleaner.py, making this loader reusable for different PDFs.

    Args:
        pdf_path: Path to the PDF file (can be string or Path object)
        password: PDF password if the file is protected (optional)

    Returns:
        DataFrame with combined table data from all tables in PDF

    Raises:
        PDFPasswordError: If PDF is password protected but no password provided
        PDFParsingError: If no tables found in PDF
        PDFLoadError: For other PDF loading errors

    Example:
        >>> df = load_pdf_data("statement.pdf", password="12345")
        >>> print(df.head())
    """

    temp_file_path = None
    try:
        # Initialize Docling converter
        logger.debug("Initializing Docling document converter")
        converter = DocumentConverter()

        # Handle Streamlit UploadedFile which is a file-like object (that docling can't handle)
        if hasattr(pdf_path, "read"):
            # It's a file-like object (Streamlit UploadedFile)
            file_name = getattr(pdf_path, "name", "uploaded.pdf")
            logger.info(f"Loading PDF from uploaded file: {file_name}")

            # Read bytes
            pdf_bytes = pdf_path.read()  # type: ignore[attr-defined]

            # If password provided, decrypt to temp file
            if password:
                temp_file_path = _decrypt_pdf_to_temp(pdf_bytes, password, file_name)
                result = converter.convert(temp_file_path)
            else:
                # Write to temp file (needed for Docling)
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".pdf", delete=False
                ) as temp_file:
                    temp_file.write(pdf_bytes)
                    temp_file_path = temp_file.name
                result = converter.convert(temp_file_path)
        else:
            # It's a path (string or Path object)
            logger.info(f"Loading PDF: {pdf_path}")

            # Decrypt if password provided
            if password:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                temp_file_path = _decrypt_pdf_to_temp(
                    pdf_bytes, password, str(pdf_path)
                )
                result = converter.convert(temp_file_path)
            else:
                result = converter.convert(pdf_path)

        # extracting tables from the document using Docling's export_to_dataframe()
        logger.debug("Extracting tables from document")
        all_tables = []
        for table in result.document.tables:
            df = pd.DataFrame(table.export_to_dataframe())
            all_tables.append(df)

        if not all_tables:
            error_msg = "No tables found in PDF"
            logger.warning(error_msg)
            raise PDFParsingError(error_msg)

        logger.info(f"Found {len(all_tables)} tables in the PDF file")

        # Combine all tables (filtering will be done in cleaner.py for M-Pesa specific logic)
        combined_df = pd.concat(all_tables, ignore_index=True)

        # cleaning up column names (lowercase, no spaces)
        combined_df.columns = (
            combined_df.columns.str.strip()
            .str.lower()
            .str.replace(r"\s+", "", regex=True)
        )

        logger.info(f"Successfully loaded {len(combined_df)} rows from PDF tables")
        logger.debug(f"DataFrame shape: {combined_df.shape}")

        return combined_df

    except PDFPasswordError:
        # Re-raise password errors as-is
        raise

    except PDFParsingError:
        # Re-raise parsing errors as-is
        raise

    except Exception as e:
        # Catch any other errors
        error_msg = f"Unexpected error loading PDF: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise PDFLoadError(error_msg) from e

    finally:
        # Clean up temporary file if it was created
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temporary file {temp_file_path}: {e}"
                )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _decrypt_pdf_to_temp(pdf_bytes: bytes, password: str, filename: str) -> str:
    """
    decrypting a password-protected PDF and saving to a temporary file.

    Args:
        pdf_bytes: PDF file bytes
        password: PDF password
        filename: Filename for error messages

    Returns:
        Path to temporary decrypted PDF file

    Raises:
        PDFPasswordError: If password is incorrect
        PDFLoadError: If decryption fails for other reasons
    """
    try:
        logger.debug("Attempting to decrypt PDF")

        # Open encrypted PDF
        with pikepdf.open(bio, password=password) as pdf:

            # Save decrypted version to temporary file
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".pdf", delete=False
            ) as temp_file:
                pdf.save(temp_file.name)
                temp_path = temp_file.name

        logger.info(f"PDF successfully decrypted to temporary file: {temp_path}")
        return temp_path

    except pikepdf.PasswordError:
        error_msg = f"Incorrect password for PDF: {filename}"
        logger.error(error_msg)
        raise PDFPasswordError(error_msg)
    except Exception as e:
        error_msg = f"Error decrypting PDF {filename}: {str(e)}"
        logger.error(error_msg)
        raise PDFLoadError(error_msg) from e


# For testing this module independently
if __name__ == "__main__":
    from configs import setup_logging

    # Set up logging
    setup_logging()

    # Test with a sample PDF (you'll need to provide a real path)
    print("Generic PDF Loader Test")
    print("=" * 60)
    print("This module loads tables from any PDF file.")
    print("Usage:")
    print("  df = load_pdf_data('path/to/document.pdf', password='12345')")
    print("=" * 60)
