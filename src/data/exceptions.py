"""
Custom exceptions for data loading and processing.

These give users clear error messages instead of confusing technical errors.
"""


class PDFLoadError(Exception):
    """
    Base exception for PDF loading errors.

    Use this when something goes wrong with PDF files.
    """

    pass


class PDFPasswordError(PDFLoadError):
    """
    Raised when PDF password is incorrect or missing.

    Example:
        raise PDFPasswordError("This PDF requires a password")
    """

    pass


class PDFParsingError(PDFLoadError):
    """
    Raised when PDF structure is not what we expect.

    Example:
        raise PDFParsingError("No transaction tables found in PDF")
    """

    pass


class DataCleaningError(Exception):
    """
    Raised when data cleaning fails.

    Example:
        raise DataCleaningError("Missing required column: Receipt No.")
    """

    pass
