"""
Transaction analyzer with clean dataclass-based return types.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional
import plotly.graph_objects as go

from configs import get_logger
from .visualizations import create_horizontal_bar_chart, create_pie_chart

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """
    Result from analyzing a transaction category.

    Much cleaner than returning (fig, amount, charges, count, frame, raw_df)!
    """

    figure: Optional[go.Figure]  # Plotly chart
    total_amount: float  # Total money (paidin or withdrawn)
    total_charges: float  # Total charges/fees
    transaction_count: int  # Number of transactions
    aggregated_frame: pd.DataFrame  # Grouped by entity (for tables)
    raw_df: pd.DataFrame  # All transactions (for details)


class Analyzer:
    """
    analyzing categorized M-Pesa transactions.

    I take categorized data and generate insights, totals, and visualizations.
    """

    def __init__(self, categorized_data: Dict[str, pd.DataFrame]):
        """
        Initialize analyzer with pre-categorized data.

        Args:
            categorized_data: Dictionary mapping category names to DataFrames
        """
        self.data = categorized_data
        logger.info(f"Analyzer initialized with {len(categorized_data)} categories")

    @staticmethod
    def is_money_in(data_category: pd.DataFrame) -> bool:
        """
        Determine if a category represents money in or money out based on column sums.

        Args:
            data_category: DataFrame with transaction data

        Returns:
            True if paidin sum is greater (money coming in), False otherwise (money going out)
        """
        if data_category.empty:
            return False

        paidin_sum = data_category.get("paidin", pd.Series([0])).sum()
        withdrawn_sum = data_category.get("withdrawn", pd.Series([0])).sum()

        return paidin_sum > withdrawn_sum

    # ========================================================================
    # MONEY IN CATEGORIES
    # ========================================================================

    def analyze_received_money(self) -> AnalysisResult:
        """
        analyzing money received from individuals.

        Returns:
            AnalysisResult with totals, chart, and data
        """
        df = self.data.get("Received (Individuals)", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        # Calculate totals
        total_amount = df["paidin"].sum()
        transaction_count = df["receiptno"].nunique()

        # grouping by sender
        aggregated = (
            df.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("paidin", "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        # Create chart
        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Top 10 Senders",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=0.0,  # No charges for received money
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    def analyze_deposits(self) -> AnalysisResult:
        """analyzing deposit transactions."""
        df = self.data.get("Deposit", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        total_amount = df["paidin"].sum()
        transaction_count = df["receiptno"].nunique()

        aggregated = (
            df.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("paidin", "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Deposits by Source",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=0.0,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    # ========================================================================
    # MONEY OUT CATEGORIES
    # ========================================================================

    def analyze_send_money(self) -> AnalysisResult:
        """analyzing money sent to others."""
        df = self.data.get("Send Money", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        # separating charges from actual transfers
        transfers = df[~df["is_charge"]]
        charges = df[df["is_charge"]]

        total_amount = transfers["withdrawn"].sum()
        total_charges = charges["withdrawn"].sum()
        transaction_count = transfers["receiptno"].nunique()

        aggregated = (
            transfers.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("withdrawn", "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Top 10 Recipients",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=total_charges,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    def analyze_buy_goods(self) -> AnalysisResult:
        """analyzing Buy Goods payments."""
        df = self.data.get("BuyGoods", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        # Separate charges
        payments = df[~df["is_charge"]]
        charges = df[df["is_charge"]]

        total_amount = payments["withdrawn"].sum()
        total_charges = charges["withdrawn"].sum()
        transaction_count = payments["receiptno"].nunique()

        aggregated = (
            payments.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("withdrawn", "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Top 10 Merchants",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=total_charges,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    def analyze_pay_bill(self) -> AnalysisResult:
        """analyzing Pay Bill payments."""
        df = self.data.get("PayBill", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        payments = df[~df["is_charge"]]
        charges = df[df["is_charge"]]

        total_amount = payments["withdrawn"].sum()
        total_charges = charges["withdrawn"].sum()
        transaction_count = payments["receiptno"].nunique()

        # grouping by business (with account numbers)
        aggregated = (
            payments.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("withdrawn", "sum"),
                accounts=(
                    "account_no",
                    lambda x: (
                        list(x.unique()) if "account_no" in payments.columns else []
                    ),
                ),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Top 10 Billers",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=total_charges,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    def analyze_withdrawals(self) -> AnalysisResult:
        """analyzing cash withdrawals."""
        df = self.data.get("Withdrawal", pd.DataFrame())

        if df.empty:
            return self._empty_result()

        withdrawals = df[~df["is_charge"]]
        charges = df[df["is_charge"]]

        total_amount = withdrawals["withdrawn"].sum()
        total_charges = charges["withdrawn"].sum()
        transaction_count = withdrawals["receiptno"].nunique()

        aggregated = (
            withdrawals.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=("withdrawn", "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title="Top 10 Withdrawal Agents",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=total_charges,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    # ========================================================================
    # GENERIC ANALYSIS (works for any category)
    # ========================================================================

    def analyze_category(
        self, category_name: str, is_money_in: bool = False
    ) -> AnalysisResult:
        """
        providing generic analysis function for any category.

        This is useful for custom YAML-defined categories!

        Args:
            category_name: Name of category to analyze
            is_money_in: True if money coming in, False if going out

        Returns:
            AnalysisResult with analysis
        """
        df = self.data.get(category_name, pd.DataFrame())

        if df.empty:
            return self._empty_result()

        # Determine which column to use. Honor the caller-provided flag
        # so callers (like the app) can force money-in semantics.
        amount_col = "paidin" if is_money_in else "withdrawn"

        # separating charges if applicable
        if "is_charge" in df.columns:
            transactions = df[~df["is_charge"]]
            charges = df[df["is_charge"]]
            total_charges = charges[amount_col].sum()
        else:
            transactions = df
            total_charges = 0.0

        total_amount = transactions[amount_col].sum()
        transaction_count = transactions["receiptno"].nunique()

        # grouping by entity
        aggregated = (
            transactions.groupby("processed_entity")
            .agg(
                count=("receiptno", "count"),
                amount=(amount_col, "sum"),
            )
            .sort_values(by="amount", ascending=False)
            .reset_index()
        )

        fig = create_horizontal_bar_chart(
            data=aggregated,
            x_col="amount",
            y_col="processed_entity",
            title=f"Top 10 by Amount - {category_name}",
        )

        return AnalysisResult(
            figure=fig,
            total_amount=total_amount,
            total_charges=total_charges,
            transaction_count=transaction_count,
            aggregated_frame=aggregated,
            raw_df=df,
        )

    # ============================================================================
    # HELPER FUNCTIONS
    # ============================================================================

    def _empty_result(self) -> AnalysisResult:
        """returning empty result when no data is available."""
        return AnalysisResult(
            figure=None,
            total_amount=0.0,
            total_charges=0.0,
            transaction_count=0,
            aggregated_frame=pd.DataFrame(),
            raw_df=pd.DataFrame(),
        )


# For testing
if __name__ == "__main__":
    from configs import setup_logging

    setup_logging()

    print("Transaction Analyzer")
    print("=" * 60)
    print("This analyzes categorized transactions.")
    print("\nUsage:")
    print("  categorized = categorize_transactions(clean_df)")
    print("  analyzer = Analyzer(categorized)")
    print("  result = analyzer.analyze_send_money()")
    print("  print(f'Total sent: {result.total_amount}')")
    print("=" * 60)
