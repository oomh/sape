"""
Lightweight PDF data loader using tabula-py.

This is a lighter alternative to loader.py (which uses Docling).
Tabula is less hardware-intensive but requires Java to be installed.

Both loaders have identical interfaces - you can swap between them
by changing which one you import.

Uses tabula-py instead of Docling (no heavy ML models needed!).
Requires: Java Runtime Environment (JRE) installed on system.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Union
from tabula.io import read_pdf
from io import BytesIO

from configs import get_logger
from .exceptions import PDFPasswordError, PDFLoadError, PDFParsingError

# Get logger for this module
logger = get_logger(__name__)


def tabula_load_pdf_data(
    pdf_path: Union[str, Path], password: Optional[str] = None
) -> pd.DataFrame:
    """
    Load table data from a PDF file using tabula-py (lightweight loader).

    This function:
    1. Opens the PDF using tabula-py (handles passwords natively)
    2. Extracts all tables from all pages
    3. Combines them into one DataFrame

    Note: Column filtering for specific statement types (e.g., M-Pesa)
    is done in cleaner.py, making this loader reusable for different PDFs.

    Args:
        pdf_path: Path to the PDF file (can be string, Path object, or file-like object)
        password: PDF password if the file is protected (optional, passed to tabula)

    Returns:
        DataFrame with combined table data from all tables in PDF

    Raises:
        PDFParsingError: If no tables found in PDF
        PDFLoadError: For other PDF loading errors (including password errors)

    Requirements:
        Java Runtime Environment (JRE) must be installed for tabula-py to work.
        Install: sudo apt-get install default-jre (Linux)
                 brew install java (macOS)

    Example:
        >>> df = tabula_load_pdf_data("statement.pdf", password="12345")
        >>> print(df.head())
    """
    try:
        logger.info("Using tabula-py (lightweight) PDF loader")

        # Handle Streamlit UploadedFile or file-like objects
        if hasattr(pdf_path, "read"):
            file_name = getattr(pdf_path, "name", "uploaded.pdf")
            logger.info(f"Loading PDF from uploaded file: {file_name}")

            # Read bytes and create BytesIO (tabula handles passwords directly)
            pdf_bytes = pdf_path.read()  # type: ignore
            pdf_to_read = BytesIO(pdf_bytes)

        else:
            # It's a path (string or Path object)
            logger.info(f"Loading PDF: {pdf_path}")
            pdf_to_read = str(pdf_path)

        # Extract tables using tabula-py (pass password if provided)
        logger.debug("Extracting tables with tabula-py (lattice mode)")

        # Try lattice mode first (better for tables with clear borders)
        try:
            df_list = read_pdf(
                pdf_to_read,
                pages="all",
                lattice=True,
                multiple_tables=True,
                silent=True,  # Suppress Java output
                password=password,  # Tabula handles password-protected PDFs
            )
        except Exception as lattice_error:
            # Fallback to stream mode (better for tables without borders)
            logger.debug(f"Lattice mode failed ({lattice_error}), trying stream mode")
            df_list = read_pdf(
                pdf_to_read,
                pages="all",
                lattice=False,
                stream=True,
                multiple_tables=True,
                guess=True,
                silent=True,
                password=password,  # Tabula handles password-protected PDFs
            )

        if not df_list:
            error_msg = "No tables found in PDF"
            logger.warning(error_msg)
            raise PDFParsingError(error_msg)

        logger.info(f"Found {len(df_list)} tables in the PDF file")

        # Filter out empty DataFrames
        valid_tables = [
            df for df in df_list if isinstance(df, pd.DataFrame) and not df.empty
        ]

        if not valid_tables:
            error_msg = "All extracted tables are empty"
            logger.warning(error_msg)
            raise PDFParsingError(error_msg)

        logger.debug(f"Filtered to {len(valid_tables)} non-empty tables")

        # Combine all tables
        combined_df = pd.concat(valid_tables, ignore_index=True)

        # Clean up column names (lowercase, no spaces) - same as Docling loader
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

    except FileNotFoundError as e:
        error_msg = f"PDF file not found: {pdf_path}"
        logger.error(error_msg)
        raise PDFLoadError(error_msg) from e

    except ImportError as e:
        error_msg = (
            "tabula-py requires Java Runtime Environment (JRE). "
            "Install Java and try again. "
            f"Error: {str(e)}"
        )
        logger.error(error_msg)
        raise PDFLoadError(error_msg) from e

    except Exception as e:
        # Catch any other errors
        error_msg = f"Unexpected error loading PDF with tabula: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise PDFLoadError(error_msg) from e


# For testing this module independently
if __name__ == "__main__":
    from configs import setup_logging

    # Set up logging
    setup_logging()

    # Test with a sample PDF (you'll need to provide a real path)
    print("Tabula PDF Loader Test")
    print("=" * 60)
    print("This is a lightweight alternative to the Docling loader.")
    print("Requires: Java Runtime Environment (JRE)")
    print("")
    print("Usage:")
    print("  from src.data import tabulaloader")
    print(
        "  df = tabulaloader.tabula_load_pdf_data('path/to/document.pdf', password='12345')"
    )
    print("=" * 60)
