# LLD — Drafting Module, Track 1: Cheque Bounce (S.138 NI Act)

Status: design for review. Nothing is built. Spec source: `allLegal_drafting_module_track_specs.docx` (21 Sep 2026), §1 and §2.

---

## 0. Context

allLegal today is a search + reader product (FastAPI + Supabase + OpenSearch/GCS; Next.js frontend). The spec adds a **drafting module**: every litigation track is one configuration of a shared flow (select track → capture facts once → deadline engine → generate fixed-format "F" documents → research group → research-linked "R" documents). Cheque bounce goes first because it is the most rigid and self-contained.

**This LLD covers Phase 1 only: F-side of cheque bounce** (intake, deadline engine, six templates, download). R documents (reply to defence, S.143A application, final submissions) are designed at the data level only, so Phase 1 does not paint us into a corner.

### What exists in the repo (verified)
| Area | State | Implication |
|---|---|---|
| `app/api/routes/{search,cases,groups}.py`, `app/services/supabase.py` | Routes → `supabase_service` (service-role client, bypasses RLS). Ownership enforced in code via `_require_group(user_id, id)` and `current_user["sub"]` | Copy this exact pattern for matters |
| `groups`, `group_items(group_id, case_id)`, `annotations(rects…)` | A group holds **cases + PDF highlights**, not saved paragraphs, and has **no slots** | The spec's "research group with pre-labelled slots + saved paragraphs" does **not exist yet**. It is a Phase 2 prerequisite (§9) |
| `app/services/gcs_service.py` | Signs read URLs for case PDFs (boto3 + HMAC) | Reusable if we ever store generated files; Phase 1 avoids storing them |
| Search returns `chunk_id`, `MatchedChunk`, `chunk_bboxes` | Paragraph-level provenance already exists | Good base for "no invented authority" citations in Phase 2 |
| No SQL migrations in repo | Supabase schema is managed by hand | Add `supabase/migrations/` starting with this module |
| No Dockerfile / LibreOffice on Render | Backend is a plain Python service | Word→PDF conversion is a deploy risk; Phase 1 ships **.docx only** |
| Pydantic 2.5, FastAPI 0.104 | | New models follow `app/schemas/schemas.py` style |

---

## 1. Scope

**In (Phase 1)**
- Track registry + cheque-bounce track config (data, not code).
- Structured fact capture, sectioned, autosaved, validated.
- Deadline engine with status flags (ok / due soon / missed / needs input).
- Templates: legal notice, complaint, complainant's affidavit (S.145), annexure/list of documents, vakalatnama, complaint synopsis (toggleable), **plus** BSA S.63 certificate for electronic evidence (proposed addition, needs lawyer OK).
- Download as editable `.docx`, "DRAFT — for advocate review" until the lawyer finalises.
- Audit trail of what was generated from which facts and template version.

**Out (Phase 1):** R documents, compendium, e-filing integration, PDF export, Hindi/regional-language output, condonation-of-delay application (Phase 1.5), multi-user matters.

---

## 2. Architecture

```
frontend  /drafting/...  (wizard)         reads track config → renders steps dynamically
   │  REST (Supabase JWT, same as /api/groups)
backend   app/api/routes/drafting.py       thin routes, ownership gate
          app/drafting/
            registry.py                    loads track configs, caches
            tracks/cheque_bounce/
              track.yaml                   stages, fields, deadline rules, doc list, research slots
              templates/*.docx             docxtpl templates (Word-editable by lawyers)
            models/cheque_bounce.py        Pydantic fact model (source of truth for validation)
            deadlines/engine.py            pure functions, no I/O
            deadlines/calendar.py          court-holiday lookup, month arithmetic
            render/docx_renderer.py        docxtpl wrapper, conditional blocks, missing-field markers
            render/formatters.py           Indian numbering, amount-in-words, date formats, ordinals
            validation/rules.py            cross-field legal checks (blocking vs warning)
          app/services/supabase.py         + matter CRUD methods (same style as groups)
```

