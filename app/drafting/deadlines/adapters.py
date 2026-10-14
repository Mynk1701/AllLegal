"""Bridges `ChequeBounceFacts` (Pydantic, the API/DB shape) to
`ChequeBounceDeadlineFacts` (plain dataclass, what engine.compute() reads).
Kept separate so engine.py and calendar.py stay free of the Pydantic
dependency and remain trivially unit-testable (see tests/drafting/)."""
from __future__ import annotations

from app.drafting.deadlines.engine import ChequeBounceDeadlineFacts
from app.drafting.models.cheque_bounce import ChequeBounceFacts


def to_deadline_facts(facts: ChequeBounceFacts) -> ChequeBounceDeadlineFacts:
    cheque = facts.relied_cheque()
    presentment = facts.presentment_for(cheque.number if cheque else None)
    dishonour = facts.dishonour_for(cheque.number if cheque else None)
    return ChequeBounceDeadlineFacts(
        cheque_date=cheque.cheque_date if cheque else None,
        presentment_date=presentment.presentment_date if presentment else None,
        return_memo_date=dishonour.return_memo_date if dishonour else None,
        bank_info_received_date=dishonour.bank_info_received_date if dishonour else None,
        notice_dispatch_date=facts.notice.dispatch_date,
        notice_delivered_on=facts.notice.delivered_on,
        notice_returned_unclaimed=facts.notice.returned_unclaimed,
        notice_refused=facts.notice.refused,
        complaint_date=facts.filing.intended_or_actual_complaint_date,
    )
