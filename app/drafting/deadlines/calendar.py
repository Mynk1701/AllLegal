"""
Pure date arithmetic for the deadline engine. No I/O, no third-party deps —
this is the part that gets exhaustively unit-tested, so it stays stdlib-only.

Day-counting convention (Limitation Act, 1963, S.12(1)): the day the clock
starts running is EXCLUDED from the count, and the last day is INCLUDED.
e.g. "15 days from receipt on 1 March" -> 2..16 March are the 15 days ->
day 15 (and the deadline) is 16 March.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional


def add_days(anchor: date, days: int) -> date:
    """`days` clear days after `anchor` (anchor excluded, per S.12(1))."""
    return anchor + timedelta(days=days)


def add_months(anchor: date, months: int) -> date:
    """`months` calendar months after `anchor`, clamped to the target month's
    last day (e.g. 31 Jan + 1 month -> 28/29 Feb, not an overflow into March).
    """
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    day = min(anchor.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


def is_court_closed(d: date, holidays: Iterable[date]) -> bool:
    """Sunday, or a date in the given holiday set. (Second Saturdays etc. are
    whatever the caller includes in `holidays` — this function only knows
    Sunday is universally closed.)"""
    return d.weekday() == 6 or d in set(holidays)


def roll_forward_if_closed(d: date, holidays: Iterable[date]) -> date:
    """If `d` falls on a day the court is closed, move to the next open day
    (General Clauses Act S.10 / Limitation Act S.4 principle: a limitation
    period that expires on a day the court is closed is extended to the next
    day it reopens). Used ONLY for court-filing deadlines, never for
    non-judicial acts like sending a notice."""
    holidays_set = set(holidays)
    while is_court_closed(d, holidays_set):
        d = d + timedelta(days=1)
    return d


@dataclass(frozen=True)
class DateWindow:
    """A deadline expressed two ways: the conservative reading a lawyer should
    plan around (`safe_by`), and the most generous reading that is still
    defensible (`outer_limit`). For a same-day rule the two are equal."""
    safe_by: date
    outer_limit: date


def days_window(
    anchor: date,
    days: int,
    *,
    roll_forward: bool = False,
    holidays: Optional[Iterable[date]] = None,
) -> DateWindow:
    outer = add_days(anchor, days)
    if roll_forward:
        outer = roll_forward_if_closed(outer, holidays or [])
    # safe_by is one clear day earlier than the outer limit, so "due soon"
    # warnings fire before the last legally defensible moment.
    safe = outer - timedelta(days=1)
    return DateWindow(safe_by=safe, outer_limit=outer)


def months_window(
    anchor: date,
    months: int,
    *,
    roll_forward: bool = False,
    holidays: Optional[Iterable[date]] = None,
) -> DateWindow:
    outer = add_months(anchor, months)
    if roll_forward:
        outer = roll_forward_if_closed(outer, holidays or [])
    safe = outer - timedelta(days=1)
    return DateWindow(safe_by=safe, outer_limit=outer)
