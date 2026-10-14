"""
Template-facing formatters: Indian-style amounts, dates and ordinals.

Deliberately stdlib-only (no `num2words`) — these are short, legally-visible
strings that go straight into a court filing, so they stay in-house and
unit-tested rather than depending on a general-purpose third-party word list.
"""
from __future__ import annotations

from datetime import date

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]
_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _two_digits_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def _three_digits_to_words(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_two_digits_to_words(rest))
    return " ".join(parts)


def indian_number_to_words(n: int) -> str:
    """Integer -> English words using the Indian numbering scale (Crore,
    Lakh, Thousand), e.g. 450000 -> 'Four Lakh Fifty Thousand'. 0 -> 'Zero'."""
    if n < 0:
        return f"Minus {indian_number_to_words(-n)}"
    if n == 0:
        return "Zero"

    crore, n = divmod(n, 1_00_00_000)
    lakh, n = divmod(n, 1_00_000)
    thousand, n = divmod(n, 1_000)
    hundred_etc = n

    parts = []
    if crore:
        parts.append(f"{indian_number_to_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two_digits_to_words(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two_digits_to_words(thousand)} Thousand")
    if hundred_etc:
        parts.append(_three_digits_to_words(hundred_etc))
    return " ".join(parts)


def indian_number_format(n: float) -> str:
    """Digit-group with the Indian comma convention: last 3 digits, then
    groups of 2, e.g. 4500000 -> '45,00,000'. Rupees are integral in these
    filings; `n` is rounded to the nearest rupee."""
    n = int(round(n))
    sign = "-" if n < 0 else ""
    n = abs(n)
    s = str(n)
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups) + "," + tail


def amount_in_words(n: float) -> str:
    """'4,50,000/- (Rupees Four Lakh Fifty Thousand only)' — the standard
    legal-drafting form for a money figure."""
    n_int = int(round(n))
    words = indian_number_to_words(n_int) if n_int else "Zero"
    return f"{indian_number_format(n_int)}/- (Rupees {words} only)"


def ordinal_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_date_long(d: date) -> str:
    """'4th March, 2026' — the form used in notices, plaints and affidavits."""
    return f"{d.day}{ordinal_suffix(d.day)} {_MONTH_NAMES[d.month - 1]}, {d.year}"
