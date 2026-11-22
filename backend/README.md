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

AI assist without an API key (uses your own Claude chat): `GET
.../hypotheses/assist-prompt` returns a prompt to paste into Claude;
`POST .../hypotheses/assist` with `{"response": "<Claude's answer>"}`
stores it as an `LLM_ASSISTED` DRAFT for normal review. Answers citing
evidence that was not in the prompt are rejected.

## Opportunity Radar (MVP 2.0)

Finds companies in the news that could buy a domain in your portfolio.

1. Import domains (Radar screen, or `POST /portfolio/import` with
   `{"text": "<list or CSV>"}`). CSV columns: `domain` plus optional
   `price, markets, keywords, industry, notes`; comma or semicolon. See
   `backend/sample_data/portfolio_sample.csv`.
2. Each domain gets a watch profile: keywords from its name
   (`robotstore` → robotstore, robot, store) and markets from its ending
   (`.de` → Germany; `.com/.io/.ai/.app` → global). Edit either on screen.
3. Scan: `POST /radar/scan` (all or `{"offer_ids": [...]}`) or the daily
   job `python backend/scripts/run_radar.py`. News comes from the free
   GDELT API (commercial use allowed; one request per 5 s, so ~6 s per
   domain per market). Only headlines naming a company event (funding,
   new company, rebrand, expansion, launch, key hire) that match the
   domain's name or keywords become opportunities.
4. Review at `GET /opportunities`: accept (creates or reuses the
   prospect, adds a source-linked news signal and evidence for the
   offer) or dismiss.

All rules (endings → markets, regions, event words per language,
scoring, the word list used to split names) are in
`backend/app/rules/radar.yaml`.
