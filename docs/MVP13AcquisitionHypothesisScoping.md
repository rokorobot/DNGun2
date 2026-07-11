# MVP 1.3 Scoping — Acquisition Hypothesis & Messaging Intelligence

Status: **RATIFIED 2026-07-11 — governing contract for MVP 1.3 implementation.**

This document ratifies the contract, lifecycle, evidence boundaries, and
governance for MVP 1.3 before implementation. Rulings were set by the
operator on 2026-07-11 (initial rulings and ratification rulings) and are
binding on implementation.

---

## Purpose

An **Acquisition Hypothesis** is a durable, governed reasoning object that
states *why a specific company may acquire a specific domain offer*. It is
the unit of reasoning that sits between evidence and outreach:

```text
Evidence Ledger
    ↓
Candidate Hypothesis
    ↓
PROPOSED — canonical content freezes
    ↓
Human Review
    ↓
APPROVED
    ↓
Optional Active Selection
    ↓
Role-aware Narrative
    ↓
Message Draft
    ↓
Message Review
```

Empirical validation remains dormant until MVP 1.4:

```text
Campaign Outcomes → empirical_confidence → SUPPORTED / WEAKENED / REJECTED
```

The hypothesis is the contract. Messaging consumes it; it never defines it.

---

## MVP 1.3A — Acquisition Hypothesis

### Binding

A hypothesis binds primarily to `Offer × Prospect`, with an optional
decision-maker refinement:

```text
offer_id            required   FK offers.id
prospect_id         required   FK prospects.id
decision_maker_id   nullable   FK decision_makers.id
```

Rules:

- The company-level motivation lives on the `Offer × Prospect` pair. The
  decision maker changes *how the argument is presented*, not why it exists.
- A hypothesis is **never** bound to an offer-fit calculation record. Fit
  scores are recalculable; the hypothesis is a durable, independently
  reviewable object that must survive fit recalculation.
- Multiple competing hypotheses may exist for the same
  `offer_id × prospect_id`, but exactly **one** may be the active outreach
  hypothesis at a time (see Active Selection).
- A decision-maker-specific hypothesis must declare which company-level
  hypothesis it refines via `refines_hypothesis_id` (nullable FK,
  self-referential). It may refine, but must not silently contradict, its
  parent. In MVP 1.3 contradiction detection is a human review
  responsibility; the structural link exists so the reviewer always sees
  the parent side by side.

Example:

```text
Offer × Prospect:
RobotStore.app × Robotics Marketplace Ltd.

Hypothesis:
The company is expanding from integration services into ecommerce and may
benefit from a category-defining marketplace domain.

Optional decision-maker refinement (Founder):
Recipient framing: long-term category ownership and brand equity.
```

### Data model

New table `acquisition_hypotheses` (conventions follow existing models:
string prefixed IDs, ISO-8601 UTC string timestamps):

| Field | Type | Notes |
|---|---|---|
| id | str PK | prefix `AH` |
| offer_id | str FK | offers.id, ON DELETE CASCADE |
| prospect_id | str FK | prospects.id, ON DELETE CASCADE |
| decision_maker_id | str FK nullable | decision_makers.id, ON DELETE SET NULL |
| refines_hypothesis_id | str FK nullable | acquisition_hypotheses.id |
| statement | text | the falsifiable company-level claim (canonical) |
| recipient_framing | text nullable | decision-maker-specific presentation angle (canonical) |
| source | str | `HUMAN` \| `DETERMINISTIC` \| `LLM_ASSISTED` |
| provider / model | str nullable | populated only for LLM_ASSISTED (mirrors offer proposals) |
| status | str | lifecycle below |
| is_active | bool | active outreach hypothesis flag |
| reasoning_confidence | int 0–100 nullable | NULL until computed; see Confidence |
| reasoning_confidence_explanation | text JSON list | provenance lines |
| empirical_confidence | float nullable | **reserved, always NULL in MVP 1.3** |
| reviewer_assessment | str nullable | `STRONG` \| `ADEQUATE` \| `WEAK` — human judgment, set at review; never feeds the computed score |
| superseded_by_id | str FK nullable | successor hypothesis |
| reviewed_at / review_notes | str nullable | set at approval/rejection |
| created_at / updated_at | str | |

