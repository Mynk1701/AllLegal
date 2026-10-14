"""
Fact model for the cheque-bounce (S.138 NI Act) track.

This is the single source of truth for what "capture facts" (LLD stage 2)
collects. Every field is Optional so a matter can be saved section-by-section
as the lawyer fills it in (PATCH /matters/{id}/facts merges one section at a
time) — "required for X" is expressed separately, per document, in
`track.yaml`'s `requires` lists and enforced by `required_sections_for()`
below, not by Pydantic's own required/optional machinery.

Field names mirror the LLD (S.5) exactly so the spec, this model, the YAML
`requires` lists and the templates all use the same vocabulary.
"""
from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

PartyKind = Literal["individual", "proprietorship", "partnership", "company", "llp", "trust"]
NoticeMode = Literal["speed_post", "registered_post", "courier", "email", "whatsapp", "hand"]
DishonourReason = Literal[
    "funds_insufficient",
    "exceeds_arrangement",
    "account_closed",
    "stop_payment",
    "signature_differs",
    "other",
]


class Advocate(BaseModel):
    name: Optional[str] = None
    enrolment_no: Optional[str] = None
    state_bar_council: Optional[str] = None
    address: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    chamber_or_court_complex_no: Optional[str] = None


class AuthorisedRepresentative(BaseModel):
    """Required when a party is not an individual (S.141 NI Act context for
    the accused side; signing authority for the complainant side)."""
    name: Optional[str] = None
    designation: Optional[str] = None
    authority_document_ref: Optional[str] = None


class Director(BaseModel):
    """One director/partner of a corporate/firm accused. `in_charge_of_business`
    and `basis` drive the S.141 pleading — see LLD S.8 ('company/firm accused
    and no director with in-charge basis -> blocking')."""
    name: str
    designation: Optional[str] = None
    address: Optional[str] = None
    in_charge_of_business: bool = False
    basis: Optional[str] = Field(
        None, description="e.g. 'cheque signatory', 'managing director', 'day-to-day affairs'"
    )
    is_cheque_signatory: bool = False


class Party(BaseModel):
    kind: Optional[PartyKind] = None
    name: Optional[str] = None
    parentage_or_designation: Optional[str] = None
    age: Optional[int] = None
    address: Optional[str] = None
    pan: Optional[str] = None
    authorised_representative: Optional[AuthorisedRepresentative] = None
    directors: List[Director] = Field(default_factory=list)


class Transaction(BaseModel):
    nature: Optional[Literal["loan", "goods_supplied", "services", "rent", "advance", "other"]] = None
    transaction_date: Optional[date] = None
    amount: Optional[float] = None
    mode_of_payment: Optional[Literal["bank_transfer", "cheque", "cash"]] = None
    cash_amount: Optional[float] = Field(
        None, description="Portion paid in cash, if any — checked against the S.269SS Income Tax Act threshold"
    )
    agreement_or_invoice_ref: Optional[str] = None
    narrative: Optional[str] = Field(None, description="Free text, lawyer-editable; feeds the complaint's facts section")
    interest_claimed: bool = False
    interest_rate_percent: Optional[float] = None
    interest_from_date: Optional[date] = None


class Cheque(BaseModel):
    number: Optional[str] = None
    cheque_date: Optional[date] = None
    amount: Optional[float] = None
    drawer_bank: Optional[str] = None
    drawer_branch: Optional[str] = None
    ifsc: Optional[str] = None
    account_holder: Optional[str] = None
    payee: Optional[str] = None
    relied_on: bool = Field(True, description="The cheque the deadline engine and templates use")


class Presentment(BaseModel):
    cheque_number: Optional[str] = Field(None, description="Links back to Cheque.number")
    presentment_date: Optional[date] = None
    presenting_bank: Optional[str] = None
    presenting_branch: Optional[str] = Field(
        None, description="Payee's bank branch — drives territorial jurisdiction under S.142(2)"
    )
    mode: Optional[str] = None