Design rules
1. **Track = config.** Adding "S.80 CPC" later means a new folder, not new routes. The engine, renderer and API never mention "cheque".
2. **Deadline engine is pure** (dates in → results out). No DB, no clock except an injected `today`. This is what gets exhaustively unit-tested.
3. **Templates are `.docx` with Jinja tags (docxtpl)**, so the reviewing lawyer edits wording in Word and we never re-deploy code for a wording change. Each template carries a semver; the version is recorded on every generation.
4. **Missing data never silently disappears.** Empty required values render as a highlighted `[●  complainant address  ●]` marker and appear in a "gaps" list returned with the file.
5. **No stored client documents in Phase 1.** We store facts + template version; the `.docx` is rendered on demand. Less confidential data at rest, no GCS write path needed.

---

## 3. Data model (new migration `supabase/migrations/0001_drafting.sql`)

```sql
create table matters (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,                       -- JWT sub; ownership gate in code (service-role bypasses RLS)
  track_key text not null,                     -- 'cheque_bounce'
  title text not null,                         -- "Sharma v. Verma Traders"
  facts jsonb not null default '{}',           -- validated against the track's Pydantic model
  facts_schema_version int not null default 1,
  research_group_id uuid references groups(id) on delete set null,  -- Phase 2 link
  status text not null default 'draft',        -- draft | in_progress | filed | closed
  created_at timestamptz default now(), updated_at timestamptz default now()
);
create index on matters(user_id, updated_at desc);

create table matter_documents (                -- audit + finalisation record, NOT file storage
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references matters(id) on delete cascade,
  user_id uuid not null,
  template_key text not null,                  -- 'legal_notice'
  template_version text not null,              -- '1.0.0'
  facts_hash text not null,                    -- sha256 of canonical facts JSON at render time
  gaps jsonb not null default '[]',            -- missing required fields at render time
  finalised_at timestamptz,                    -- lawyer attestation (null = draft)
  created_at timestamptz default now()
);

create table court_holidays (                  -- for deadline roll-forward; seeded per state
  state text not null, court_type text not null default 'district',
  holiday_date date not null, name text,
  primary key (state, court_type, holiday_date)
);
```
RLS: enable and deny-all for anon (service role is used, same as `groups`). Facts JSON is PII plus privileged material — see §10.

**Phase 2 tables (design only, not built now):** `group_slots(id, group_id, track_key, slot_key, label)` and `group_paragraphs(id, group_id, slot_id, case_id, chunk_id, text_snapshot, pinpoint jsonb, note)`. Snapshot the paragraph text and pinpoint at save time so later re-indexing cannot change what the lawyer cited.

---

## 4. Track config (`tracks/cheque_bounce/track.yaml`, abridged)

```yaml
key: cheque_bounce
title: "Cheque bounce (S.138 NI Act)"
facts_model: app.drafting.models.cheque_bounce.ChequeBounceFacts
statute_regime: fixed            # NI Act has no CrPC/BNSS split, but the *procedural* refs do — see §8
stages:
  - {key: parties,     label: "Parties",              sections: [complainant, accused, advocate]}
  - {key: transaction, label: "Underlying transaction", sections: [transaction]}
  - {key: instrument,  label: "Cheque & dishonour",    sections: [cheques, presentment, dishonour]}
  - {key: notice,      label: "Legal notice",          sections: [notice, reply]}
  - {key: filing,      label: "Court & filing",        sections: [forum, filing]}
deadlines: [cheque_validity, notice_deadline, payment_window, complaint_window]
documents:
  - {key: legal_notice,   template: legal_notice.docx,  requires: [complainant, accused, transaction, cheques, dishonour], stage: pre_notice}
  - {key: complaint,      template: complaint.docx,     requires: [..., notice], blocks_if_missing: [notice.delivered_on|notice.dispatch_proof]}
  - {key: affidavit_s145, template: affidavit.docx}
  - {key: synopsis,       template: synopsis.docx,      feature_flag: synopsis_mandatory}   # Sanjabij Tari flag
  - {key: list_of_docs,   template: annexures.docx}
  - {key: vakalatnama,    template: vakalatnama.docx}
  - {key: bsa63_certificate, template: bsa63.docx,      when: "notice.mode includes email|whatsapp or any electronic exhibit"}
research_slots:                  # opened in Phase 2; declared now so the config is complete
  - presumption_118_139
  - legally_enforceable_debt
  - territorial_jurisdiction_142_2
  - director_partner_liability_141
  - likely_defences
```

