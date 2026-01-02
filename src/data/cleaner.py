"""
Data cleaning and standardization module for M-Pesa transactions.

taking raw PDF data (from loader.py) and:
1. Validating the DataFrame has data
2. Filtering for M-Pesa transaction columns (statement-specific logic)
3. Cleaning and converting data types (dates, numbers, strings)
4. Extracting transaction type and entity from details
5. Splitting type into type_class and type_desc for categorization

By handling M-Pesa-specific filtering here (instead of in loader.py),
I'm keeping the loader generic and reusable for other statement types.
"""

import pandas as pd
import re
from typing import Tuple

from configs import get_logger
from .exceptions import DataCleaningError

# Get logger for this module
logger = get_logger(__name__)

# Expected columns in M-Pesa statement tables (moved from loader.py for better separation of concerns)
EXPECTED_COLUMNS = [
    "Receiptno.",
    "ReceiptNo",
    "CompletionTime",
    "Details",
    "PaidIn",
    "Withdrawn",
]

# compiling regex pattern once (faster than compiling every time)
DETAILS_PATTERN = re.compile(r"(.*?)(?<!\S)(?: *)-(?: *)\s(?=\S)(.*)", re.IGNORECASE)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    cleaning and standardizing M-Pesa transaction data.

    This function:
    1. Validates the DataFrame has data
    2. Filters for M-Pesa transaction columns (moved from loader.py)
    3. Converts data types (dates, numbers, strings)
    4. Extracts transaction type and entity from details
    5. Splits type into type_class and type_desc

    Args:
        df: Raw DataFrame from PDF loader (can contain any tables)

    Returns:
        Cleaned DataFrame with columns:
        - receiptno (string)
        - completiontime (datetime)
        - details (string)
        - paidin (float)
        - withdrawn (float)
        - type (string) - transaction type
        - entity (string) - who/what was involved
        - type_class (string) - first 4 words of type
        - type_desc (string) - remaining words of type

    Raises:
        DataCleaningError: If DataFrame is empty or doesn't contain M-Pesa columns

    Example:
        >>> raw_df = load_pdf_data("statement.pdf")
        >>> clean_df = clean_data(raw_df)
        >>> print(clean_df.dtypes)
    """
    logger.info("Starting data cleaning")

    # Validate input
    if df is None or df.empty:
        error_msg = "DataFrame is empty - nothing to clean"
        logger.error(error_msg)
        raise DataCleaningError(error_msg)

    logger.debug(f"Input shape: {df.shape}")

    # Filter for M-Pesa transaction rows (moved from loader.py)
    # checking if DataFrame has M-Pesa expected columns
    df_columns = [str(col).strip() for col in df.columns]
    has_expected_cols = any(
        expected.lower().replace(" ", "") in df_columns for expected in EXPECTED_COLUMNS
    )

    if not has_expected_cols:
        error_msg = (
            f"No M-Pesa transaction columns found in data. "
            f"Expected columns like: {', '.join(EXPECTED_COLUMNS[:4])}... "
            f"Found columns: {', '.join(df.columns[:5])}"
        )
        logger.error(error_msg)
        raise DataCleaningError(error_msg)

    logger.info("M-Pesa transaction columns detected")

    # Handle duplicate column names (keep only first occurrence)
    if df.columns.duplicated().any():
        logger.warning(
            f"Found duplicate columns: {df.columns[df.columns.duplicated()].tolist()}"
        )
        df = df.loc[:, ~df.columns.duplicated(keep="last")]
        logger.info(f"After removing duplicates: {df.columns}")

    # Work on a copy
    df_clean = df.copy()

    # Clean and convert data types
    df_clean = _clean_column_values(df_clean)
    columns2 = df_clean.columns

    logger.info(f"After Cleaning the data frame has these columns {columns2}")

    # Date range logging
    date_range = (
        f"{df_clean['completiontime'].min().strftime('%b %d, %Y')} → "
        f"{df_clean['completiontime'].max().strftime('%b %d, %Y')}"
    )
    logger.info(f"Date range: {date_range}")

    # Extract transaction info
    df_clean = _extract_transaction_info(df_clean)

    # Log summary
    logger.info(f"Cleaning complete. Final shape: {df_clean.shape}")

    return df_clean


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _clean_column_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    cleaning and converting column values to proper types.

    - receiptno: Convert to string
    - completiontime: Parse as datetime
    - details: Clean whitespace
    - paidin: Convert to float, remove commas
    - withdrawn: Convert to float, remove commas, take absolute value

    Args:
        df: DataFrame with raw values

    Returns:
        DataFrame with cleaned values
    """
    logger.debug("Cleaning column values and converting types")
    columns = df.columns
    logger.info(f"Columns found: {columns}")

    # Standardize column names to lowercase first
    df.columns = df.columns.str.lower().str.strip()

    df = df[~pd.isnull(df["completiontime"])]

    # M-Pesa statements generated by the M-PESA app don't have this fullstop but those sent to your email do
    if "receiptno." in df.columns:
        df = df.rename(columns={"receiptno.": "receiptno"})

    # Saw this error in aroound 40% of the statements i worked with
    if "withdraw\nn" in df.columns:
        df = df.rename(columns={"withdraw\nn": "withdrawn"})

    # Filter to keep only expected M-Pesa columns (using EXPECTED_COLUMNS constant)
    # Normalize EXPECTED_COLUMNS to lowercase for matching
    expected_cols_lower = list(
        set([col.lower().replace(".", "") for col in EXPECTED_COLUMNS])
    )

    # Find which expected columns are present
    present_cols = [col for col in expected_cols_lower if col in df.columns]

    if not present_cols:
        logger.error(
            f"None of the expected columns found after standardization. Columns present: {df.columns.tolist()}"
        )
        raise DataCleaningError(
            "Expected M-Pesa columns not found after standardization"
        )

    # Get unexpected columns that will be removed
    unexpected_cols = [col for col in df.columns if col not in expected_cols_lower]

    if unexpected_cols:
        logger.info(
            f"Removing {len(unexpected_cols)} unexpected column(s): {unexpected_cols}"
        )

    # Keep only expected columns
    df = df[present_cols]
    logger.info(f"Kept only M-Pesa columns: {present_cols}")

    # Receipt number as string
    df["receiptno"] = df["receiptno"].astype("string")

    # Date/time as datetime
    df["completiontime"] = pd.to_datetime(df["completiontime"], errors="coerce")

    # checking for failed date conversions and logging them
    null_dates = df["completiontime"].isnull().sum()
    if null_dates > 0:
        logger.warning(f"{null_dates} dates could not be parsed")

    # Withdrawn amount (money out)
    # removing commas, handling empty/missing, converting to number, making positive
    df["withdrawn"] = (
        pd.to_numeric(
            df["withdrawn"]
            .astype(str)
            .str.replace(",", "")  # Remove thousands separator (1,500 → 1500)
            .replace(["", "-", "N/A", "nan"], "0"),  # Handle missing values
            errors="coerce",
        )
        .abs()  # Make sure all values are positive
        .fillna(0)  # Fill any remaining NaN with 0
    )

    # Paid in amount (money in)
    df["paidin"] = pd.to_numeric(
        df["paidin"]
        .astype(str)
        .str.replace(",", "")
        .replace(["", "-", "N/A", "nan"], "0"),
        errors="coerce",
    ).fillna(0)

    # cleaning details text (collapsing multiple spaces into single space)
    if "details" in df.columns:
        df["details"] = df["details"].astype(str).str.replace(r"\s+", " ", regex=True)
        
        # Proper capitalization of details: first letter uppercase, rest lowercase
        df["details"] = df["details"].str.title()

    return df


