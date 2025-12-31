import yaml
import pandas as pd
from pathlib import Path

from src.categorization.categorizer import TransactionCategorizer


def test_categorizer_matches_custom_yaml(tmp_path: Path):
    # Create a minimal YAML config with one category
    cfg = {
        "categories": [
            {
                "name": "MyBill",
                "type": "Test",
                "description": "Test bill",
                "merchant_type": "Biller",
                "color_map": "Purples",
                "patterns": {"details": {"contains": ["pay bill"]}},
            }
        ]
    }

    cfg_path = tmp_path / "cats.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))

    # Initialize categorizer pointing to our tmp config
    cat = TransactionCategorizer(config_path=str(cfg_path))

    # Create a fake row
    row = pd.Series(
        {
            "receiptno": "r1",
            "completiontime": pd.to_datetime("2025-01-01"),
            "details": "Pay Bill to 12345 - NETFLIX",
            "paidin": 0.0,
            "withdrawn": 300.0,
            "entity": "NETFLIX",
            "type_class": "Pay Bill Online",
            "type_desc": "to 12345",
        }
    )

    matches = cat.categorize_transaction(row)
    names = [m["category"] for m in matches]
    assert "MyBill" in names