---

## 5. Fact model (`models/cheque_bounce.py`)

Pydantic models, every field optional at save time (autosave), required at generate time per document (`requires`). Sections:

- **complainant**: kind (`individual | proprietorship | partnership | company | llp | trust`), name, parentage/designation, age, address, PAN (optional), authorised representative (name, designation, authority document ref) — required when not an individual.
- **accused**: same shape; if `company/firm`: `directors[]` (name, designation, address, `in_charge_of_business: bool`, `basis` e.g. signatory) → drives S.141 conditional block; `cheque_signatory` flag per person.
- **advocate**: name, enrolment no., state bar council, address, mobile, email, court-complex/chamber no.
- **transaction**: nature (`loan | goods_supplied | services | rent | advance | other`), date(s), amount, mode of payment (`bank_transfer | cheque | cash`), cash amount (for S.269SS check, threshold ₹20,000), agreement/invoice refs, narrative (free text, lawyer-editable), interest claimed (rate, from date).
- **cheques[]**: number, date, amount, drawer bank + branch + IFSC, account holder, payee, in-favour-of; `relied_on: bool`.
- **presentment[]** per cheque: date, presenting bank + branch (payee's bank → forum under S.142(2)), mode.
- **dishonour[]** per presentment: return-memo date, memo no., reason code/text (`funds_insufficient | exceeds_arrangement | account_closed | stop_payment | signature_differs | other`), **date the complainant received the bank's information** (the statutory trigger — see §8 item 1).
- **notice**: dispatch date(s), modes (`speed_post | registered_post | courier | email | whatsapp | hand`), addressee address used, postal receipt/consignment no., tracking status, **delivered_on** (or `returned_unclaimed | refused`), amount demanded (cheque amount + optional interest/costs shown separately).
- **reply**: received? date, summary, denies liability? (informs Phase 2).
- **forum**: state, district, court complex, court name — from a lookup, not free text (so cause title and holiday calendar stay consistent).
- **filing**: intended/actual complaint date, earlier proceedings on same cheque, other pending S.138 matters against same accused, compounding stance (optional).

---

## 6. Deadline engine (`deadlines/engine.py`)

Signature: `compute(facts, today, holidays) -> list[DeadlineResult]`.

```python
@dataclass
class DeadlineResult:
    key: str
    label: str
    status: Literal["needs_input","ok","due_soon","missed","not_applicable"]
    safe_by: date | None        # conservative (earlier) reading — what the UI leads with
    outer_limit: date | None    # most generous defensible reading — shown as secondary
    condonable: bool | None     # can the court excuse a miss?
    basis: str                  # human-readable derivation, e.g. "30 days from 2026-03-04 (receipt of bank memo)"
    authority: str              # provision text, e.g. "S.138 proviso (b) NI Act"
    warnings: list[str]
```

Rules (parameters live in `track.yaml`, not hard-coded, so a reviewer can change a number without a deploy):

| # | Deadline | Anchor → rule | Notes |
|---|---|---|---|
| 1 | Cheque validity | cheque date → +3 calendar months | Status `missed` if the earliest relied presentment is after it. `safe_by` = same date minus 1 day; `outer_limit` = same date. **Also check** the statutory six-month ceiling in proviso (a) — see §8 item 2 |
| 2 | Notice deadline | date complainant received bank's dishonour info → +30 days | `safe_by` = day 30. Not condonable (treated as mandatory) → `condonable=false`; flag |
| 3 | Payment window | notice `delivered_on` → +15 days | If only dispatch date is known: `needs_input` + optional deemed-delivery estimate (config `deemed_delivery_days`, warns "confirm with tracking"). Refused/unclaimed → treated as served, warning |
| 4 | Complaint window | day after payment window ends = cause-of-action date → +1 month | `safe_by` = same day-of-month less one day; `outer_limit` = one calendar month. `condonable=true` (proviso to S.142(1)(b)) |

Calendar rules (`calendar.py`)
- **Day counting:** exclude the anchor day (Limitation Act S.12 convention), include the last day. Configurable per rule for the conservative/outer readings.
- **Months:** `add_months` clamps to month end (31 Jan + 1 month → 28/29 Feb); returns both readings.
- **Court-closed roll-forward:** applied **only** to the *filing* deadline (#4) using `court_holidays` for the forum's state; **not** to notice sending (#2) or validity (#1), since no court is involved. Rolled dates are reported as `outer_limit`, never as `safe_by`. (Lawyer to confirm — §8 item 4.)
- **Multiple presentments:** engine runs per relied-upon presentment; UI shows the one the lawyer marks `relied_on`, and warns when another presentment is also inside its own windows.
- **Status:** `missed` if `today > outer_limit`; `due_soon` if within 7 days of `safe_by` (configurable); a `safe_by` passed but `outer_limit` not yet → `due_soon` with a "conservative date passed" warning.

Test vectors to hard-code as unit tests (each verified by a lawyer): month-end clamping, leap year, deadline on Sunday/holiday, 30th day = notice date, notice dispatched day 31, refused service, two presentments, company accused.

---

## 7. Document rendering

- `docxtpl` renders templates with a context built from `facts` + computed values (`deadlines`, `amount_in_words`, `forum.cause_title`).
- **Conditional blocks** with Jinja `{% if accused.kind in ['company','firm'] %}…{% endif %}`: S.141 averments, authorised-signatory clause, "per pro" verification, jurisdiction paragraph variants.
- **Formatters:** `₹ 4,50,000/- (Rupees Four Lakh Fifty Thousand only)` (Indian grouping + `num2words(lang='en_IN')`), ordinals for dates ("4th March, 2026"), multi-cheque tabular block.
- **Draft posture:** header "DRAFT — FOR ADVOCATE REVIEW" and footer with template version + facts hash until `finalised_at` is set; finalising re-renders without the header. Finalising records the lawyer's attestation ("I have reviewed and adopt this draft") — the product never presents output as final on its own.
- **Gaps report** returned in the response header/JSON: list of unfilled required fields and hard-validation warnings.

New dependencies: `docxtpl`, `python-docx`, `num2words`, `PyYAML`. (No LibreOffice; PDF is Phase 1.5 via a Dockerised worker or client-side print.)

---

## 8. Legal-correctness rules (encoded in `validation/rules.py`)

Blocking = generation refused; Warning = generated with visible note.

| Rule | Type |
|---|---|
| Cheque relied on is presented within validity (§6 #1) | Blocking for complaint; warning for notice |
| Notice dispatch date ≤ notice deadline | Blocking for complaint (warn with condonation caveat) |
| Complaint date ≥ payment-window end + 1 (no premature complaint) | Blocking |
| Notice amount demanded ≥ cheque amount and cheque amount stated separately from interest/costs | Warning |
| Dishonour reason is one S.138 covers (insufficiency / exceeds arrangement); `stop_payment`, `account_closed`, `signature_differs` need a research-slot prompt | Warning + flag |
| Accused is company/firm and no director/partner with "in-charge" basis captured | Blocking for complaint (S.141) |
| Cash loan > ₹20,000 (S.269SS) — show a note that non-compliance does not by itself defeat the debt (Sanjabij Tari flag) | Warning |
| Presenting bank branch missing → territorial jurisdiction paragraph cannot be generated | Blocking |
| Any date in the future, or dishonour before presentment, or cheque date after presentment | Blocking |

**Points where the spec itself needs correcting or confirming before build** (raise with the reviewer; not asserted as fact):
1. **Notice trigger.** Spec §2.1 anchors the 30 days on the "return memo date". S.138 proviso (b) runs from *receipt of information from the bank*. We capture both dates; anchor on the later-known statutory one, default to the memo date only when the receipt date is blank, and warn.
2. **Cheque validity.** Spec says 3 months. S.138 proviso (a) says the *earlier* of six months from drawing or the validity period. Since 2012 the RBI/banking validity is 3 months, so "3 months" is the operative number, but the statutory wording should be cited in `authority`.
3. **BNSS section mapping.** Spec §2 lists "S.223 BNSS (cognizance) / S.204 CrPC". My understanding is S.223 BNSS corresponds to S.200 CrPC (examination of complainant; its proviso on hearing the accused before cognizance) while cognizance is S.210 BNSS (S.190 CrPC) and issue of process is S.227 BNSS (S.204 CrPC). Confirm against the bare act before any template cites a BNSS section.
4. **Weekends/holidays.** Whether roll-forward for court holidays applies to the one-month filing window (Limitation Act S.4 / General Clauses Act S.10) in S.138 practice.
5. **Deemed service** by registered post (presumption of service at correct address) and unclaimed/refused envelopes — lawyer to confirm the rule and any default `deemed_delivery_days`.
6. **Sanjabij Tari v. Kishore S. Borcar, 2025 INSC 1158** (synopsis, no pre-cognizance summons, e-service, compounding costs): treat the synopsis template as **feature-flagged**, default ON, per the reviewer's decision on the spec's flag. Read the actual judgment before finalising the synopsis fields.
7. **Jan Vishwas** bills: confirm S.138 is untouched before compounding-guidance text is added.

---

## 9. API (`app/api/routes/drafting.py`, mounted at `/api/drafting`)

| Method & path | Purpose |
|---|---|
| `GET /tracks` | Available tracks (only cheque_bounce enabled) |
| `GET /tracks/{key}` | Stages, field definitions, documents — drives the wizard |
| `POST /matters` `{track_key,title}` | Create matter |
| `GET /matters` | List user's matters |
| `GET /matters/{id}` | Matter + facts + deadlines + document readiness |
| `PATCH /matters/{id}/facts` | Merge one section (validated partially; JSON merge, not overwrite) |
| `GET /matters/{id}/deadlines` | Computed deadline list |
| `POST /matters/{id}/documents/{template_key}` | Render → `.docx` stream + `X-Gaps` header; writes a `matter_documents` row |
| `POST /matters/{id}/documents/{doc_id}/finalise` | Record attestation |
| `DELETE /matters/{id}` | Hard delete (client-data erasure) |

All handlers follow `groups.py`: `Depends(get_current_user)`, a `_require_matter(user_id, matter_id)` gate returning 404 for non-owners, Pydantic request/response models in `schemas.py`.

**Phase 2 additions (not now):** `GET/POST /matters/{id}/research/slots`, `POST /groups/{id}/paragraphs`, `POST /matters/{id}/documents/{template_key}` accepting `use_paragraphs=true`.

---

## 10. Frontend (`frontend/app/(app)/drafting/`)

Read `frontend/AGENTS.md` / `frontend/CLAUDE.md` first (this repo's Next.js version differs from common assumptions).

- `drafting/page.tsx` — matter list + "New matter" (track picker).
- `drafting/[matterId]/page.tsx` — wizard: left rail = stages from track config, centre = section forms generated from field definitions, right rail = **live deadline panel** (colour-coded ok / due soon / missed) and **document readiness** list.
- Components: `DeadlinePanel`, `DocumentList` (Generate / Download / Finalise), `GapsDialog`, `SectionForm` (config-driven), `DirectorsTable` (repeating rows for S.141).
- Autosave per section (debounced `PATCH`), optimistic UI, visible "saved" state.
- API client additions in `frontend/lib/api.ts`; types in `frontend/lib/drafting/types.ts` mirroring the schemas.

---

## 11. Security, privacy, professional-conduct guardrails

- Facts contain client names, addresses, bank details and privileged narrative. Keep them **only** in `matters.facts`; never log fact bodies (existing request logger logs path + query only — keep it that way; do not send facts as query params).
- Supabase region and retention: confirm data location; provide delete matter (hard delete) for DPDP Act 2023 erasure/withdrawal requests; keep IFSC/account numbers to last-4 where the template does not need the full number.
- Positioning: the tool is for advocates (enrolment number captured); every output carries the draft banner; finalisation is an explicit lawyer act. No text is presented as legal advice.
- Templates never cite case law in Phase 1 (F documents only). Phase 2 R documents may cite only saved, snapshotted paragraphs (spec §1.2).

---

## 12. Testing

- **Unit (pytest):** deadline engine (parametrised vectors in §6), calendar/month clamping, formatters (Indian grouping/words), validation rules.
- **Golden files:** render each template with 3–5 fixture matters (individual v individual; company accused; multiple cheques; refused notice; electronic notice) → compare extracted text against lawyer-approved goldens.
- **Route tests:** ownership (user B cannot read/patch/render user A's matter → 404), partial facts, gaps header.
- **Manual/E2E:** run the wizard against one real, anonymised past cheque-bounce file with a lawyer beside you (see §14).

---

## 13. Build order

| Step | Deliverable | Files |
|---|---|---|
| M0 | Migration + seed of holidays for pilot state(s) | `supabase/migrations/0001_drafting.sql` |
| M1 | Fact model + registry + config loader + matter CRUD routes | `app/drafting/models`, `registry.py`, `routes/drafting.py`, `schemas.py`, `supabase.py` |
| M2 | Deadline engine + tests (lawyer signs off vectors) | `app/drafting/deadlines/*` |
| M3 | Renderer + formatters + **legal notice** template (first end-to-end slice) | `render/*`, `templates/legal_notice.docx` |
| M4 | Complaint, affidavit, annexure index, vakalatnama, synopsis, BSA S.63 templates | `templates/*.docx` |
| M5 | Validation rules + gaps report | `validation/rules.py` |
| M6 | Frontend wizard + deadline panel | `frontend/app/(app)/drafting/*` |
| M7 | Lawyer pilot on real matters; fix wording; freeze template v1.0.0 | — |
| Phase 2 | Group slots + saved paragraphs → R documents; PDF export | separate LLD |

**Start with M1–M3 vertical slice on the legal notice alone**: it is the first document chronologically, has no dependencies on the notice-service facts, and proves intake → deadlines → docx end to end.

---

## 14. What we need from outside to make the output legally usable

### A. Authoritative sources (a lawyer/researcher supplies; we do not paraphrase from memory)
1. Bare-act text (current, as amended) from India Code / official gazette: **NI Act 1881** (ss.138–147, incl. 2002, 2015, 2018 amendments), **Limitation Act 1963** (ss.4, 5, 12), **General Clauses Act** (ss.10, 27), **BNSS 2023 ↔ CrPC 1973 concordance** for every procedural section cited, **Bharatiya Sakshya Adhiniyam 2023 s.63** (and s.65B Evidence Act for older matters), **Income Tax Act s.269SS** (cash loans).
2. The judgment text of *Sanjabij Tari v. Kishore S. Borcar* (2025 INSC 1158) and the directions as they read, plus any High Court circulars implementing it for the pilot state.
3. Landmark authorities the notice/complaint conventionally rely on (presumption, blank signed cheque, deemed service, jurisdiction, S.141 pleading, successive presentments). These become Phase 2 research slots — we do **not** hard-code them into F templates.

### B. Court-specific format inputs (biggest gap between "correct" and "acceptable to the registry")
1. **Pilot jurisdiction decision** — one state/district first (e.g. Delhi, Mumbai, Ahmedabad). Formats differ per High Court's rules for subordinate courts.
2. That High Court's **Civil/Criminal Rules & Orders** clauses on: complaint form, cause-title layout, affidavit/verification wording, number of copies, language, paper size/margins/font/spacing, paginated index, vakalatnama form and court-fee/welfare-stamp (some states require Advocates' Welfare Fund stamp on vakalatnama).
3. **District Court e-filing / eCourts notice** for that pilot: allowed file formats, size limits, bookmark/OCR requirements, synopsis and e-service instructions after Sanjabij Tari.
4. **Court-fee schedule** applicable to S.138 complaints in that state (some states charge; many don't).
5. **Court and court-complex master list** (state → district → complex → court name/number) and an **annual court-holiday/vacation calendar** per state (gazetted + court-specific).

### C. Sample documents (format and phrasing reference), in `.docx` not scanned PDF
1. **3–5 real, anonymised, court-accepted sets** from 2–3 practising advocates in the pilot court: legal notice, complaint, affidavit-in-lieu-of-evidence, list of documents, vakalatnama, synopsis (post-Nov 2025 if any), BSA S.63 certificate.
2. A **reply-to-notice** and one **defence-stage document** (for Phase 2 slot design).
3. Variants: company accused, partnership, proprietorship, multiple cheques, notice returned unclaimed, notice served by email/WhatsApp.
4. Lawyers' **standard clause bank**: interest, costs, compensation prayer, S.143A interim compensation prayer, S.147 compounding statement, jurisdiction paragraph.

### D. Structured reference data we will encode
- Bank return-memo **reason codes** (RBI standard list) → S.138 applicability mapping.
- Postal rules: Speed Post/registered post deemed-delivery norms and India Post tracking terminology (delivered / refused / unclaimed / left).
- Notice-addressee conventions for companies (registered office vs. factory vs. director's residence).

### E. Sign-off process (what makes it "legally usable" rather than "plausible")
1. **Named reviewing advocate(s)** per template with a written **template approval record** (template key, version, date, reviewer, jurisdiction it is approved for). Show "Approved for: [state] — v1.0.0 — [date]" on the template card; disable generation for jurisdictions with no approved template.
2. A **checklist per document** (mandatory averments, prayer, verification, signature blocks, annexure references) used at review; the same checklist becomes our golden-test assertions.
3. A **change log** and re-approval rule whenever law changes (new SC directions, amendments) — Jan Vishwas, Sanjabij Tari implementation, BNSS practice notes.
4. **Disclaimers**: not legal advice, for use by enrolled advocates, output requires advocate review before filing; explicit finalisation click.
5. Record what was **not** verified (jurisdictions without an approved template) in the UI rather than in a footnote.

### F. Compliance / business inputs
- DPDP Act 2023 position (data location, retention, erasure), an advocate–client confidentiality statement, terms of use that address the Advocates Act / Bar Council rules on technology and solicitation.
- Decision on **language** (English only vs Hindi/regional for subordinate courts) — affects templates 2×–5×.

---

## 15. Verification (once built)

1. `pytest app/drafting` — deadline vectors, validation, formatters all green.
2. `uvicorn main:app`, then with a real Supabase JWT: create matter → PATCH each section → `GET deadlines` shows the expected four rows → `POST documents/legal_notice` returns a `.docx`.
3. Open the `.docx` in Word: cause title, amounts in words, conditional S.141 block, highlighted gaps markers, draft banner.
4. Cross-user check: a second account gets 404 on the first account's matter.
5. Run one anonymised historical matter end to end with a lawyer; compare generated notice/complaint with what was actually filed; every difference is either a template fix or a documented judgement call.
