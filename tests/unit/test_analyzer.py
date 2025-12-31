import pandas as pd
from pathlib import Path

from src.analysis.analyzer import Analyzer


def test_analyze_category_with_fauxdata(tmp_path: Path):
    # Load faux data shipped with the repo
    faux_path = Path(".streamlit") / "faux_data.csv"
    assert faux_path.exists(), "faux_data.csv not found in .streamlit"

    df = pd.read_csv(faux_path)

    # Ensure datetime conversion
    df["completiontime"] = pd.to_datetime(df["completiontime"])

    # Create helper columns analyzer expects
    # processed_entity: extract part after ' - ' if present, otherwise use details
    def extract_entity(details: str) -> str:
        if not isinstance(details, str):
            return ""
        parts = details.split(" - ")
        return parts[-1].strip() if len(parts) > 1 else details.strip()

    df["processed_entity"] = df["details"].apply(extract_entity)

    # is_charge: mark rows where 'charge' appears in details (case-insensitive)
    df["is_charge"] = df["details"].str.lower().str.contains("charge")

    # Build categorized mapping with a single category containing all rows
    categorized = {"Faux": df}

    analyzer = Analyzer(categorized)

    # Analyze as money-out (withdrawn)
    res_out = analyzer.analyze_category("Faux", is_money_in=False)

    # Compute expected totals programmatically (exclude charges)
    transactions_out = df[~df["is_charge"]]
    expected_total_out = transactions_out["withdrawn"].sum()
    expected_charges_out = df[df["is_charge"]]["withdrawn"].sum()
    expected_count_out = transactions_out["receiptno"].nunique()

    assert float(res_out.total_amount) == float(expected_total_out)
    assert float(res_out.total_charges) == float(expected_charges_out)
    assert int(res_out.transaction_count) == int(expected_count_out)

    # Analyze as money-in (paidin)
    res_in = analyzer.analyze_category("Faux", is_money_in=True)

    transactions_in = df[~df["is_charge"]]
    expected_total_in = transactions_in["paidin"].sum()
    expected_charges_in = df[df["is_charge"]]["paidin"].sum()
    expected_count_in = transactions_in["receiptno"].nunique()

    assert float(res_in.total_amount) == float(expected_total_in)
    assert float(res_in.total_charges) == float(expected_charges_in)
    assert int(res_in.transaction_count) == int(expected_count_in)