def _extract_transaction_info(df: pd.DataFrame) -> pd.DataFrame:
    """
    extracting transaction type and entity from details column.

    M-Pesa details format: "Transaction type - Entity"
    Example: "Customer transfer to 254712345678 - JOHN DOE"

    I'm extracting into:
    - type: "Customer transfer to 254712345678"
    - entity: "JOHN DOE"
    - type_class: "Customer transfer to 254712345678" (first 4 words)
    - type_desc: "" (remaining words)

    Args:
        df: DataFrame with details column

    Returns:
        DataFrame with added type, entity, type_class, type_desc columns
    """
    logger.debug("Extracting transaction type and entity")

    # splitting details into type and entity
    df[["type", "entity"]] = df["details"].apply(lambda x: pd.Series(split_details(x)))

    # splitting type into type_class and type_desc
    df[["type_class", "type_desc"]] = df["type"].apply(
        lambda x: pd.Series(split_type(x))
    )

    return df


def split_details(details_text: str) -> Tuple[str, str]:
    """
    parsing transaction details into type and entity.

    M-Pesa format: "Transaction type - Entity name"
    Example: "Customer transfer to 254712345678 - JOHN DOE"
    Returns: ("Customer transfer to 254712345678", "JOHN DOE")

    Args:
        details_text: Raw transaction details string

    Returns:
        Tuple of (transaction_type, entity_name)
    """
    match = DETAILS_PATTERN.search(str(details_text))

    if match:
        return match.group(1).strip(), match.group(2).strip()
    else:
        # No separator found, return same for both
        return details_text, details_text


def split_type(transaction_type: str) -> Tuple[str, str]:
    """
    splitting transaction type into class and description.

    I'm taking first 4 words as "class", rest as "description".
    The categorizer uses this for pattern matching.

    Example: "Customer transfer to 254712345678 from account"
    Returns: ("Customer transfer to 254712345678", "from account")

    Args:
        transaction_type: Transaction type string

    Returns:
        Tuple of (type_class, type_description)
    """
    if pd.isna(transaction_type):
        return "", ""

    words = str(transaction_type).split(" ")
    type_class = " ".join(words[0:4])  # First 4 words
    type_desc = " ".join(words[4:])  # Everything else

    return type_class, type_desc


# For testing this module independently
if __name__ == "__main__":
    from configs import setup_logging

    setup_logging()

    print("Data Cleaner Module")
    print("=" * 60)
    print("This cleans raw data from the PDF loader.")
    print("\nUsage:")
    print("  from src.data import load_pdf_data, clean_data")
    print("  raw_df = load_pdf_data('statement.pdf')")
    print("  clean_df = clean_data(raw_df)")
    print("=" * 60)
