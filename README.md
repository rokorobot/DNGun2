# DNGun 2

Internal prospect intelligence console. Scores outbound prospects from
manually captured signals, tracks campaign outcomes, and learns which
signals predict revenue. Single-operator, local-only — no auth, no
outreach automation. See [DNGunArchitecture.md](DNGunArchitecture.md)
for the full architecture and roadmap.

## Run locally

Backend (FastAPI + SQLite). The frontend proxy expects port **8001**:

```powershell
python -m uvicorn backend.app.main:app --reload --port 8001
```

Frontend (Next.js on http://127.0.0.1:3000):

```powershell
cd frontend
npm install
npm run dev
```

The SQLite database is created at `data/dngun.sqlite3` (override with
the `DNGUN_DB_PATH` environment variable).

## Tests

```powershell
python -m pytest backend/tests
```

## Seed sample data

```powershell
python backend\scripts\seed_mvp0.py
```

## Maintenance

Recalculate stored decision-maker authority scores after changing
`backend/app/rules/authority_rules.yaml` or the matching logic
(scores are persisted at write time, so existing records go stale):

```powershell
python backend\scripts\recalculate_authority.py
```

Updates only records whose score or rationale changed and reports the
count. Never runs automatically.

## Development notes

- Do **not** run `next build` while `next dev` is active in the same
  workspace — both write to `frontend/.next` and the dev server will
  start returning 500s. Restart `npm run dev` if this happens.
- The API has no authentication. Keep the backend bound to
  `127.0.0.1`; do not expose it on a network interface.
