"""
Unit tests for the cheque-bounce deadline engine. Pure stdlib + the engine
itself — no DB, no FastAPI, so these run even without `pip install -r
requirements.txt` (useful for CI as well as for a lawyer-reviewer sanity
check against the written test vectors in the LLD, S.6).

Run: python3 -m pytest tests/drafting/   (or python3 -m unittest discover)
"""
from datetime import date

from app.drafting.deadlines.calendar import add_months
from app.drafting.deadlines.engine import ChequeBounceDeadlineFacts, compute


def test_add_months_clamps_to_month_end():
    # 31 Jan + 1 month -> 28 Feb in a non-leap year, not an overflow to March.
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    # 2028 is a leap year.
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_add_months_plain():
    assert add_months(date(2026, 3, 4), 3) == date(2026, 6, 4)


def test_cheque_validity_missing_date_needs_input():
    facts = ChequeBounceDeadlineFacts()
    results = {r.key: r for r in compute(facts, today=date(2026, 1, 1))}
    assert results["cheque_validity"].status == "needs_input"
    assert results["cheque_validity"].safe_by is None


def test_cheque_validity_presented_in_time():
    facts = ChequeBounceDeadlineFacts(
        cheque_date=date(2026, 1, 4),
        presentment_date=date(2026, 2, 1),  # well within 3 months
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 2, 1))}
    assert results["cheque_validity"].status == "ok"
    assert results["cheque_validity"].outer_limit == date(2026, 4, 4)


def test_cheque_validity_presented_too_late_is_missed():
    facts = ChequeBounceDeadlineFacts(
        cheque_date=date(2026, 1, 4),
        presentment_date=date(2026, 6, 1),  # after the 3-month window
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 6, 1))}
    assert results["cheque_validity"].status == "missed"


def test_notice_deadline_falls_back_to_return_memo_with_warning():
    facts = ChequeBounceDeadlineFacts(
        cheque_date=date(2026, 1, 4),
        return_memo_date=date(2026, 3, 4),
        bank_info_received_date=None,
        notice_dispatch_date=date(2026, 3, 20),
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 3, 20))}
    nd = results["notice_deadline"]
    assert nd.outer_limit == date(2026, 4, 3)  # 30 days from 4 March
    assert nd.status == "ok"
    assert any("return-memo date" in w for w in nd.warnings)


def test_notice_sent_on_30th_day_is_ok_not_missed():
    # Exact boundary: notice dispatched exactly on day 30.
    facts = ChequeBounceDeadlineFacts(
        bank_info_received_date=date(2026, 3, 4),
        notice_dispatch_date=date(2026, 4, 3),
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 4, 3))}
    assert results["notice_deadline"].status == "ok"
    assert results["notice_deadline"].outer_limit == date(2026, 4, 3)


def test_notice_sent_on_31st_day_is_missed():
    facts = ChequeBounceDeadlineFacts(
        bank_info_received_date=date(2026, 3, 4),
        notice_dispatch_date=date(2026, 4, 4),
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 4, 4))}
    assert results["notice_deadline"].status == "missed"
    assert results["notice_deadline"].condonable is False


def test_payment_window_and_complaint_window_chain():
    facts = ChequeBounceDeadlineFacts(
        cheque_date=date(2026, 1, 4),
        presentment_date=date(2026, 3, 1),
        return_memo_date=date(2026, 3, 4),
        bank_info_received_date=date(2026, 3, 4),
        notice_dispatch_date=date(2026, 3, 20),
        notice_delivered_on=date(2026, 3, 25),
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 3, 25))}

    payment = results["payment_window"]
    assert payment.outer_limit == date(2026, 4, 9)  # 15 days from 25 March

    complaint = results["complaint_window"]
    # Cause of action = day after payment window outer limit = 10 April.
    # Complaint window = 1 month from 10 April = 10 May 2026 — but that's a
    # Sunday, so the engine rolls it forward to 11 May (a court-filing
    # deadline, unlike the other three).
    assert date(2026, 5, 10).weekday() == 6  # confirms the fixture's premise
    assert complaint.outer_limit == date(2026, 5, 11)
    assert any("rolled forward" in w for w in complaint.warnings)
    assert complaint.condonable is True


def test_notice_refused_uses_deemed_delivery_with_warning():
    facts = ChequeBounceDeadlineFacts(
        notice_dispatch_date=date(2026, 3, 20),
        notice_refused=True,
        notice_delivered_on=None,
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 3, 26))}
    payment = results["payment_window"]
    assert payment.safe_by is not None  # deemed-delivery anchor was used
    assert any("deemed" in w.lower() for w in payment.warnings)


def test_complaint_filed_in_time_is_ok():
    facts = ChequeBounceDeadlineFacts(
        notice_delivered_on=date(2026, 3, 25),
        complaint_date=date(2026, 5, 1),  # before 10 May outer limit
    )
    results = {r.key: r for r in compute(facts, today=date(2026, 5, 1))}
    assert results["complaint_window"].status == "ok"


def test_due_soon_fires_before_outer_limit():
    # No action recorded, today is 2 days before safe_by.
    facts = ChequeBounceDeadlineFacts(notice_delivered_on=date(2026, 3, 25))
    results = {r.key: r for r in compute(facts, today=date(2026, 4, 6))}
    # payment_window safe_by = 8 Apr, outer_limit = 9 Apr; today 6 Apr is
    # within the 7-day due-soon window of safe_by but before outer_limit.
    assert results["payment_window"].status == "due_soon"


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
