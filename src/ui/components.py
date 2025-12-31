"""
UI Components Module for M-Pesalytics v2

Reusable Streamlit UI components with consistent styling and behavior.
All components work with AnalysisResult dataclass for cleaner integration.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List
import matplotlib
from plotly import graph_objects as go

from configs import get_logger

logger = get_logger(__name__)


def display_metrics(
    total_amount: float,
    total_charges: float,
    transaction_count: int,
    unique_entities: int,
) -> None:
    """
    Display transaction metrics in a standardized 2x2 grid.

    Args:
        total_amount: Total transaction amount
        total_charges: Total charges incurred
        transaction_count: Number of transactions
        unique_entities: Number of unique entities transacted with
    """
    # Top row
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("Transacted", f"{total_amount:,.0f}/=", border=True)
    with col2:
        st.metric("Charges Incurred", f"{total_charges:,.0f}/=", border=True)

    # Bottom row
    col3, col4 = st.columns([1, 1])
    with col3:
        st.metric("Transactions", f"{transaction_count:,}", border=True)
    with col4:
        st.metric("Unique Entities", f"{unique_entities:,}", border=True)


def display_aggregated_table(
    aggregated_frame: pd.DataFrame,
    merchant_type: str = "Merchant",
    color_map: str = "Reds",
) -> Any:
    """
    Display aggregated transaction data with styling and interactivity.

    Args:
        aggregated_frame: DataFrame grouped by entity with amount and count
        merchant_type: Label for the entity column (e.g., "Merchant", "Recipient")
        color_map: Color map for gradient styling

    Returns:
        Streamlit dataframe event object with selection info
    """
    if aggregated_frame.empty:
        st.info(f"No {merchant_type.lower()} data to display.")
        return None

    # Column configuration
    column_config = {
        "processed_entity": st.column_config.Column(merchant_type, pinned=True),
        "amount": st.column_config.NumberColumn("Amount", format="%.0f/="),
        "count": st.column_config.NumberColumn("Transactions", width="small"),
    }

    # Apply styling
    styled_df = aggregated_frame.style.background_gradient(
        cmap=color_map, subset=["count"]
    ).format({"amount": lambda x: f"{x:,.0f}/="})

    # Display with selection enabled
    event = st.dataframe(
        styled_df,
        column_config=column_config,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
    )

    return event


def display_transaction_details(
    raw_df: pd.DataFrame,
    aggregated_frame: pd.DataFrame,
    selection: Optional[Dict[str, Any]],
    merchant_type: str = "Merchant",
) -> None:
    """
    Display detailed transactions for selected entities in an expander.

    Args:
        raw_df: Raw transaction DataFrame
        aggregated_frame: Aggregated DataFrame (for entity lookup)
        selection: Selection object from dataframe event
        merchant_type: Label for the entity type
    """
    if not selection or not selection.get("rows"):
        st.markdown(
            f"💡 Select row(s) from the table above to see detailed transactions for specific {merchant_type.lower()}s."
        )
        return

    # Get selected entities
    selected_indices = selection["rows"]
    entity_values = [
        aggregated_frame.iloc[idx]["processed_entity"] for idx in selected_indices
    ]

    # Filter transactions
    result = raw_df[raw_df["processed_entity"].isin(entity_values)].copy()

    if result.empty:
        st.warning("No transactions found for selected entities.")
        return

    # Sort by date (most recent first)
    if "completiontime" in result.columns:
        result = result.sort_values("completiontime", ascending=False)

    # Determine title
    num_selected = len(entity_values)
    title = (
        f"Details for {num_selected} selected {merchant_type}s"
        if num_selected > 1
        else f"Details for {merchant_type}"
    )

    with st.expander(title, expanded=True):
        # Column configuration
        column_config = {
            "receiptno": st.column_config.Column("Receipt", width="small"),
            "completiontime": st.column_config.DatetimeColumn(
                "Date/Time", format="ddd, DD MMM, YY | hh:mma"
            ),
            "details": st.column_config.Column("Details"),
            "withdrawn": st.column_config.NumberColumn("Withdrawn", format="%.0f/="),
            "paidin": st.column_config.NumberColumn("Paid In", format="%.0f/="),
        }

        # Select columns to display
        display_columns = [
            "receiptno",
            "completiontime",
            "details",
            "withdrawn",
            "paidin",
        ]

        # Filter to available columns
        display_columns = [col for col in display_columns if col in result.columns]

        st.dataframe(
            result[display_columns],
            column_config=column_config,
            hide_index=True,
        )


def display_chart(
    figure: Optional[go.Figure],
    title: str,
) -> None:
    """
    Display a Plotly chart with consistent configuration.

    Args:
        figure: Plotly figure to display
        title: Chart title
    """
    if figure is None:
        st.info(f"No chart data available for {title}")
        return

    st.plotly_chart(figure, config={"fillFrame": True})


def display_all_transactions(
    raw_df: pd.DataFrame,
    transaction_type: str,
) -> None:
    """
    Display all transactions in a collapsible expander.

    Args:
        raw_df: Raw transaction DataFrame
        transaction_type: Type of transaction (e.g., "Send Money")
    """
    with st.expander(f"All {transaction_type} Transactions", expanded=False):
        if raw_df.empty:
            st.info(f"No {transaction_type} transactions found.")
            return

        # Column configuration
        column_config = {
            "receiptno": st.column_config.Column("Receipt", width="small"),
            "completiontime": st.column_config.DatetimeColumn(
                "Date/Time", format="ddd, DD MMM, YY | hh:mma"
            ),
            "details": st.column_config.Column("Details"),
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
            "withdrawn",
            "paidin",
        ]

        # Filter to available columns
        display_columns = [col for col in display_columns if col in raw_df.columns]

        st.dataframe(
            raw_df[display_columns],
            column_config=column_config,
            hide_index=True,
        )


def display_category_tab(
    analysis_result,  # AnalysisResult dataclass
    category_name: str,
    merchant_type: str = "Merchant",
    color_map: str = "Reds",
) -> None:
    """
    Display a complete category analysis tab with all components.

    This is the main orchestration function that combines all UI components
    to create a full category view (metrics, table, details, chart, all transactions).

    Args:
        analysis_result: AnalysisResult dataclass from analyzer
        category_name: Name of the category (e.g., "SendMoney")
        merchant_type: Label for entity column (e.g., "Recipient", "Merchant")
        color_map: Color map for styling
    """
    # Check if we have data
    if analysis_result.raw_df.empty:
        st.warning(
            f"No {category_name} transactions found in the provided statement.",
            icon="⚠️",
        )
        return

    # Display metrics
    unique_entities = analysis_result.aggregated_frame["processed_entity"].nunique()
    display_metrics(
        total_amount=analysis_result.total_amount,
        total_charges=analysis_result.total_charges,
        transaction_count=analysis_result.transaction_count,
        unique_entities=unique_entities,
    )

    st.markdown("\n")

    # Display aggregated table
    event = display_aggregated_table(
        aggregated_frame=analysis_result.aggregated_frame,
        merchant_type=merchant_type,
        color_map=color_map,
    )

    # Display transaction details for selected rows
    selection = event.get("selection") if event else None
    display_transaction_details(
        raw_df=analysis_result.raw_df,
        aggregated_frame=analysis_result.aggregated_frame,
        selection=selection,
        merchant_type=merchant_type,
    )

    st.markdown("\n")

    # Display chart
    display_chart(
        figure=analysis_result.figure,
        title=f"Top 10 {category_name}",
    )

    st.markdown("\n")

    # Display all transactions
    display_all_transactions(
        raw_df=analysis_result.raw_df,
        transaction_type=category_name,
    )


def display_error_state(error_message: str, error_type: str = "Error") -> None:
    """
    Display a standardized error state.

    Args:
        error_message: Error message to display
        error_type: Type of error (Error, Warning, Info)
    """
    logger.error(f"{error_type}: {error_message}")
    st.error(f"{error_type}: {error_message}", icon="🚨")


def display_empty_state(message: str) -> None:
    """
    Display a standardized empty state.

    Args:
        message: Message to display
    """
    st.info(message, icon="ℹ️")
