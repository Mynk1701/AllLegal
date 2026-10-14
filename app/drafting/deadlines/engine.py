"""
Deadline engine for the cheque-bounce (S.138 NI Act) track.

Pure functions only: dates go in, `DeadlineResult`s come out. No DB, no
`datetime.now()` — `today` is always injected by the caller so this module
stays trivially unit-testable and deterministic in tests.

Implements the four deadlines in the LLD (plans/read-alllegal-drafting-
module-track-spec-keen-ladybug.md, S.6):
  1. cheque_validity   — 3 months from the cheque date
  2. notice_deadline    — 30 days from the complainant learning of dishonour
  3. payment_window     — 15 days from the accused's receipt of the notice
  4. complaint_window   — 1 month from the day after (3) lapses

Every number here is a rule *parameter*, not a hard assumption buried in
code — see `DEFAULT_PARAMS` below, overridable by the track config so a
lawyer-reviewed change doesn't require touching this file.

⚑ Several anchors below encode a judgement call flagged for lawyer review in
the LLD (S.8) — see the inline "LLD S.8 #n" references. Do not change the
anchor logic without updating that section too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, List, Literal, Optional

from .calendar import DateWindow, add_days, add_months, days_window, months_window

Status = Literal["needs_input", "ok", "due_soon", "missed"]

# Days before `safe_by` that a still-open deadline starts reading "due_soon".
DEFAULT_DUE_SOON_WINDOW_DAYS = 7

DEFAULT_PARAMS = {
    "cheque_validity_months": 3,
    "notice_deadline_days": 30,
    "payment_window_days": 15,
    "complaint_window_months": 1,
    # Used only when notice.delivered_on is unknown but refused/unclaimed or
    # dispatch is known — a conservative stand-in, always surfaced as a
    # warning, never silently trusted. Lawyer to confirm (LLD S.8 #5).
    "deemed_delivery_days": 5,
}


@dataclass(frozen=True)
class ChequeBounceDeadlineFacts:
    """The subset of ChequeBounceFacts the deadline engine actually reads,
    expressed as a flat dataclass so this module has zero dependency on
    Pydantic/the fact model. Build this from `ChequeBounceFacts` at the call
    site (see `app/drafting/deadlines/adapters.py`)."""

    cheque_date: Optional[date] = None
    presentment_date: Optional[date] = None
    return_memo_date: Optional[date] = None
    # The statutory trigger for the 30-day notice clock is the complainant's
    # *receipt of information* from the bank (S.138 proviso (b)), which is
    # not always the same day as the return-memo date (LLD S.8 #1).
    bank_info_received_date: Optional[date] = None
    notice_dispatch_date: Optional[date] = None
    notice_delivered_on: Optional[date] = None
    notice_returned_unclaimed: bool = False
    notice_refused: bool = False
    complaint_date: Optional[date] = None  # actual, or intended, filing date


@dataclass(frozen=True)
class DeadlineResult:
    key: str
    label: str
    status: Status
    safe_by: Optional[date]
    outer_limit: Optional[date]
    condonable: Optional[bool]
    basis: str
    authority: str
    warnings: List[str] = field(default_factory=list)


def _status_for_window(
    window: Optional[DateWindow],
    today: date,
    action_date: Optional[date],
    due_soon_days: int,
) -> Status:
    if window is None:
        return "needs_input"
    if action_date is not None:
        # A compliance date was recorded (notice sent, complaint filed, ...):
        # judge THAT date against the window, not `today`.
        if action_date <= window.safe_by:
            return "ok"
        if action_date <= window.outer_limit:
            return "ok"  # still within the outer, defensible reading
        return "missed"
    # No action recorded yet: this is a forward-looking "still have to do
    # this" deadline, judged against today.
    if today <= window.safe_by - timedelta(days=due_soon_days):
        return "ok"
    if today <= window.outer_limit:
        return "due_soon"
    return "missed"


def compute(
    facts: ChequeBounceDeadlineFacts,
    today: date,
    *,
    holidays: Iterable[date] = (),
    params: Optional[dict] = None,
    due_soon_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS,
) -> List[DeadlineResult]:
    """Compute all four cheque-bounce deadlines. Each result is independent
    to render; #4's anchor is derived from #3's outer limit, so #3 is always
    computed first."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    holidays = list(holidays)
    results: List[DeadlineResult] = []

    # ---- 1. Cheque validity: 3 months from the cheque date -----------------
    warnings_1: List[str] = []
    window_1 = None
    if facts.cheque_date is not None:
        window_1 = months_window(facts.cheque_date, p["cheque_validity_months"])
    results.append(
        DeadlineResult(
            key="cheque_validity",
            label="Cheque validity",
            status=_status_for_window(window_1, today, facts.presentment_date, due_soon_days),
            safe_by=window_1.safe_by if window_1 else None,
            outer_limit=window_1.outer_limit if window_1 else None,
            condonable=None,  # a banking rule, not a procedural delay a court excuses
            basis=(
                f"{p['cheque_validity_months']} months from the cheque date "
                f"({facts.cheque_date.isoformat()})" if facts.cheque_date else "Needs the cheque date."
            ),
            authority="S.138 proviso (a), NI Act, 1881 (as read with current cheque-validity banking practice)",
            warnings=warnings_1,
        )
    )

    # ---- 2. Notice deadline: 30 days from learning of dishonour -----------
    warnings_2: List[str] = []
    notice_anchor = facts.bank_info_received_date
    if notice_anchor is None and facts.return_memo_date is not None:
        notice_anchor = facts.return_memo_date
        warnings_2.append(
            "Date the complainant received the bank's information is not set; "
            "using the return-memo date instead. Confirm these are the same day — "
            "S.138 proviso (b) runs from receipt of information, not the memo date (LLD S.8 #1)."
        )
    window_2 = None
    if notice_anchor is not None:
        window_2 = days_window(notice_anchor, p["notice_deadline_days"])
    results.append(
        DeadlineResult(
            key="notice_deadline",
            label="Notice deadline",
            status=_status_for_window(window_2, today, facts.notice_dispatch_date, due_soon_days),
            safe_by=window_2.safe_by if window_2 else None,
            outer_limit=window_2.outer_limit if window_2 else None,
            condonable=False,
            basis=(
                f"{p['notice_deadline_days']} days from {notice_anchor.isoformat()} "
                "(complainant's receipt of dishonour information)" if notice_anchor else
                "Needs the return-memo date, or the date the complainant received the bank's information."
            ),
            authority="S.138 proviso (b), NI Act, 1881",
            warnings=warnings_2,
        )
    )

    # ---- 3. Payment window: 15 days from the accused's receipt of notice --
    warnings_3: List[str] = []
    payment_anchor = facts.notice_delivered_on
    if payment_anchor is None and (facts.notice_returned_unclaimed or facts.notice_refused):
        if facts.notice_dispatch_date is not None:
            payment_anchor = add_days(facts.notice_dispatch_date, p["deemed_delivery_days"])
            warnings_3.append(
                "Notice was returned unclaimed/refused and no delivery date is recorded; "
                f"treating it as served {p['deemed_delivery_days']} days after dispatch as a "
                "conservative placeholder. Confirm the deemed-service rule and the actual "
                "tracking history before relying on this (LLD S.8 #5)."
            )
        else:
            warnings_3.append(
                "Notice was returned unclaimed/refused but the dispatch date is also missing — "
                "cannot estimate a deemed-service date."
            )
    window_3 = None
    if payment_anchor is not None:
        window_3 = days_window(payment_anchor, p["payment_window_days"])
    results.append(
        DeadlineResult(
            key="payment_window",
            label="Accused's payment window",
            status=_status_for_window(window_3, today, None, due_soon_days),
            safe_by=window_3.safe_by if window_3 else None,
            outer_limit=window_3.outer_limit if window_3 else None,
            condonable=None,
            basis=(
                f"{p['payment_window_days']} days from the accused's receipt of the notice "
                f"({payment_anchor.isoformat()})" if payment_anchor else
                "Needs the notice's delivery date (or unclaimed/refused status plus dispatch date)."
            ),
            authority="S.138 proviso (c), NI Act, 1881",
            warnings=warnings_3,
        )
    )

    # ---- 4. Complaint window: 1 month from the day after (3) lapses -------
    warnings_4: List[str] = []
    cause_of_action_date = None
    if window_3 is not None:
        cause_of_action_date = window_3.outer_limit + timedelta(days=1)
    window_4 = None
    if cause_of_action_date is not None:
        window_4 = months_window(
            cause_of_action_date,
            p["complaint_window_months"],
            roll_forward=True,
            holidays=holidays,
        )
        if window_4.outer_limit != add_months(cause_of_action_date, p["complaint_window_months"]):
            warnings_4.append(
                "Outer limit rolled forward past a Sunday/listed court holiday for the chosen forum. "
                "Confirm courts actually extend this filing deadline that way before relying on it "
                "(LLD S.8 #4)."
            )
    results.append(
        DeadlineResult(
            key="complaint_window",
            label="Complaint filing window",
            status=_status_for_window(window_4, today, facts.complaint_date, due_soon_days),
            safe_by=window_4.safe_by if window_4 else None,
            outer_limit=window_4.outer_limit if window_4 else None,
            condonable=True,
            basis=(
                f"{p['complaint_window_months']} month from the cause of action "
                f"({cause_of_action_date.isoformat()}), the day after the payment window lapses"
                if cause_of_action_date else
                "Needs the payment-window deadline to be computable first."
            ),
            authority="S.142(1)(b) NI Act, 1881 (proviso allows condonation for sufficient cause)",
            warnings=warnings_4,
        )
    )

    return results