New table `hypothesis_evidence_links`:

| Field | Type | Notes |
|---|---|---|
| id | str PK | prefix `HEL` |
| hypothesis_id | str FK | acquisition_hypotheses.id, ON DELETE CASCADE |
| evidence_entry_id | str FK | evidence_entries.id, ON DELETE RESTRICT |
| note | text nullable | why this evidence supports the claim |
| created_at | str | |
| — | unique | (hypothesis_id, evidence_entry_id) |

New table `hypothesis_audit_events` (ruling 2 — in-place corrections to
non-canonical metadata are permitted only with an audit trail):

| Field | Type | Notes |
|---|---|---|
| id | str PK | prefix `HAE` |
| hypothesis_id | str FK | acquisition_hypotheses.id, ON DELETE CASCADE |
| event_type | str | e.g. `METADATA_CORRECTED`, `STATUS_CHANGED`, `ACTIVATED`, `DEACTIVATED`, `SUPERSEDED` |
| detail | text nullable | what changed and why |
| created_at | str | |

Amendment to `evidence_entries` (ruling 3 — lifecycle states over
destructive deletion):

| Field | Type | Notes |
|---|---|---|
| status | str NOT NULL default `ACTIVE` | `ACTIVE` \| `ARCHIVED` \| `RETRACTED` \| `INVALIDATED` |

Evidence is referenced by ID only — never copied into a JSON blob on the
hypothesis. `ON DELETE RESTRICT` on the evidence side enforces invariant 9
and ruling 3: evidence that supports a reviewed or used hypothesis —
including superseded and rejected ones — is part of the historical
decision trail and cannot be physically deleted while referenced. Evidence
that is no longer considered valid transitions to `RETRACTED` or
`INVALIDATED`; this preserves the distinction between *evidence no longer
valid* and *evidence that never existed*.

Database constraint for active selection: partial unique index

```sql
CREATE UNIQUE INDEX uq_active_hypothesis
ON acquisition_hypotheses (offer_id, prospect_id)
WHERE is_active = 1;
```

### Lifecycle

```text
DRAFT → PROPOSED → APPROVED → VALIDATING → SUPPORTED
                 ↘ REJECTED              ↘ WEAKENED
any post-DRAFT state → SUPERSEDED
```

| Status | Meaning | Set by |
|---|---|---|
| DRAFT | Being authored; freely editable | Human, or generator output pre-submission |
| PROPOSED | Submitted to the review gate; canonical content and evidence set freeze | Human action only |
| APPROVED | A human accepts it as reasonable enough to use | Human action only |
| REJECTED | Human declines it; terminal (may be cloned to a new DRAFT) | Human action only |
| VALIDATING | Active in outreach with outcomes pending | **Dormant in 1.3** — entered only by MVP 1.4 outcome integration |
| SUPPORTED / WEAKENED | Outcome evidence supports / undermines the claim | **Dormant in 1.3** — MVP 1.4 only |
| SUPERSEDED | Replaced by a successor; terminal, immutable | System, on successor approval or explicit supersede |

MVP 1.3 implements `DRAFT / PROPOSED / APPROVED / REJECTED / SUPERSEDED`
plus active selection. **Dormant-state safeguard (ratified):** the dormant
states are defined in the schema and enums now so the contract is stable,
but the service layer must make them unreachable — no MVP 1.3 route or
repository method may set `VALIDATING`, `SUPPORTED`, or `WEAKENED`, and
transition tests must prove these states cannot be entered before outcome
integration exists.

**Approval ≠ validation.** Approval means a human accepts the reasoning.
Validation means external campaign outcomes provide evidence about whether
it predicts buyer behavior. These are never conflated.

### Evidence boundary

Internal actions — drafting, LLM generation, human approval, editing,
selecting for outreach — may change **workflow status only**. They must
never increase outcome-derived confidence.

Only external observations may eventually affect empirical confidence
(`REPLIED, INTERESTED, PRICE_REQUEST, NEGOTIATION, OFFER_RECEIVED,
SALE_COMPLETED, DECLINED, NO_RESPONSE` after a defined observation
window). That state machine is **MVP 1.4**; MVP 1.3 therefore ships:

