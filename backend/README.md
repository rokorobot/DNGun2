# DNGun Backend

MVP 0 implements the internal prospect intelligence loop:

1. Create prospects.
2. Add manual tiered signals.
3. Calculate scores with provenance.
4. Define and manually assign Alpha Signals.
5. Create campaign batches.
6. Track campaign outcomes.
7. Add evidence entries.
8. Record confidence updates.

Domain mapping notes:

```sh
cat docs/Phase1DomainMapping.md
```

Run locally (the frontend proxy expects port 8001):

```sh
python -m uvicorn backend.app.main:app --reload --port 8001
```

Run tests:

```sh
pytest backend/tests
```

The default SQLite database is created at `data/dngun.sqlite3`.

No email automation, scraping, auth, billing, or CRM features are included.

Seed MVP 0.1 sample data:

```sh
python backend/scripts/seed_mvp0.py
```

Recalculate stored decision-maker authority scores after rule or
matcher changes (scores are persisted at write time):

```sh
python backend/scripts/recalculate_authority.py
```

Campaign intelligence report:

```text
GET /reports/campaign-intelligence
GET /reports/campaign-intelligence.md
```

Rule registry files:

```text
backend/app/rules/score_bands.yaml
backend/app/rules/signal_taxonomy.yaml
backend/app/rules/alpha_signals.yaml
backend/app/rules/disqualifiers.yaml
```

Rule registry endpoints:

```text
GET /rules
GET /rules/score-bands
GET /rules/alpha-signals
GET /rules/signal-taxonomy
GET /rules/disqualifiers
```

Acquisition hypothesis endpoints (MVP 1.3A-3; contract in
`docs/MVP13AcquisitionHypothesisScoping.md`). Governance violations
return `409`; request bodies cannot set status, confidence, source, or
activation:

```text
POST   /offers/{offer_id}/prospects/{prospect_id}/hypotheses           create DRAFT (HUMAN)
POST   /offers/{offer_id}/prospects/{prospect_id}/hypotheses/generate  deterministic DRAFT
GET    /offers/{offer_id}/prospects/{prospect_id}/hypotheses           list
GET    /hypotheses/{id}                                                detail + evidence + audit + parent
PUT    /hypotheses/{id}                                                DRAFT only
POST   /hypotheses/{id}/evidence/{evidence_entry_id}                   link (DRAFT, ACTIVE evidence)
DELETE /hypotheses/{id}/evidence/{evidence_entry_id}                   unlink (DRAFT)
POST   /hypotheses/{id}/propose | approve | reject | activate | supersede
```
