import pandas as pd
from src.data.cleaner import split_details, split_type


def test_split_details_with_separator():
    details = "Customer transfer to 254712345678 - JOHN DOE"
    ttype, entity = split_details(details)
    assert "Customer transfer to 254712345678" in ttype
    assert "JOHN DOE" == entity


def test_split_details_without_separator():
    details = "Some weird format with no separator"
    ttype, entity = split_details(details)
    assert ttype == details
    assert entity == details


def test_split_type_short_and_long():
    short = "Funds received from"
    c, d = split_type(short)
    assert c == "Funds received from"
    assert d == ""

    long = "Customer transfer to 254712345678 from account"
    c2, d2 = split_type(long)
    # first 4 words
    assert c2 == "Customer transfer to 254712345678"
    assert d2 == "from account"