```text
reasoning_confidence   = strength and completeness of current supporting
                         evidence (available now)
empirical_confidence   = outcome-backed predictive confidence
                         (schema-reserved, always NULL until MVP 1.4)
```

These two scores are never collapsed into one.

### Reasoning confidence (ratified ruling 1)

`reasoning_confidence` is **computed deterministically** from linked
evidence only, using a documented rubric:

- evidence count with diminishing returns
- evidence-type diversity
- recency
- relevance to the specific offer–prospect pair
- decision-maker coverage, where applicable
- penalties for stale, contradictory, or weakly sourced evidence

Every computation writes `reasoning_confidence_explanation` lines showing
exactly how the score was derived, mirroring score provenance elsewhere in
DNGun.

Prohibited:

- manual score entry
- reviewer score inflation
- LLM-selected or LLM-adjusted confidence
- approval itself increasing the score

Human judgment is preserved in a **separate** field,
`reviewer_assessment` (`STRONG` / `ADEQUATE` / `WEAK`), optionally with a
structured rationale in `review_notes`. The reviewer's assessment never
feeds the computed score.

**Freeze point:** the canonical evidence set and the computed
`reasoning_confidence` freeze when the hypothesis enters `PROPOSED` — the
stored value is what the reviewer reviewed against.

### Generation authority

Three sources, one gate:

```text
HUMAN | DETERMINISTIC | LLM_ASSISTED  →  all enter PROPOSED  →  human review
```

- **No source receives automatic approval.**
- The **deterministic engine** is the default and permanent fallback. It
  synthesizes a candidate statement from the approved offer intelligence
  profile, prospect segment/signals, and existing evidence entries — and
  may cite only evidence IDs that exist.
- The **LLM assist** is optional and env-gated (same pattern as
  `offer_llm.py`: strict JSON schema, timeout, returns None on any failure
  → deterministic fallback). It receives only scoped, already-recorded
  evidence text as input, and must return the subset of evidence IDs it
  relied on. The LLM must not:
  - invent evidence,
  - activate a hypothesis,
  - raise any confidence value,
  - select the final outreach hypothesis,
  - generate a send-ready message without review.

### Active selection (ratified safeguard)

Activation preconditions — all enforced in the repository layer, backed by
the partial unique index:

```text
status == APPROVED
if refines_hypothesis_id is set: the parent hypothesis is APPROVED
at least one evidence link exists whose evidence entry is ACTIVE
reasoning_confidence is not NULL (has been computed)
```

- A `DRAFT`, `PROPOSED`, `REJECTED`, or `SUPERSEDED` hypothesis must never
  become active.
- Activating one deactivates the previously active hypothesis for the same
  `offer_id × prospect_id` (it remains APPROVED, just not active).
- Activation and deactivation write `hypothesis_audit_events` entries.

### Immutability, corrections & supersession (ratified ruling 2)

- `DRAFT` is freely editable.
- From `PROPOSED` onward, the **canonical content** — `statement`,
  `recipient_framing`, the evidence set, the bindings, and the frozen
  `reasoning_confidence` — is immutable, **even for a typo**. Otherwise the
  system can no longer prove exactly what the reviewer approved.

**Requires a new version (supersession) and full review:**

- changing the hypothesis claim
- adding or removing evidence
- changing the prospect, offer, or decision-maker binding
- altering the acquisition motivation
- changing reasoning that could affect outreach
- changing the computed confidence basis

**May be corrected in place, with a `hypothesis_audit_events` record:**

- spelling or formatting in non-canonical display metadata
- correcting an external link without changing the referenced evidence
- administrative labels or operator notes explicitly outside the approved
  claim

There is **no fast-path** around review for successors: every superseding
hypothesis re-enters the full review gate. Superseding never deletes or
detaches the predecessor's evidence links — the full evidence trail of
every hypothesis ever used remains auditable.

### API surface (sketch)

