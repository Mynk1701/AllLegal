"""
Legal-correctness checks for the cheque-bounce track (LLD S.8).

Two severities:
  - "blocking": generation of the named document(s) is refused until fixed.
    `applies_to_documents == []` means it blocks every document in the track.
  - "warning": the document still generates, but the issue is surfaced to
    the lawyer (in the gaps/warnings panel and, where noted, in the rendered
    text itself) rather than silently absorbed.

Pure function: facts + computed deadlines + `today` in, issues out. No I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Literal, Optional

from app.drafting.deadlines.engine import DeadlineResult
from app.drafting.models.cheque_bounce import ChequeBounceFacts

Severity = Literal["blocking", "warning"]

CASH_LOAN_269SS_THRESHOLD = 20_000  # Income Tax Act S.269SS, LLD S.8 #7


@dataclass(frozen=True)
class ValidationIssue:
    rule: str
    severity: Severity
    message: str
    field_path: Optional[str] = None
    applies_to_documents: List[str] = field(default_factory=list)  # [] = blocks every document


def _deadline(deadlines: List[DeadlineResult], key: str) -> Optional[DeadlineResult]:
    return next((d for d in deadlines if d.key == key), None)


def validate(
    facts: ChequeBounceFacts, deadlines: List[DeadlineResult], today: date
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    cheque = facts.relied_cheque()
    presentment = facts.presentment_for(cheque.number if cheque else None)
    dishonour = facts.dishonour_for(cheque.number if cheque else None)

    # ---- date sanity (no future dates; chronological order) ---------------
    for label, d in [
        ("cheque date", cheque.cheque_date if cheque else None),
        ("presentment date", presentment.presentment_date if presentment else None),
        ("return-memo date", dishonour.return_memo_date if dishonour else None),
        ("notice dispatch date", facts.notice.dispatch_date),
        ("notice delivery date", facts.notice.delivered_on),
    ]:
        if d is not None and d > today:
            issues.append(
                ValidationIssue(
                    rule="no_future_dates",
                    severity="blocking",
                    message=f"The {label} ({d.isoformat()}) is in the future.",
                    applies_to_documents=[],
                )
            )

    # ---- cheque validity vs presentment (rule 1) ---------------------------
    validity = _deadline(deadlines, "cheque_validity")
    if validity and validity.status == "missed":
        issues.append(
            ValidationIssue(
                rule="cheque_validity",
                severity="blocking",
                message="The relied-upon cheque was presented after its validity period lapsed.",
                field_path="cheques",
                applies_to_documents=["complaint"],
            )
        )
        issues.append(
            ValidationIssue(
                rule="cheque_validity",
                severity="warning",
                message="The cheque's validity window had already lapsed before presentment — "
                "confirm this notice should still be sent on this cheque.",
                field_path="cheques",
                applies_to_documents=["legal_notice"],
            )
        )

    # ---- notice sent within 30 days (rule 2) -------------------------------
    notice_deadline = _deadline(deadlines, "notice_deadline")
    if notice_deadline and notice_deadline.status == "missed":
        issues.append(
            ValidationIssue(
                rule="notice_deadline",
                severity="blocking",
                message=(
                    "The legal notice was (or would be) sent more than 30 days after the "
                    "complainant learned of the dishonour. This is not itself condonable, "
                    "though delay in filing the complaint afterwards can be excused for "
                    "sufficient cause under the proviso to S.142(1)(b) — that is a separate "
                    "question from whether this notice is valid. Review with counsel before "
                    "generating the complaint."
                ),
                field_path="notice.dispatch_date",
                applies_to_documents=["complaint"],
            )
        )

    # ---- no premature complaint (rule 3->4 boundary) -----------------------
    payment_window = _deadline(deadlines, "payment_window")
    complaint_date = facts.filing.intended_or_actual_complaint_date
    if payment_window and payment_window.outer_limit and complaint_date:
        if complaint_date <= payment_window.outer_limit:
            issues.append(
                ValidationIssue(
                    rule="premature_complaint",
                    severity="blocking",
                    message=(
                        "The complaint date is on or before the end of the accused's 15-day "
                        "payment window — the cause of action has not yet arisen."
                    ),
                    field_path="filing.intended_or_actual_complaint_date",
                    applies_to_documents=["complaint"],
                )
            )

    # ---- notice amount vs cheque amount (rule 4) ---------------------------
    if cheque and cheque.amount and facts.notice.amount_demanded:
        if facts.notice.amount_demanded < cheque.amount:
            issues.append(
                ValidationIssue(
                    rule="notice_amount",
                    severity="warning",
                    message="The amount demanded in the notice is less than the cheque amount.",
                    field_path="notice.amount_demanded",
                    applies_to_documents=["legal_notice"],
                )
            )
    if facts.notice.interest_or_costs_demanded and cheque and cheque.amount and facts.notice.amount_demanded:
        if facts.notice.amount_demanded != cheque.amount:
            issues.append(
                ValidationIssue(
                    rule="notice_amount_breakdown",
                    severity="warning",
                    message="Show the cheque amount and interest/costs as separate figures in the notice, "
                    "not combined into one demand.",
                    field_path="notice.amount_demanded",
                    applies_to_documents=["legal_notice"],
                )
            )

    # ---- dishonour reason coverage (rule 5) --------------------------------
    if dishonour and dishonour.reason_code in ("stop_payment", "account_closed", "signature_differs"):
        issues.append(
            ValidationIssue(
                rule="dishonour_reason_contested",
                severity="warning",
                message=(
                    f"Dishonour reason '{dishonour.reason_code}' is more likely to be contested than "
                    "'funds insufficient' / 'exceeds arrangement'. This track's 'likely defences' research "
                    "slot should be reviewed before finalising the complaint."
                ),
                field_path="dishonours",
                applies_to_documents=[],
            )
        )

    # ---- S.141 director/partner basis for corporate accused (rule 6) ------
    if facts.accused.kind in ("company", "partnership", "llp"):
        has_in_charge = any(d.in_charge_of_business for d in facts.accused.directors)
        if not has_in_charge:
            issues.append(
                ValidationIssue(
                    rule="s141_in_charge_missing",
                    severity="blocking",
                    message=(
                        "The accused is a company/firm but no director/partner is marked "
                        "'in charge of and responsible for the conduct of its business' — "
                        "this averment is required to plead S.141 liability."
                    ),
                    field_path="accused.directors",
                    applies_to_documents=["complaint"],
                )
            )

    # ---- S.269SS cash-loan note (rule 7) -----------------------------------
    cash_amount = facts.transaction.cash_amount or 0
    if cash_amount > CASH_LOAN_269SS_THRESHOLD:
        issues.append(
            ValidationIssue(
                rule="s269ss_cash_loan",
                severity="warning",
                message=(
                    f"₹{cash_amount:,.0f} of this transaction was in cash, above the S.269SS Income Tax Act "
                    "threshold (₹20,000). General understanding is that this does not by itself defeat an "
                    "otherwise legally enforceable debt — confirm current position with counsel before relying "
                    "on this (see the Jan Vishwas / Sanjabij Tari flags in the LLD)."
                ),
                field_path="transaction.cash_amount",
                applies_to_documents=[],
            )
        )

    # ---- territorial jurisdiction needs the presenting branch (rule 8) ----
    if not (presentment and presentment.presenting_branch):
        issues.append(
            ValidationIssue(
                rule="jurisdiction_branch_missing",
                severity="blocking",
                message="The payee's presenting bank branch is not set — the territorial-jurisdiction "
                "averment under S.142(2) cannot be generated without it.",
                field_path="presentments.presenting_branch",
                applies_to_documents=["complaint"],
            )
        )

    return issues


def blocking_issues_for(issues: List[ValidationIssue], document_key: str) -> List[ValidationIssue]:
    """Issues that block generating `document_key` — either named explicitly
    or flagged as blocking every document (`applies_to_documents == []`)."""
    return [
        i for i in issues
        if i.severity == "blocking" and (not i.applies_to_documents or document_key in i.applies_to_documents)
    ]