class Dishonour(BaseModel):
    cheque_number: Optional[str] = None
    return_memo_date: Optional[date] = None
    return_memo_no: Optional[str] = None
    reason_code: Optional[DishonourReason] = None
    reason_text: Optional[str] = None
    bank_info_received_date: Optional[date] = Field(
        None,
        description=(
            "Date the complainant actually received the bank's information of dishonour — "
            "the statutory trigger for the 30-day notice clock under S.138 proviso (b). "
            "Falls back to return_memo_date (with a warning) if left blank."
        ),
    )


class Notice(BaseModel):
    dispatch_date: Optional[date] = None
    modes: List[NoticeMode] = Field(default_factory=list)
    addressee_address_used: Optional[str] = None
    postal_receipt_no: Optional[str] = None
    tracking_status: Optional[str] = None
    delivered_on: Optional[date] = None
    returned_unclaimed: bool = False
    refused: bool = False
    amount_demanded: Optional[float] = Field(None, description="Cheque amount; interest/costs shown separately")
    interest_or_costs_demanded: Optional[float] = None


class NoticeReply(BaseModel):
    received: bool = False
    received_date: Optional[date] = None
    summary: Optional[str] = None
    denies_liability: Optional[bool] = None


class Forum(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    court_complex: Optional[str] = None
    court_name: Optional[str] = None


class Filing(BaseModel):
    intended_or_actual_complaint_date: Optional[date] = None
    earlier_proceedings_same_cheque: Optional[str] = None
    other_pending_matters_same_accused: Optional[str] = None
    compounding_stance: Optional[str] = None


class ChequeBounceFacts(BaseModel):
    """Root fact object for one cheque-bounce matter. Every section is
    optional at the model level — see module docstring."""

    complainant: Party = Field(default_factory=Party)
    accused: Party = Field(default_factory=Party)
    advocate: Advocate = Field(default_factory=Advocate)
    transaction: Transaction = Field(default_factory=Transaction)
    cheques: List[Cheque] = Field(default_factory=list)
    presentments: List[Presentment] = Field(default_factory=list)
    dishonours: List[Dishonour] = Field(default_factory=list)
    notice: Notice = Field(default_factory=Notice)
    reply: NoticeReply = Field(default_factory=NoticeReply)
    forum: Forum = Field(default_factory=Forum)
    filing: Filing = Field(default_factory=Filing)

    def relied_cheque(self) -> Optional[Cheque]:
        for c in self.cheques:
            if c.relied_on:
                return c
        return self.cheques[0] if self.cheques else None

    def presentment_for(self, cheque_number: Optional[str]) -> Optional[Presentment]:
        for p in self.presentments:
            if p.cheque_number == cheque_number:
                return p
        return self.presentments[0] if self.presentments else None

    def dishonour_for(self, cheque_number: Optional[str]) -> Optional[Dishonour]:
        for d in self.dishonours:
            if d.cheque_number == cheque_number:
                return d
        return self.dishonours[0] if self.dishonours else None

    @model_validator(mode="after")
    def _no_future_dates_relative_to_each_other(self) -> "ChequeBounceFacts":
        """Cheap internal-consistency guard (presentment can't precede the
        cheque, dishonour can't precede presentment). Statute-deadline checks
        live in app/drafting/validation/rules.py, not here — this model only
        rejects data that is self-contradictory regardless of any deadline."""
        cheque = self.relied_cheque()
        if cheque and cheque.cheque_date:
            presentment = self.presentment_for(cheque.number)
            if presentment and presentment.presentment_date:
                if presentment.presentment_date < cheque.cheque_date:
                    raise ValueError("Presentment date cannot be before the cheque's own date.")
                dishonour = self.dishonour_for(cheque.number)
                if dishonour and dishonour.return_memo_date:
                    if dishonour.return_memo_date < presentment.presentment_date:
                        raise ValueError("Return-memo date cannot be before the presentment date.")
        return self