```text
POST   /offers/{offer_id}/prospects/{prospect_id}/hypotheses         create DRAFT (source=HUMAN)
POST   /offers/{offer_id}/prospects/{prospect_id}/hypotheses/generate  deterministic or LLM draft
GET    /offers/{offer_id}/prospects/{prospect_id}/hypotheses         list (all statuses)
GET    /hypotheses/{id}
PUT    /hypotheses/{id}                                              DRAFT only
POST   /hypotheses/{id}/evidence/{evidence_entry_id}                 link (DRAFT only)
DELETE /hypotheses/{id}/evidence/{evidence_entry_id}                 unlink (DRAFT only)
POST   /hypotheses/{id}/propose          freezes canonical content + confidence
POST   /hypotheses/{id}/approve          requires ≥1 evidence link (invariant 1); accepts reviewer_assessment
POST   /hypotheses/{id}/reject
POST   /hypotheses/{id}/activate         preconditions above; swaps active
POST   /hypotheses/{id}/supersede        creates successor DRAFT
```

### Workbench UI

A Hypothesis Workbench view (new view in the existing console shell):
list per offer×prospect with status and active badge; detail pane showing
statement, framing, linked evidence (fetched by ID from the Evidence
Ledger, with evidence status visible), reasoning-confidence explanation,
and — for refinements — the parent statement side by side; review actions
(propose/approve/reject with reviewer assessment and notes); activate
toggle; generate-draft buttons (deterministic always, LLM when
configured); audit event history.

---

## MVP 1.3B — Messaging Intelligence

Starts **only after 1.3A is implemented and its contract is stable.**
Messaging consumes the hypothesis contract; it must never reshape it.

### Inputs

```text
Approved (and active) Hypothesis
+ Decision Maker role (authority score, rationale)
+ Contact context (available contact paths, confidence, verification)
→ Narrative strategy
→ Draft message
```

### Scope

- **Narrative strategies are rule-registry YAML** (`narrative_strategies.yaml`),
  keyed by role/authority band — consistent with the architecture rule that
  business logic is editable without code changes. Each strategy defines
  tone, emphasis (e.g. founder → category ownership & brand equity;
  operations → cost/continuity), and structure hints.
- `message_drafts` table: id (`MD`), hypothesis_id (FK), decision_maker_id
  (FK), narrative_strategy code, subject, body, status, created_at /
  updated_at, reviewed_at / review_notes.
- Draft generation (deterministic template default; LLM-assist optional,
  same gate) may reference **only** evidence linked to the approved
  hypothesis (invariant 6) plus the recipient's role and contact context.
- Human edit and approval in the workbench. Approved drafts are
  copy/export only.

### Message draft lifecycle (ratified ruling 4)

```text
DRAFT → PROPOSED → APPROVED → USED
      ↘ REJECTED
any post-DRAFT state → SUPERSEDED
```

- `DRAFT` may be edited.
- Entering `PROPOSED` freezes the canonical message text **and its inputs**
  (hypothesis version, narrative strategy, referenced evidence).
- Any later textual change creates a new version (supersession).
- `USED` records exactly what was actually sent or externally delivered.
  A used message may **never** be overwritten.
- Approval does not equal delivery.

This matters because future outcome learning (MVP 1.4) must correlate
results with the exact message used, not with a later edited version.
(In MVP 1.3, marking `USED` is a manual operator action recording an
external send; no delivery integration exists.)

### Explicit non-goals for all of MVP 1.3

- No email sending or delivery integration of any kind (invariant 10).
- No campaign automation, sequencing, or scheduling.
- No outcome learning, outcome recording against hypotheses, or
  empirical-confidence movement (MVP 1.4).
- No scraping or external data acquisition.
- No changes to the offer-fit engine or scoring engine.

---

## Invariants (binding on implementation and tests)

1. **No evidence means no approvable hypothesis.** The approve transition
   requires ≥1 linked evidence entry; enforced in the API layer and tested.
2. **A hypothesis is never itself evidence.** No code path creates an
   Evidence Ledger entry from a hypothesis; evidence entries carry no
   hypothesis-source field.
3. **Human approval does not prove predictive success.** Approval sets
   workflow status only; `empirical_confidence` stays NULL in MVP 1.3.
4. **Only one active hypothesis per `offer_id × prospect_id`.** Repository
   logic + partial unique index + activation preconditions.
