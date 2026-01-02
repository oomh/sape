"""
MpesaLens - M-Pesa Statement Analyzer

A Streamlit application for analyzing M-Pesa transaction statements.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple, Dict, List
import yaml
import hashlib
import plotly.graph_objects as go


from configs import setup_logging, get_logger
from src.data import tabula_load_pdf_data, clean_data
from src.categorization import TransactionCategorizer
from src.analysis import Analyzer
from src.ui import display_category_tab, display_error_state, display_empty_state
from src.ui.components import display_transaction_type_overview


import plotly.colors as pc


# Setup logging
setup_logging()
logger = get_logger(__name__)
PALETTES = {}  

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    layout="wide", page_title="MpesaLens: M-Pesa Statement Analyzer", page_icon="💸"
)

# Disable auto-scroll on reruns
st.markdown(
    """
    <style>
        * {
            overflow-anchor: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# SESSION STATE
# ============================================================================


def initialize_session_state():
    """Initialize all session state variables."""
    defaults = {
        "pdf_path": None,
        "pdf_password": "",
        "process_clicked": False,
        "faux_data_clicked": False,
        "disable": {"date": False, "month": False},
        # Caching variables
        "df_cleaned": None,
        "categorized_data": None,
        "current_pdf_hash": None,
        # Custom categories (session-only)
        "custom_categories": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_pdf_hash(pdf_file) -> str | None:
    """
    Generate a hash for the uploaded PDF to detect changes.

    Uses file name and size to create a unique identifier.
    This invalidates cache when a different PDF is uploaded.

    Args:
        pdf_file: Streamlit UploadedFile object

    Returns:
        Hash string representing this specific file
    """
    if pdf_file is None:
        return None

    # Create hash from file name and size
    hash_input = f"{pdf_file.name}_{pdf_file.size}".encode()
    return hashlib.md5(hash_input).hexdigest()


# ============================================================================
# HEADER
# ============================================================================

    
st.image(
    "src/ui/img/batch_banner.png",
    width="stretch"
)
st.logo(
    "src/ui/img/batch_logo.png", 
    size = "large",
)

# ============================================================================
# FILE UPLOAD
# ============================================================================

with st.expander(
    "📁 Upload M-Pesa Statement",
    expanded=not st.session_state.get("process_clicked", False),
):
    with st.form("pdf_upload_form"):
        pdf = st.file_uploader("Upload your M-Pesa statement (PDF)", type=["pdf"])
        password = st.text_input(
            "Enter PDF password (leave blank if not protected)",
            type="password",
        )
        process = st.form_submit_button("Process")
        faux_data = st.form_submit_button("Show Dashboard with faux data")

    if process:
        # Generate hash for the uploaded PDF
        new_pdf_hash = get_pdf_hash(pdf)

        # Check if this is a new PDF (invalidate cache if so)
        if new_pdf_hash != st.session_state.current_pdf_hash:
            logger.info("New PDF detected - invalidating cache")
            st.session_state.df_cleaned = None
            st.session_state.categorized_data = None
            st.session_state.current_pdf_hash = new_pdf_hash

        st.session_state.pdf_path = pdf
        st.session_state.pdf_password = password
        st.session_state.process_clicked = True
        st.session_state.faux_data_clicked = False

    if faux_data:
        # Clear cache when switching to faux data
        st.session_state.df_cleaned = None
        st.session_state.categorized_data = None
        st.session_state.current_pdf_hash = None
        st.session_state.faux_data_clicked = True
        st.session_state.process_clicked = False

# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================


def load_and_process_pdf(
    pdf_file, password: str
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load and clean PDF data with error handling.

    Note: Caching is now handled via session state instead of @st.cache_data
    to allow proper invalidation when new PDFs are uploaded.
    """
    try:
        with st.spinner("Extracting and cleaning your statement..."):
            logger.info("Loading PDF data")
            df = tabula_load_pdf_data(pdf_file, password)

            logger.info("Cleaning data")
            df_cleaned = clean_data(df)

        return df_cleaned, None
    except Exception as e:
        logger.error(f"Error loading/cleaning PDF: {e}")
        return None, str(e)


@st.cache_data(show_spinner="Loading faux data...")
def load_faux_data() -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Load and clean faux data for demo."""
    try:
        faux_path = Path(".streamlit/faux_data.csv")
        if not faux_path.exists():
            return None, "Faux data file not found"

        logger.info("Loading faux data")
        df = pd.read_csv(faux_path)

        # Convert completion_time to datetime
        df["completiontime"] = pd.to_datetime(df["completiontime"])

        logger.info("Cleaning faux data")
        df_cleaned = clean_data(df)

        return df_cleaned, None
    except Exception as e:
        logger.error(f"Error loading faux data: {e}")
        return None, str(e)


def categorize_transactions(
    df_cleaned: pd.DataFrame,
    custom_categories: Optional[List] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Categorize transactions using YAML definitions and custom categories.

    Note: Caching is now handled via session state instead of @st.cache_data
    to allow proper invalidation when new PDFs are uploaded.
    """
    try:
        with st.spinner("Categorizing transactions..."):
            logger.info("Categorizing transactions")
            categorizer = TransactionCategorizer(custom_categories=custom_categories)
            categorized = categorizer.categorize_transactions(df_cleaned)
        return categorized, None
    except Exception as e:
        logger.error(f"Error categorizing transactions: {e}")
        return None, str(e)


@st.cache_data(show_spinner="Applying filters...")
def filter_categorized_data(
    categorized_data: Dict,
    date_filter: Optional[Tuple] = None,
    month_filter: Optional[list] = None,
) -> Dict:
    """Apply date/month filters to categorized data."""
    if not date_filter and not month_filter:
        return categorized_data

    filtered_categories = {}

    for category, df in categorized_data.items():
        if df.empty:
            filtered_categories[category] = df
            continue

        filtered_df = df.copy()

        # Apply date range filter
        if date_filter and len(date_filter) == 2:
            start_date, end_date = date_filter
            mask = (filtered_df["completiontime"] >= pd.to_datetime(start_date)) & (
                filtered_df["completiontime"] <= pd.to_datetime(end_date)
            )
            filtered_df = filtered_df.loc[mask]

        # Apply month filter
        elif month_filter:
            month_mask = (
                filtered_df["completiontime"].dt.strftime("%B_%Y").isin(month_filter)
            )
            filtered_df = filtered_df.loc[month_mask]

        filtered_categories[category] = filtered_df

    return filtered_categories


# ============================================================================
# DATA LOADING
# ============================================================================

# Check which mode we're in
if st.session_state.get("process_clicked") and st.session_state.pdf_path:
    # Check if data is already cached in session state
    if st.session_state.df_cleaned is not None:
        logger.info("Using cached cleaned DataFrame from session state")
        df_cleaned = st.session_state.df_cleaned
    else:
        # Load and clean PDF (first time or cache invalidated)
        logger.info("Loading and processing PDF (not cached)")
        df_cleaned, error = load_and_process_pdf(
            st.session_state.pdf_path, st.session_state.pdf_password
        )

        if error:
            display_error_state(f"Failed to load/clean PDF: {error}")
            st.stop()

        # Cache the cleaned DataFrame in session state
        st.session_state.df_cleaned = df_cleaned
        logger.info("Cached cleaned DataFrame in session state")

elif st.session_state.get("faux_data_clicked"):
    # Check if faux data is already cached
    if st.session_state.df_cleaned is not None:
        logger.info("Using cached faux data from session state")
        df_cleaned = st.session_state.df_cleaned
    else:
        logger.info("Loading faux data (not cached)")
        df_cleaned, error = load_faux_data()

        if error:
            display_error_state(f"Failed to load faux data: {error}")
            st.stop()

        # Cache the faux data
        st.session_state.df_cleaned = df_cleaned
        logger.info("Cached faux data in session state")

else:
    st.info("Please upload your PDF and click 'Process' to continue.")
    st.stop()

# Get date range for display
if df_cleaned is not None:
    if df_cleaned.empty == False:
        start_date = df_cleaned["completiontime"].min().strftime("%b %d, %Y")
        end_date = df_cleaned["completiontime"].max().strftime("%b %d, %Y")
    else:
        display_error_state("No data found in the statement")
        st.stop()

    # Categorize transactions
    # Check if categorized data is already cached in session state
    if st.session_state.categorized_data is not None:
        logger.info("Using cached categorized data from session state")
        categorized_data = st.session_state.categorized_data
    else:
        # Categorize transactions (first time or cache invalidated)
        logger.info("Categorizing transactions (not cached)")
        categorized_data, error = categorize_transactions(
            df_cleaned, custom_categories=st.session_state.custom_categories
        )

        if error:
            display_error_state(f"Failed to categorize transactions: {error}")
            st.stop()

        # Cache the categorized data in session state
        st.session_state.categorized_data = categorized_data
        logger.info("Cached categorized data in session state")

# ============================================================================
# SIDEBAR FILTERS
# ============================================================================


def update_toggles():
    """Update toggle states to ensure mutual exclusivity."""
    st.session_state.disable["month"] = st.session_state.date_filter
    st.session_state.disable["date"] = st.session_state.month_filter


date_filter_value = None
month_filter_value = None


def handle_user_category(
    logger,
    cat_name,
    cat_type,
    cat_description,
    merchant_type,
    color_map,
    match_field,
    match_operator,
    match_values,
    add_advanced,
    match_field_2,
    match_operator_2,
    match_values_2,
    submit,
):
    if submit:
        # Validate inputs
        if not cat_name or not cat_type or not match_values:
            st.error("Please fill in all required fields (*)")
        else:
            try:
                # Parse match values
                values_list = [
                    v.strip().lower()
                    for v in match_values.split(",")
                    if v.strip().lower()
                ]

                # Build pattern dictionary
                patterns = {}

                # Primary pattern
                if match_operator == "contains":
                    patterns[match_field] = {"contains": values_list}
                elif match_operator == "equals":
                    patterns[match_field] = {
                        "equals": (
                            values_list[0] if len(values_list) == 1 else values_list
                        )
                    }
                elif match_operator == "startswith":
                    patterns[match_field] = {"startswith": values_list}

                    # Secondary pattern (if advanced)
                if add_advanced and match_values_2:
                    values_list_2 = [
                        v.strip() for v in match_values_2.split(",") if v.strip()
                    ]
                    if match_operator_2 == "contains":
                        patterns[match_field_2] = {"contains": values_list_2}
                    elif match_operator_2 == "equals":
                        patterns[match_field_2] = {
                            "equals": (
                                values_list_2[0]
                                if len(values_list_2) == 1
                                else values_list_2
                            )
                        }
                    elif match_operator_2 == "startswith":
                        patterns[match_field_2] = {"startswith": values_list_2}

                        # Create category definition
                new_category = {
                    "name": cat_name,
                    "type": cat_type,
                    "description": (
                        cat_description
                        if cat_description
                        else f"{cat_name} transactions"
                    ),
                    "merchant_type": merchant_type,
                    "color_map": color_map,
                    "patterns": patterns,
                }

                # Check if category name already exists in session
                existing_names = [
                    cat["name"] for cat in st.session_state.custom_categories
                ]
                if cat_name in existing_names:
                    st.error(
                        f"Category '{cat_name}' already exists in custom categories."
                    )
                else:
                    # Add to session state
                    st.session_state.custom_categories.append(new_category)

                    # Clear categorized data cache to force re-categorization
                    st.session_state.categorized_data = None

                    st.success(
                        f"✅ Category '{cat_name}' added! Recategorizing transactions..."
                    )
                    st.rerun()

            except Exception as e:
                st.error(f"Error adding category: {str(e)}")
                logger.error(f"Error adding category: {e}")


with st.sidebar:
    st.header("🔍 Filters")

    # Date toggle
    date_toggle = st.toggle(
        "📅 Date Filter",
        key="date_filter",
        on_change=update_toggles,
        disabled=st.session_state.disable["date"],
    )

    # Month toggle
    month_toggle = st.toggle(
        "📆 Month Filter",
        key="month_filter",
        on_change=update_toggles,
        disabled=st.session_state.disable["month"],
    )

    # Date range filter

    if df_cleaned is not None and st.session_state.get("date_filter"):
        date_range = st.date_input(
            "Select Date Range",
            value=[
                df_cleaned["completiontime"].min().date(),
                df_cleaned["completiontime"].max().date(),
            ],
            min_value=df_cleaned["completiontime"].min().date(),
            max_value=df_cleaned["completiontime"].max().date(),
        )
        if len(date_range) == 2:
            date_filter_value = date_range
        else:
            st.warning("Select both dates", icon="⚠️")

    # Month filter
    elif df_cleaned is not None and st.session_state.get("month_filter"):
        # Build a sorted list of unique months in the format "Month_Year" (e.g. "January_2023")
        months = (
            df_cleaned["completiontime"]
            .dt.to_period("M")
            .drop_duplicates()
            .sort_values()
        )
        month_list = months.dt.strftime("%B_%Y").dropna().tolist()
        default_months = (
            month_list[:3] if len(month_list) >= 3 else month_list
        )  # First three months are already selected
        month_filter_value = st.segmented_control(
            "Select Months",
            options=month_list,
            default=default_months,
            selection_mode="multi",
        )
        if not month_filter_value:
            month_filter_value = None
    else:
        st.info(f"💡 Showing all data from {start_date} to {end_date}")

    st.divider()

    # ========================================================================
    # CUSTOM CATEGORY BUILDER
    # ========================================================================

    st.header("➕ Custom Categories")

    # Show current custom categories
    if st.session_state.custom_categories:
        st.caption(
            f"**Active custom categories ({len(st.session_state.custom_categories)}):**"
        )
        for cat in st.session_state.custom_categories:
            st.caption(f"• {cat['name']} \n ({cat['type']})")

        # Clear all button
        if st.button(
            "🗑️ Clear All Custom Categories", width="content", type="secondary"
        ):
            st.session_state.custom_categories = []
            st.session_state.categorized_data = None
            st.rerun()

    with st.expander("➕ Add new category", expanded=False):
        with st.form("add_category_form"):
            st.markdown("**Category Details**")
            st.info(
                "Give your category type a unique name. Category Types could have multiple groups of transactions Individual transactions have withdrawals, send money etc. If you want this you have to add each group individually under the same Type,"
            )

            # Basic info

            cat_type = st.text_input(
                "Category Type*",
                placeholder="e.g., Subscriptions",
            )

            cat_name = st.text_input(
                "Category Name*",
                placeholder="e.g., Netflix,",
            )

            cat_description = st.text_area(
                "Description",
                placeholder="e.g., Monthly Netflix subscription payments",
            )

            # Metadata
            col1, col2 = st.columns(2)

            with col1:
                merchant_type = st.text_input(
                    "Merchant Type*",
                    value="Service",
                    placeholder="e.g., Merchant, Service, Landlord",
                )

            with col2:
                color_map = st.selectbox(
                    "Color Scheme*",
                    options=["Greens", "Reds", "Blues", "Oranges", "Purples", "Greys"],
                )

            st.markdown("**Pattern Matching**")
            st.info(
                "Define how to identify transactions. Patterns match against transaction fields to automatically categorize them. All matching is case-insensitive."
            )

            # Pattern matching - simplified interface
            st.markdown("**Match Field**")
            st.info(
                """
**Available fields to match on:**
- **details**: The full transaction description ("Pay Bill Online to 123321 - NETFLIX KE Acc. TCSHS9L78S4SX3HJ)
- **entity**: The merchant/person name ("NETFLIX KE")
- **type_class**: Transaction type ("Pay Bill Online")
- **type_desc**: Transaction description ("to 123321")
"""
            )

            match_field = st.selectbox(
                "Select field to match*",
                options=["details", "entity", "type_class", "type_desc"],
            )

            st.markdown("**Match Type**")
            st.info(
                """
**Matching operators:**
- **contains**: Matches if the field contains any of your keywords (most flexible)
- **equals**: Exact match only (use for specific values)
- **startswith**: Matches if the field starts with your keyword
"""
            )

            match_operator = st.selectbox(
                "How to match*",
                options=["contains", "equals", "startswith"],
            )

            st.markdown("**Match Values**")
            st.info(
                "💡 Enter one or more keywords separated by commas. For example: `netflix, netflix ke` will match transactions containing either word."
            )

            match_values = st.text_input(
                "Keywords to match*",
                placeholder="e.g., netflix",
            )

            # Advanced patterns (optional)
            add_advanced = st.checkbox("Add additional pattern (AND condition)")

            # Initialize variables to avoid Pylance errors
            match_field_2 = ""
            match_operator_2 = ""
            match_values_2 = ""

            if add_advanced:
                st.info(
                    "🔗 Add a second pattern that must ALSO match (AND logic). Both patterns must be true for a transaction to be categorized."
                )
                match_field_2 = st.selectbox(
                    "Second Match Field",
                    options=["details", "entity", "type_class", "type_desc"],
                    key="match_field_2",
                )

                match_operator_2 = st.selectbox(
                    "Second Match Type",
                    options=["contains", "equals", "startswith"],
                    key="match_operator_2",
                )

                match_values_2 = st.text_input(
                    "Second Match Values",
                    placeholder="e.g., online",
                    key="match_values_2",
                )

            # Form submission
            submit = st.form_submit_button(
                "Add Category & Recategorize", width="content"
            )

            handle_user_category(
                logger,
                cat_name,
                cat_type,
                cat_description,
                merchant_type,
                color_map,
                match_field,
                match_operator,
                match_values,
                add_advanced,
                match_field_2,
                match_operator_2,
                match_values_2,
                submit,
            )

# Apply filters
filtered_categorized_data = filter_categorized_data(
    categorized_data if isinstance(categorized_data, dict) else {},
    date_filter=date_filter_value,
    month_filter=month_filter_value,
)

st.divider()

# ============================================================================
# LOAD CATEGORY METADATA
# ============================================================================

# Load category definitions to get metadata
config_path = Path(__file__).parent / "configs" / "categories.yaml"
with open(config_path) as f:
    category_config = yaml.safe_load(f)
    logger.info("Loading YAML with category definitions")

# Create category metadata mapping (from YAML + custom categories)
category_metadata = {}

# Add YAML categories
for cat_def in category_config["categories"]:
    category_metadata[cat_def["name"]] = {
        "type": cat_def.get("type", "other"),
        "description": cat_def.get("description", ""),
        "merchant_type": cat_def.get("merchant_type", "Merchant"),
        "color_map": cat_def.get("color_map", "Reds"),
    }

# Add custom categories from session
for cat_def in st.session_state.custom_categories:
    category_metadata[cat_def["name"]] = {
        "type": cat_def.get("type", "other"),
        "description": cat_def.get("description", ""),
        "merchant_type": cat_def.get("merchant_type", "Merchant"),
        "color_map": cat_def.get("color_map", "Reds"),
    }

# ============================================================================
# ANALYZE DATA
# ============================================================================

# Initialize analyzer
logger.info("Initializing the Analyzer")
analyzer = Analyzer(filtered_categorized_data)

# Get all analysis results
analysis_results = {}
for category_name in filtered_categorized_data.keys():
    if category_name != "uncategorized":
        # Determine if this is money in or out based on color_map
        # Green colors typically indicate money coming in
        metadata = category_metadata.get(category_name, {})
        is_money_in = metadata.get("color_map", "").lower() == "greens"

        result = analyzer.analyze_category(category_name, is_money_in=is_money_in)
        analysis_results[category_name] = result

# ============================================================================
# ORGANIZE CATEGORIES BY TYPE
# ============================================================================

# Group categories by their type (dynamically from YAML)
# First, collect all unique types from the categories
type_groups = {}

for category_name in analysis_results.keys():
    cat_type = category_metadata.get(category_name, {}).get("type", "other")

    # Initialize the type group if it doesn't exist
    if cat_type not in type_groups:
        type_groups[cat_type] = []

    type_groups[cat_type].append(category_name)

# Remove empty types
type_groups = {k: v for k, v in type_groups.items() if v}
# Exclude "Misc" and "Other" types from display (case-insensitive)
_exclude = {}
type_groups = {k: v for k, v in type_groups.items() if k.lower() not in _exclude}


if not type_groups:
    st.warning("No categorized transactions found.")
    st.stop()

    # ============================================================================
    # SUMMARY SECTION - TYPE OVERVIEW WITH STACKED BAR CHARTS
    # ============================================================================



display_transaction_type_overview(type_groups, analysis_results)

st.divider()

# ============================================================================
# DETAILED SECTIONS BY TYPE
# ============================================================================


# Display each type as a separate section
for type_name, categories in type_groups.items():
    # Check if any category in this type has data
    has_data = any(
        not analysis_results[cat].raw_df.empty
        for cat in categories
        if cat in analysis_results
    )

    # Skip this type if it has no data
    if not has_data:
        continue

    with st.expander(f"**{type_name}**", expanded=False):
        # add function that will collapse each category when another is opened
        # Create tabs for each category within this type
        if len(categories) == 1:
            # If only one category, don't create tabs
            category_name = categories[0]
            result = analysis_results[category_name]
            metadata = category_metadata.get(category_name, {})

            st.subheader(category_name)
            display_category_tab(
                analysis_result=result,
                category_name=category_name,
                merchant_type=metadata.get("merchant_type", "Merchant"),
                color_map=metadata.get("color_map", "Reds"),
            )
        else:
            # Multiple categories - create tabs
            tabs = st.tabs(categories)

            for idx, category_name in enumerate(categories):
                with tabs[idx]:
                    result = analysis_results[category_name]
                    metadata = category_metadata.get(category_name, {})

                    display_category_tab(
                        analysis_result=result,
                        category_name=category_name,
                        merchant_type=metadata.get("merchant_type", "Merchant"),
                        color_map=metadata.get("color_map", "Reds"),
                    )

# ============================================================================
# UNCATEGORIZED TRANSACTIONS SECTION
# ============================================================================

st.divider()

# Get uncategorized transactions
uncategorized_df = filtered_categorized_data.get("uncategorized", pd.DataFrame())

if not uncategorized_df.empty:
    st.header(f"⚠️ Uncategorized Transactions ({len(uncategorized_df)})")

    with st.expander("View Uncategorized Transactions", expanded=False):
        # Show helpful context
        st.info(
            "These transactions don't match any category patterns. "
            "Review the patterns below and use the **Add Custom Category** section in the sidebar to categorize them."
        )

        # Show unique type_class values to help identify patterns
        unique_types = uncategorized_df["type_class"].unique()
        if len(unique_types) > 0:
            st.markdown("**Common transaction types in uncategorized:**")
            st.write(", ".join([f"`{t}`" for t in unique_types[:10]]))

        # Configure column display
        column_config = {
            "receiptno": st.column_config.Column("Receipt", width="small"),
            "completiontime": st.column_config.DatetimeColumn(
                "Date/Time", format="ddd, DD MMM, YY | hh:mma"
            ),
            "details": st.column_config.Column("Details", width="large"),
            "entity": st.column_config.Column("Entity", width="medium"),
            "type_class": st.column_config.Column("Type Class", width="medium"),
            "type_desc": st.column_config.Column("Type Description", width="medium"),
            "withdrawn": st.column_config.NumberColumn(
                "Withdrawn", format="%.0f/=", width="small"
            ),
            "paidin": st.column_config.NumberColumn(
                "Paid In", format="%.0f/=", width="small"
            ),
        }

        # Select columns to display
        display_columns = [
            "receiptno",
            "completiontime",
            "details",
            "entity",
            "type_class",
            "type_desc",
            "withdrawn",
            "paidin",
        ]

        # Filter to only include columns that exist in the dataframe
        display_columns = [
            col for col in display_columns if col in uncategorized_df.columns
        ]

        # Display the dataframe
        st.dataframe(
            uncategorized_df[display_columns],
            column_config=column_config,
            hide_index=True,
            width="content",
        )