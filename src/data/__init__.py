"""
Data loading and processing package.

Two PDF loaders are available:
- loader (Docling): More accurate but hardware-intensive (currently disabled)
- tabulaloader (tabula-py): Lightweight but requires Java

Usage:
    # Option 1: Use tabula (lightweight)
    from src.data import tabula_load_pdf_data, clean_data

    # Option 2: Import specific loader
    from src.data.tabulaloader import tabula_load_pdf_data  # Tabula
"""

from .exceptions import (
    PDFLoadError,
    PDFPasswordError,
    PDFParsingError,
    DataCleaningError,
)
from .tabulaloader import tabula_load_pdf_data  # Tabula loader function
from .cleaner import clean_data

# Make tabula loader available via submodule
from . import tabulaloader  # Tabula loader module

__all__ = [
    # Exceptions
    "PDFLoadError",
    "PDFPasswordError",
    "PDFParsingError",
    "DataCleaningError",
    # Main functions
    "tabula_load_pdf_data",
    "clean_data",
    # Loader modules (for explicit switching)
    "tabulaloader",
]