5. **DM-specific hypotheses refine, never silently contradict.** They must
   link a parent via `refines_hypothesis_id`; the review UI shows the
   parent statement alongside; an unapproved parent blocks activation.
6. **Messages may reference only evidence attached to the approved
   hypothesis.** Generation inputs are restricted to that set; tested.
7. **LLM output is always a proposal.** LLM-assisted paths can produce
   DRAFT/PROPOSED objects only; no LLM code path touches approve, activate,
   or any confidence field.
8. **Historical hypotheses are immutable after use.** Canonical content
   freezes at PROPOSED; amendment is supersession, never mutation;
   non-canonical metadata corrections require an audit event.
9. **Superseding never deletes the evidence trail.** Links persist;
   `ON DELETE RESTRICT` protects referenced evidence; evidence uses
   lifecycle states (`ACTIVE / ARCHIVED / RETRACTED / INVALIDATED`), never
   physical deletion while referenced.
10. **No email sending enters MVP 1.3.** No SMTP/provider dependency may be
    added; drafts are copy/export only.

Additional ratified safeguards:

- **Dormant states are unreachable in 1.3.** Service-layer enforcement plus
  transition tests proving `VALIDATING / SUPPORTED / WEAKENED` cannot be
  entered before outcome integration exists.
- **Activation preconditions** (APPROVED status, approved parent if
  refinement, ≥1 ACTIVE evidence link, computed reasoning confidence) are
  enforced in the repository layer, not just the UI.

---

## Sequencing & definition of done

Implementation order (each its own scoped commit series, per working
convention):

```text
1.3A-1  Schema + models + migrations (hypotheses, evidence links, audit
        events, evidence status column, partial unique index)
1.3A-2  Repository + lifecycle transitions + reasoning-confidence rubric
        + dormant-state and activation-precondition enforcement
1.3A-3  API endpoints + deterministic generator
1.3A-4  Optional LLM-assist (env-gated) behind the same review gate
1.3A-5  Hypothesis Workbench UI
1.3B-1  narrative_strategies.yaml + rule registry loading
1.3B-2  message_drafts model/repository/API + deterministic drafting
1.3B-3  Messaging workbench UI + optional LLM-assist
```

**1.3A done when:** all invariants 1–5, 7–9 and both safeguards have
passing tests; full loop (create → link evidence → propose → approve →
activate → supersede) works through the live UI; deterministic generation
produces a reviewable draft citing only real evidence IDs; backend suite
green.

**1.3B done when:** an approved active hypothesis + a decision maker with a
contact path yields a role-aware draft in the UI; invariant 6 and 10 tests
pass; message lifecycle freeze/supersession tests pass; a hypothesis-less
or unapproved-hypothesis path cannot produce a draft.

---

## Ratified rulings (2026-07-11)

Resolutions of the four open questions from the draft:

1. **Reasoning confidence:** deterministic and provenance-derived, computed
   only from linked evidence; rubric includes count (diminishing returns),
   type diversity, recency, offer–prospect relevance, DM coverage, and
   penalties for stale/contradictory/weakly sourced evidence. No manual
   entry, no reviewer inflation, no LLM-selected confidence, no score
   increase from approval. Human judgment lives in the separate
   `reviewer_assessment` field. Evidence set and score freeze at PROPOSED.
2. **Supersession boundary:** canonical claim/evidence/binding/reasoning
   changes require a new version and full review — no fast-path. The
   canonical statement is immutable after PROPOSED even for typos.
   Non-canonical display metadata may be corrected in place with an audit
   event.
3. **Evidence deletion:** `ON DELETE RESTRICT` stays; archived/superseded
   hypotheses never release their evidence hold. Evidence transitions
   through lifecycle states (`ACTIVE / ARCHIVED / RETRACTED /
   INVALIDATED`) instead of being deleted while referenced.
4. **Message draft immutability:** approved drafts freeze like hypotheses;
   lifecycle `DRAFT / PROPOSED / APPROVED / USED / SUPERSEDED / REJECTED`;
   PROPOSED freezes canonical text and inputs; USED records exactly what
   was delivered and is never overwritten.
