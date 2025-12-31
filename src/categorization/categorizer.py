"""
YAML-based transaction categorizer.

reading category definitions from config/categories.yaml
You can add/modify categories by editing the YAML file - no code changes needed!
"""

import pandas as pd
import yaml
import re
import os
from typing import Dict, List, Optional, Tuple

from configs import get_logger

logger = get_logger(__name__)


class TransactionCategorizer:
    """
    I'm categorizing M-Pesa transactions based on YAML configuration.

    Categories are defined in config/categories.yaml and can be customized by you
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        custom_categories: Optional[List[Dict]] = None,
    ):
        """
        Initialize categorizer with category definitions from YAML.

        Args:
            config_path: Path to categories.yaml (optional, uses default if not provided)
            custom_categories: List of custom category definitions (optional, session-only)
        """
        if config_path is None:
            # Default path relative to project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(
                current_dir, "..", "..", "configs", "categories.yaml"
            )

        logger.info(f"Loading category definitions from: {config_path}")
        self.category_definitions = self._load_categories(config_path)

        # Add custom categories if provided (these will be checked first)
        if custom_categories:
            logger.info(
                f"Adding {len(custom_categories)} custom categories from session"
            )
            # Insert custom categories at the beginning so they're checked first
            self.category_definitions = custom_categories + self.category_definitions

        self.categories = {cat["name"]: [] for cat in self.category_definitions}

        # Add special categories (only add these once at the start)
        self.categories["NoDetails"] = []
        self.categories["uncategorized"] = []

        # Entity processing patterns (from v1) - compiling regex patterns for performance
        self.masked_phone_pattern = re.compile(r"\*+")
        self.paybill_pattern = re.compile(r"(.*?)(?:\s+Acc\.\s+(.*)|$)")
        self.business_payment_pattern = re.compile(
            r"(.*?)(?:\s+(?:via).*?(?:is)\s+(.*)|$)", re.IGNORECASE
        )

        logger.info(
            f"Loaded {len(self.category_definitions)} total category definitions"
        )

    def categorize_transactions(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        categorizing all transactions in a DataFrame.

        Transactions can match multiple categories - they will be added to ALL matching categories.

        Args:
            df: Cleaned DataFrame with columns: details, type_desc, type_class, entity, etc.

        Returns:
            Dictionary mapping category names to DataFrames of transactions
        """
        logger.info(f"Categorizing {len(df)} transactions")

        # Single pass through all transactions
        for _, row in df.iterrows():
            matched_categories = self.categorize_transaction(row)

            # Add transaction to all matched categories
            for category_data in matched_categories:
                category = category_data["category"]
                if category in self.categories:
                    self.categories[category].append(category_data)

        # Convert lists to DataFrames
        categorized_dfs = {}
        for category, transactions in self.categories.items():
            if transactions:
                categorized_dfs[category] = pd.DataFrame(transactions)
                logger.debug(f"{category}: {len(transactions)} transactions")
            else:
                categorized_dfs[category] = pd.DataFrame()

        # Log summary
        active_categories = len([c for c in categorized_dfs.values() if len(c) > 0])
        logger.info(f"Categorization complete! {active_categories} active categories")

        if len(categorized_dfs.get("uncategorized", pd.DataFrame())) > 0:
            logger.warning(
                f"{len(categorized_dfs['uncategorized'])} uncategorized transactions"
            )
            logger.debug(
                f"Uncategorized type_classes: {categorized_dfs['uncategorized']['type_class'].unique()}"
            )
        else:
            logger.info("All transactions successfully categorized!")

        return categorized_dfs

    def categorize_transaction(self, row: pd.Series) -> List[Dict]:
        """
        categorizing a single transaction using YAML-defined patterns.

        Transactions can match multiple categories - returns ALL matches.

        Args:
            row: DataFrame row with transaction data

        Returns:
            List of dictionaries with categorized transaction data (one per matched category)
        """
        # Extract fields (lowercase for matching)
        details = str(row["details"]).lower()
        type_desc = str(row["type_desc"]).lower()
        type_class = str(row["type_class"]).lower()
        entity = str(row["entity"])

        # Base transaction data
        base_transaction_data = {
            "receiptno": row["receiptno"],
            "completiontime": row["completiontime"],
            "details": row["details"],
            "paidin": row["paidin"],
            "withdrawn": row["withdrawn"],
            "entity": entity,
            "type_class": row["type_class"],
            "type_desc": row["type_desc"],
            "processed_entity": entity,
            "is_charge": "charge" in type_desc or "charge" in details,
            "category": None,
            "subcategory": None,
        }

        # Handle special case: no details
        if details == "nan" or not details:
            no_details_data = base_transaction_data.copy()
            no_details_data["category"] = "NoDetails"
            return [no_details_data]

        # Collect all matching categories
        matched_categories = []

        # Try to match against category definitions
        for cat_def in self.category_definitions:
            if self._matches_pattern(
                details, type_desc, type_class, entity, cat_def["patterns"]
            ):
                # Create a copy for this category
                transaction_data = base_transaction_data.copy()
                transaction_data["category"] = cat_def["name"]

                # Process entity based on category type
                transaction_data = self._process_entity(
                    transaction_data, cat_def["name"]
                )

                logger.debug(f"Matched category: {cat_def['name']}")
                matched_categories.append(transaction_data)

        # If no matches found, add to uncategorized
        if not matched_categories:
            uncategorized_data = base_transaction_data.copy()
            uncategorized_data["category"] = "uncategorized"
            logger.debug(
                f"Uncategorized: details={details[:50]}, type_class={type_class}"
            )
            matched_categories.append(uncategorized_data)

        return matched_categories

    # ============================================================================
    # HELPER FUNCTIONS
    # ============================================================================

    def _load_categories(self, config_path: str) -> List[Dict]:
        """
        loading category definitions from YAML file.

        Args:
            config_path: Path to categories.yaml

        Returns:
            List of category definition dictionaries
        """
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            categories = config.get("categories", [])
            logger.debug(f"Found {len(categories)} categories in config")

            return categories

        except FileNotFoundError:
            logger.error(f"Category config file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise

    def _matches_pattern(
        self, details: str, type_desc: str, type_class: str, entity: str, patterns: Dict
    ) -> bool:
        """
        checking if transaction matches the pattern definition.

        Args:
            details: Transaction details (lowercase)
            type_desc: Transaction type description (lowercase)
            type_class: Transaction type class (lowercase)
            entity: Transaction entity (original case)
            patterns: Pattern definition from YAML

        Returns:
            True if all pattern conditions match
        """
        fields = {
            "details": details,
            "type_desc": type_desc,
            "type_class": type_class,
            "entity": entity.lower(),
        }

        # Check each field pattern (AND logic between fields)
        for field_name, field_patterns in patterns.items():
            if field_name not in fields:
                continue

            field_value = fields[field_name]

            # Check if this field matches (OR logic within field)
            if not self._matches_field_pattern(field_value, field_patterns):
                return False  # This field didn't match, so overall pattern fails

        # All fields matched!
        return True

    def _matches_field_pattern(self, field_value: str, field_patterns: Dict) -> bool:
        """
        checking if a field value matches the pattern conditions.

        Args:
            field_value: The field value to check (lowercase)
            field_patterns: Pattern conditions (contains, equals, etc.)

        Returns:
            True if field matches any of the pattern conditions
        """
        # Handle "contains" patterns (OR logic - match ANY)
        if "contains" in field_patterns:
            contains_list = field_patterns["contains"]
            if any(pattern in field_value for pattern in contains_list):
                return True

        # Handle "equals" pattern
        if "equals" in field_patterns:
            if field_value == field_patterns["equals"]:
                return True

        # Handle "startswith" patterns (OR logic - match ANY)
        if "startswith" in field_patterns:
            startswith_list = field_patterns["startswith"]
            if any(field_value.startswith(pattern) for pattern in startswith_list):
                return True

        # Handle "startswith_numeric" pattern - checking if field starts with a digit
        if "startswith_numeric" in field_patterns:
            if (
                field_patterns["startswith_numeric"]
                and field_value
                and field_value[0].isdigit()
            ):
                return True

        # Handle "not_starts_with" pattern
        if "not_starts_with" in field_patterns:
            if not field_value.startswith(field_patterns["not_starts_with"]):
                return True

        # If we got here and there were patterns defined, none matched
        if field_patterns:
            return (
                "contains" not in field_patterns
                and "equals" not in field_patterns
                and "startswith" not in field_patterns
                and "startswith_numeric" not in field_patterns
            )

        # No patterns defined for this field
        return True

    def _process_entity(self, transaction_data: Dict, category: str) -> Dict:
        """
        processing entity based on category type (extracting names, accounts, etc.).

        Args:
            transaction_data: Transaction data dictionary
            category: Category name

        Returns:
            Updated transaction data with processed_entity and account_no
        """
        entity = transaction_data["entity"]

        # Categories that need entity processing
        money_transfer_cats = [
            "Send Money",
            "Received (Individuals)",
            "Received (Business)",
            "Customer Payment",
            "Business Transfer (SME)",
            "Business Transfer (Customer)",
        ]

        if category in money_transfer_cats:
            # checking if entity is a phone number (starts with digit or contains asterisks)
            if entity and (entity[0].isdigit() or "*" in entity):
                name, phone = self.process_masked_phone(entity)
                transaction_data["processed_entity"] = name
                transaction_data["account_no"] = phone
            else:
                # Business entity
                name, extra_info = self.process_business_and_account(entity)
                transaction_data["processed_entity"] = name
                transaction_data["account_no"] = extra_info

        # PayBill needs account extraction
        elif category == "PayBillPayments":
            business_name, account_no = self.extract_paybill_details(entity)
            transaction_data["processed_entity"] = business_name
            transaction_data["account_no"] = account_no

        # Airtime/Pochi - just extract name from masked phone
        elif category in ["airtime_bundle", "Pochi"]:
            if entity and (entity[0].isdigit() or "*" in entity):
                name, _ = self.process_masked_phone(entity)
                transaction_data["processed_entity"] = name

        return transaction_data

    def process_masked_phone(self, entity: str) -> Tuple[str, str]:
        """extracting the name from a masked phone number."""
        if pd.isna(entity) or entity == "":
            return entity, ""

        if self.masked_phone_pattern.search(entity):
            parts = entity.split(" ", 1)
            if len(parts) > 1:
                return parts[1].title(), parts[0].title()
            return parts[0].title(), ""

        return entity.title(), ""

    def process_business_and_account(self, entity: str) -> Tuple[str, str]:
        """extracting business name and extra info."""
        if pd.isna(entity) or entity == "":
            return entity, ""

        match = self.business_payment_pattern.search(entity)
        if match:
            business_name = match.group(1).strip() if match.group(1) else ""
            extra_info = match.group(2).strip() if match.group(2) else ""
            return business_name, extra_info

        return entity, ""

    def extract_paybill_details(self, entity: str) -> Tuple[str, str]:
        """extracting business name and account number from paybill entity."""
        if pd.isna(entity) or entity == "":
            return entity, ""

        match = self.paybill_pattern.search(entity)
        if match:
            business_name = match.group(1).strip()
            account_no = match.group(2).strip() if match.group(2) else ""
            return business_name, account_no

        return entity, ""


# Convenience function for easy usage
def categorize_transactions(
    df: pd.DataFrame, config_path: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """
    categorizing transactions using YAML configuration.

    Args:
        df: Cleaned DataFrame with transaction data
        config_path: Optional path to categories.yaml

    Returns:
        Dictionary mapping category names to DataFrames

    Example:
        >>> from src.data import load_pdf_data, clean_data
        >>> from src.categorization import categorize_transactions
        >>>
        >>> raw_df = load_pdf_data("statement.pdf")
        >>> clean_df = clean_data(raw_df)
        >>> categorized = categorize_transactions(clean_df)
        >>> print(categorized["SendMoney"].head())
    """
    categorizer = TransactionCategorizer(config_path)
    return categorizer.categorize_transactions(df)


# For testing
if __name__ == "__main__":
    from configs import setup_logging

    setup_logging()

    print("Transaction Categorizer")
    print("=" * 60)
    print("This categorizes transactions based on config/categories.yaml")
    print("\nTo add custom categories:")
    print("1. Edit config/categories.yaml")
    print("2. Add your category definition")
    print("3. Restart the app")
    print("=" * 60)
