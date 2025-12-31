"""
Visualization utilities for transaction analysis.

Simple, reusable chart functions for M-Pesa transaction data.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional, List

# Default configuration
DEFAULT_TEMPLATE = "xgridoff"
DEFAULT_HEIGHT = 500
TOP_N = 10


def create_horizontal_bar_chart(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    template: str = DEFAULT_TEMPLATE,
    height: Optional[int] = None,
) -> Optional[go.Figure]:
    """
    Create a horizontal bar chart showing top entities by amount.

    Args:
        data: DataFrame with aggregated data
        x_col: Column for x-axis (usually "amount")
        y_col: Column for y-axis (usually "processed_entity")
        title: Chart title
        template: Plotly template
        height: Chart height (optional)

    Returns:
        Plotly figure or None if data is empty
    """
    if data.empty:
        return None

    # Take top N, sort ascending for better display
    chart_data = data.nlargest(TOP_N, x_col).sort_values(by=x_col, ascending=True)

    fig = px.bar(
        chart_data,
        y=y_col,
        x=x_col,
        orientation="h",
        title=title,
        template=template,
        hover_data={"count": True} if "count" in chart_data.columns else None,
    )

    fig.update_layout(
        height=height if height else DEFAULT_HEIGHT,
        showlegend=False,
        xaxis_title="",
        xaxis=dict(showticklabels=False),
        yaxis_title="",
        dragmode=False,
    )

    fig.update_traces(
        texttemplate="%{x:,.0f}/=",  # Format: "1,500/="
        textposition="auto",
        hovertemplate=(
            "%{y}<br>Amount: %{x:,.0f}/=<br>Transactions: %{customdata[0]}<extra></extra>"
            if "count" in chart_data.columns
            else "%{y}<br>Amount: %{x:,.0f}/=<extra></extra>"
        ),
    )

    return fig


def create_pie_chart(
    data: pd.DataFrame,
    values_col: str,
    names_col: str,
    title: str,
    template: str = DEFAULT_TEMPLATE,
    color_sequence: Optional[List] = None,
) -> Optional[go.Figure]:
    """
    Create a pie chart for proportion visualization.

    Args:
        data: DataFrame with data
        values_col: Column for slice sizes (usually "amount")
        names_col: Column for slice labels (usually "processed_entity")
        title: Chart title
        template: Plotly template
        color_sequence: Optional color sequence

    Returns:
        Plotly figure or None if data is empty
    """
    if data.empty:
        return None

    if color_sequence is None:
        color_sequence = px.colors.qualitative.Set3

    fig = px.pie(
        data,
        values=values_col,
        names=names_col,
        title=title,
        color_discrete_sequence=color_sequence,
        template=template,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{value:,.0f}/= (%{percent})<extra></extra>",
    )

    return fig


# For testing
if __name__ == "__main__":
    print("Visualization Utilities")
    print("=" * 60)
    print("This provides chart functions for analysis.")
    print("\nUsage:")
    print("  fig = create_horizontal_bar_chart(")
    print("      data=aggregated_df,")
    print("      x_col='amount',")
    print("      y_col='processed_entity',")
    print("      title='Top Merchants'")
    print("  )")
    print("=" * 60)
