# DNGun 2

Internal prospect intelligence console. Scores outbound prospects from
manually captured signals, tracks campaign outcomes, and learns which
signals predict revenue. Single-operator, local-only — no auth, no
outreach automation. See [DNGunArchitecture.md](DNGunArchitecture.md)
for the full architecture and roadmap.

## Run locally

Backend (FastAPI + SQLite). The frontend proxy expects port **8001**:

```sh
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8001
```

Frontend (Next.js on http://127.0.0.1:3000):

```sh
cd frontend
npm install
npm run dev
```

The SQLite database is created at `data/dngun.sqlite3` (override with
the `DNGUN_DB_PATH` environment variable).

## Tests

```sh
python -m pytest backend/tests
```

## Seed sample data

```sh
python backend/scripts/seed_mvp0.py
```

## Find buyers for a domain (treg)

Ranks companies that buy Google Ads on, or rank organically for, a domain's
keywords. It pulls live data through [treg](https://treg.to) and needs
`TREG_TOKEN` in the environment or the repo-root `.env`. Each searched keyword
costs about $0.02–0.04. `--dry-run` prints the cost estimate.

```sh
python backend/scripts/find_domain_buyers.py aiautomation.com                       # keyword derived: "ai automation"
python backend/scripts/find_domain_buyers.py aiautomation.com -k "ai automation, ai agents" --expand 3
python backend/scripts/find_domain_buyers.py aiautomation.com --no-big-advertisers  # drop >= $100k/mo spenders
python backend/scripts/find_domain_buyers.py aiautomation.com --save 10 --segment AI_AUTOMATION
```

- `-k/--keyword` can be repeated and accepts comma-separated phrases. Without
  it, the domain is split into words using Google's own keyword data.
- `--expand N` also searches the N related keywords with the highest
  volume × CPC.
- `--big-advertisers` / `--no-big-advertisers` keeps or drops advertisers
  spending at least `--big-budget` dollars a month (default 100,000). By
  default they are kept.
- `--save N` creates the top N candidates as prospects. It reuses prospects
  that already exist. It attaches the ad, ranking, and brand evidence as
  pending signal suggestions. Review them with `suggest_signals.py` (below).
  Without `--save`, nothing is written.

## Suggest signals for a prospect (treg)

Looks up a prospect's company size, sales hiring, recent launches, website
authority, founder email, and founder LinkedIn posts. It stores what it finds
as **pending** suggestions. A suggestion becomes a scored signal only after you
approve it. Rejected suggestions are not proposed again. A lookup costs up to
about $0.12 per prospect, usually around $0.05.

In the console, the **Suggested Signals** panel under Prospect Intelligence does
the same thing. **Find via treg** runs the lookups, and each row has
**Approve** and **Reject** buttons. The backend reads `TREG_TOKEN` from the
repo-root `.env`. API endpoints: `GET /prospects/{id}/signal-suggestions`,
`POST /prospects/{id}/signal-suggestions/run`,
`POST /signal-suggestions/{id}/approve` and `POST /signal-suggestions/{id}/reject`.

```sh
python backend/scripts/suggest_signals.py <prospect_id> [--dry-run]
python backend/scripts/suggest_signals.py --list [<prospect_id>]
python backend/scripts/suggest_signals.py --approve <SS-id> ... | --reject <SS-id> ...
```

## Maintenance

Recalculate stored decision-maker authority scores after changing
`backend/app/rules/authority_rules.yaml` or the matching logic
(scores are persisted at write time, so existing records go stale):

```sh
python backend/scripts/recalculate_authority.py
```

Updates only records whose score or rationale changed and reports the
count. Never runs automatically.

## Development notes

- Do **not** run `next build` while `next dev` is active in the same
  workspace — both write to `frontend/.next` and the dev server will
  start returning 500s. Restart `npm run dev` if this happens.
- The API has no authentication. Keep the backend bound to
  `127.0.0.1`; do not expose it on a network interface.
