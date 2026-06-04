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

```powershell
Get-Content docs/Phase1DomainMapping.md
```

Run locally:

```powershell
uvicorn backend.app.main:app --reload
```

Run tests:

```powershell
pytest backend/tests
```

The default SQLite database is created at `data/dngun.sqlite3`.

No email automation, scraping, auth, billing, or CRM features are included.

Seed MVP 0.1 sample data:

```powershell
python backend\scripts\seed_mvp0.py
```

Campaign intelligence report:

```text
GET /reports/campaign-intelligence
GET /reports/campaign-intelligence.md
```
