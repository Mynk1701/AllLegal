"""Unit tests for template-facing formatters (amounts, ordinals, dates)."""
from datetime import date

from app.drafting.render.formatters import (
    amount_in_words,
    format_date_long,
    indian_number_format,
    indian_number_to_words,
)


def test_indian_number_format_grouping():
    assert indian_number_format(4500000) == "45,00,000"
    assert indian_number_format(100000) == "1,00,000"
    assert indian_number_format(999) == "999"
    assert indian_number_format(1000) == "1,000"
    assert indian_number_format(12345678) == "1,23,45,678"


def test_indian_number_to_words():
    assert indian_number_to_words(450000) == "Four Lakh Fifty Thousand"
    assert indian_number_to_words(100000) == "One Lakh"
    assert indian_number_to_words(1234) == "One Thousand Two Hundred Thirty Four"
    assert indian_number_to_words(0) == "Zero"
    assert indian_number_to_words(19) == "Nineteen"
    assert indian_number_to_words(20) == "Twenty"
    assert indian_number_to_words(21) == "Twenty One"
    assert indian_number_to_words(10_000_000) == "One Crore"


def test_amount_in_words():
    assert amount_in_words(450000) == "4,50,000/- (Rupees Four Lakh Fifty Thousand only)"
    assert amount_in_words(0) == "0/- (Rupees Zero only)"


def test_format_date_long_ordinals():
    assert format_date_long(date(2026, 3, 4)) == "4th March, 2026"
    assert format_date_long(date(2026, 3, 1)) == "1st March, 2026"
    assert format_date_long(date(2026, 3, 2)) == "2nd March, 2026"
    assert format_date_long(date(2026, 3, 3)) == "3rd March, 2026"
    assert format_date_long(date(2026, 3, 11)) == "11th March, 2026"
    assert format_date_long(date(2026, 3, 21)) == "21st March, 2026"


if __name__ == "__main__":
    import sys

    mod = sys.modules[__name__]
    failures = 0
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            fn = getattr(mod, name)
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if failures else 0)
