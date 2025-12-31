"""
UI module for M-Pesalytics v2.

Provides reusable Streamlit components for displaying transaction analysis.
"""

from .components import (
    display_metrics,
    display_aggregated_table,
    display_transaction_details,
    display_chart,
    display_all_transactions,
    display_category_tab,
    display_error_state,
    display_empty_state,
)

__all__ = [
    "display_metrics",
    "display_aggregated_table",
    "display_transaction_details",
    "display_chart",
    "display_all_transactions",
    "display_category_tab",
    "display_error_state",
    "display_empty_state",
]
