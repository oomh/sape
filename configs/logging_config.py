"""
Simple logging setup for M-Pesalytics.
"""

import logging
import sys
from pathlib import Path


def setup_logging():
    """
    Set up logging for the entire app.

    Call this ONCE at the start

    What it does:
    1. Creates a 'logs' folder if it doesn't exist
    2. Saves ALL logs to 'logs/mpesalytics.log' file
    3. Shows INFO and above in the terminal (less noise)

    Example:
        from src.config import setup_logging
        setup_logging()  # That's it!
    """
    # Make sure logs directory exists
    log_dir = Path("logs")
    # log_dir.mkdir(exist_ok=True)

    # Create the format for log messages
    # Example output: "2024-01-15 10:30:45 - INFO - Loading PDF: statement.pdf"
    log_format = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Get the root logger (the main one)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture everything

    # Remove any existing handlers (prevents duplicates)
    logger.handlers.clear()

    # Handler 1: Print to terminal (console)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)  # Only show INFO and above (not DEBUG)
    console.setFormatter(log_format)
    logger.addHandler(console)

    # Handler 2: Save to file (everything, including DEBUG)
    # file_handler = logging.FileHandler(
    #     log_dir / "mpesalytics.log",
    #     mode="w",  # 'w' = overwrite (fresh logs each run)
    #     encoding="utf-8",
    # )
    # file_handler.setLevel(logging.DEBUG)  # Save everything to file
    # file_handler.setFormatter(log_format)
    # logger.addHandler(file_handler)

    # logger.info("Logging system initialized")


def get_logger(name):
    """
    Get a logger for the module.

    Use this in each of the Python files.

    Args:
        name: Usually just pass __name__ (the module name)

    Returns:
        A logger you can use

    Example in the file:
        from src.config import get_logger
        logger = get_logger(__name__)

        logger.info("This is an info message")
        logger.warning("Something might be wrong")
        logger.error("Something failed!")
    """
    return logging.getLogger(name)


# ------------------------------------------------------------------------------
# LOG LEVELS MIND MAP (from least to most important)
# ------------------------------------------------------------------------------
#
# logger.debug("Very detailed info, only useful when debugging")
#   → Only saved to file, not shown in terminal
#   → Example: "Regex pattern matched: Customer transfer"
#
# logger.info("Normal informational message")
#   → Shown in terminal AND saved to file
#   → Example: "Loading PDF: statement.pdf"
#
# logger.warning("Something unexpected, but app can continue")
#   → Shown in terminal AND saved to file
#   → Example: "No transactions found for date range"
#
# logger.error("Something failed, but app might recover")
#   → Shown in terminal AND saved to file
#   → Example: "Failed to load PDF: file not found"
#
# logger.critical("App is about to crash!")
#   → Shown in terminal AND saved to file
#   → Example: "Database connection lost"
# ------------------------------------------------------------------------------
