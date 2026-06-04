# DNGun Architecture

## Purpose

Translate the Obsidian knowledge system into software architecture.

DNGun should be coded as a prospect intelligence engine first, not as a full outreach SaaS.

The goal is to turn DNGun's rules, models, Alpha Signals, campaign outcomes, evidence, confidence, and profitability learning into an internal execution system.

---

# Core Principle

> DNGun must not start as outreach software.

It should start as:

```text
Prospect Discovery Intelligence
+
Scoring Engine
+
Campaign Learning System
+
Evidence Governance System
```

Do not build random UI screens.

Do not build a CRM first.

Do not build email automation first.

Build the smallest internal tool that tests whether the prospect intelligence system works.

The most important architectural rule:

> If it cannot learn from campaign outcomes, it is not DNGun.

---

# Knowledge-to-Software Map

```text
Obsidian Knowledge Map
        ->
Rules / Models
        ->
DNGun App
        ->
Prospect Scoring
        ->
Campaign Results
        ->
Evidence + Confidence Updates
```

## Expanded System Architecture

```text
Obsidian Knowledge System
        ->
DNGun Rule Registry
        ->
Prospect Intelligence Engine
        ->
Scoring + Alpha Signal Detection
        ->
Campaign Batch Testing
        ->
Evidence Ledger
        ->
Confidence Updates
        ->
Signal Weight Updates
        ->
Profitability Learning
```

---

# Obsidian vs App Boundary

Obsidian stays the brain.

The DNGun app becomes the execution system.

| Layer | Role | Examples |
|---|---|---|
| Obsidian | Why | Strategy memory, model definitions, decision logs, research notes. |
| DNGun App | What happened | Prospect database, scoring engine, campaign tracker, evidence calculator. |

## Obsidian Files Feeding the App

| Obsidian File | Software Role |
|---|---|
| [[SignalFramework|Signal Framework]] | Signal taxonomy and tier logic. |
| [[ProspectDiscoveryEngine|Prospect Discovery Engine]] | Scoring formula and prospect decisions. |
| [[AlphaSignals|Alpha Signals]] | Alpha Signal definitions and bonuses. |
| [[CampaignIntelligence|Campaign Intelligence]] | Outcome metrics and learning loops. |
| [[ConfidenceEngine|Confidence Engine]] | Confidence update rules. |
| [[ProfitabilityLedger|Profitability Ledger]] | Business-model viability and delivery economics. |
| [[ExecutionProtocol|Execution Protocol]] | Allocation and governance rules. |
| [[ProspectDiscoveryModels/PDM-AIAutomation|PDM - AI Automation]] | Segment-specific theory file. |
| [[ProspectDiscoveryModels/PDM-RevOps|PDM - RevOps]] | Segment-specific theory file. |
| [[ProspectDiscoveryModels/PDM-SEO|PDM - SEO]] | Segment-specific theory file. |
| [[ProspectDiscoveryModels/PDM-Webflow|PDM - Webflow]] | Segment-specific theory file. |

---

# Rule Engine Layer

The Rule Layer must be a first-class backend module, not hardcoded logic scattered through the scoring code.

```text
backend/
  rules/
    signals.yaml
    alpha_signals.yaml
    disqualifiers.yaml
    score_bands.yaml
```

The scoring engine should consume rules through a registry:

```py
score = ScoringEngine(
    rules=RuleRegistry()
).calculate(prospect)
```

This gives DNGun:

- no hardcoded scoring logic,
- business logic editable without code changes,
- future AI-assisted rule suggestions,
- segment-specific rule evolution.

The moat is not the code.

The moat is the evolving rule set.

Rule files should define:

- signal names,
- signal tiers,
- scoring multipliers,
- Alpha Signal requirements,
- Alpha Signal bonuses,
- disqualification rules,
- score bands,
- segment-specific overrides.

---

# MVP 0 - Manual-First Internal Tool

MVP 0 is an internal prospect intelligence console.

It should do only this:

1. Add prospect.
2. Add public signals manually.
3. Calculate prospect score.
4. Assign or detect Alpha Signal.
5. Select campaign batch.
6. Track outreach result.
7. Add evidence entry.
8. Update confidence.
9. Show campaign intelligence.
10. Export learning report.

## First Milestone

```text
Input: 25 agencies
        ->
Add signals manually
        ->
Calculate scores
        ->
Rank prospects
        ->
Create first campaign batch
        ->
Track replies
        ->
Update confidence
        ->
Export report
```

This is enough to test whether the system learns.

---

# Recommended Technical Architecture

Use a simple internal app first.

```text
frontend/
  Next.js + Tailwind
  Prospect dashboard
  Campaign dashboard
  Evidence ledger
  PDM editor

backend/
  FastAPI
  rule registry
  scoring engine
  alpha signal engine
  campaign engine
  evidence engine
  confidence engine
  profitability engine

backend/rules/
  signals.yaml
  alpha_signals.yaml
  disqualifiers.yaml
  score_bands.yaml

database/
  SQLite first
  PostgreSQL later
```

## Stack

| Layer | Technology | Reason |
|---|---|---|
| Frontend | Next.js + Tailwind | Fast internal UI, easy dashboards. |
| Backend | FastAPI | Clean Python rules engine and API layer. |
| Rules | YAML files + RuleRegistry | Editable business logic without code changes. |
| Database | SQLite | Simple local/internal MVP. |
| Future Database | PostgreSQL | Use only after real campaign volume appears. |

---

# Core Data Models

## Prospect

```ts
Prospect {
  id
  companyName
  website
  segment: "AI_AUTOMATION" | "REVOPS" | "SEO" | "WEBFLOW"
  founderName
  founderLinkedIn
  teamSize
  offerValueEstimate
  contactPath
  status
}
```

## Signal

```ts
Signal {
  id
  prospectId
  signalType
  tier: 1 | 2 | 3
  score: 0-5
  sourceUrl
  observedAt
  notes
}
```

## AlphaSignal

```ts
AlphaSignal {
  id
  code: "AS-001"
  name
  requiredSignals[]
  bonusScore
  validationStatus
}
```

## ProspectScore

```ts
ProspectScore {
  prospectId
  tier1Total
  tier2Total
  tier3Total
  baseScore
  alphaMatches[]
  alphaBonus
  finalScore
  decision: "CONTACT_NOW" | "SECONDARY" | "IGNORE" | "DISQUALIFY"
  explanation[]
}
```

## ScoreExplanation

```ts
ScoreExplanation {
  id
  prospectScoreId
  sourceType: "SIGNAL" | "ALPHA_SIGNAL" | "DISQUALIFIER" | "SCORE_BAND"
  sourceCode
  label
  tier
  impact
  notes
}
```

## CampaignBatch

```ts
CampaignBatch {
  id
  name
  segment
  createdAt
  status
  notes
}
```

## CampaignOutcome

```ts
CampaignOutcome {
  id
  campaignBatchId
  prospectId
  contacted
  replied
  callBooked
  proposalRequested
  paidPilot
  lostDeal
  outcomeNotes
  recordedAt
}
```

## EvidenceEntry

```ts
EvidenceEntry {
  id
  project
  evidenceType
  evidence
  impact
  source
  createdAt
}
```

## ConfidenceUpdate

```ts
ConfidenceUpdate {
  id
  confidenceBefore
  evidenceImpact
  confidenceAfter
  reason
  createdAt
}
```

## SignalPerformance

```ts
SignalPerformance {
  id
  signalName
  segment
  timesSeen
  replyRate
  callRate
  proposalRate
  pilotRate
  confidence
  lastUpdatedAt
}
```

## AlphaSignalPerformance

```ts
AlphaSignalPerformance {
  id
  alphaSignalCode
  segment
  timesSeen
  replyRate
  callRate
  proposalRate
  pilotRate
  confidence
  lastUpdatedAt
}
```

---

# Scoring Formula

Formula from [[ProspectDiscoveryEngine|Prospect Discovery Engine]]:

```text
Base Score = (Tier 1 Total * 3) + (Tier 2 Total * 2) + (Tier 3 Total * 1)
Final Score = Base Score + Alpha Bonus
```

Alpha Signals should remain separate from base scoring:

```text
Base Score: 64

Alpha Matches:
- AS-001
- AS-004

Final Score: 84
```

This allows DNGun to measure base score predictive power separately from Alpha Signal predictive power.

## Score Provenance

Every score must be explainable.

Example score output:

```json
{
  "prospect_id": "P-102",
  "base_score": 67,
  "alpha_matches": ["AS-003"],
  "final_score": 87,
  "explanation": [
    {
      "signal": "Founder discussing growth",
      "tier": 1,
      "impact": 15
    },
    {
      "signal": "Hiring SDR",
      "tier": 1,
      "impact": 12
    },
    {
      "alpha_signal": "AS-003",
      "impact": 20
    }
  ]
}
```

Without provenance, `Score = 87` is not useful.

With provenance, the system can answer: why is it 87?

## Decision Bands

| Score | Decision |
|---:|---|
| 80+ | Contact Immediately |
| 60-79 | Secondary Queue |
| <60 | Ignore |
| Deal-killer present | Disqualify regardless of score |

---

# MVP Screens

Build only these five screens first.

## 1. Prospect Inbox

Purpose:

- Add prospects.
- View raw prospects.
- Assign segment.
- See status.

Do not turn this into a CRM.

## 2. Prospect Scoring View

Purpose:

- Add tiered signals.
- Attach source URLs.
- Apply Alpha Signals.
- Show base score, Alpha Signal matches, final score, decision, and explanation.

## 3. Campaign Batch View

Purpose:

- Select prospects for a campaign.
- Track whether they were contacted.
- Track outcomes.

## 4. Evidence Ledger View

Purpose:

- Convert campaign outcomes into evidence entries.
- Feed the Confidence Engine.
- Feed signal and Alpha Signal performance analytics.

## 5. Campaign Intelligence Dashboard

Purpose:

- Show reply rate.
- Show call rate.
- Show proposal rate.
- Show pilot rate.
- Compare outcomes by score band.
- Compare Alpha Signal performance.
- Compare signal performance.

---

# Backend Modules

## `/rules`

```py
RuleRegistry()
```

Responsibilities:

- Load signal, Alpha Signal, disqualifier, and score-band rules.
- Validate rule definitions.
- Provide rules to scoring and Alpha Signal engines.
- Keep business logic editable outside application code.

## `/scoring`

```py
calculateProspectScore()
```

Responsibilities:

- Sum tiered signals.
- Apply tier multipliers.
- Return base score separately from Alpha Signal matches.
- Add Alpha Signal bonus only when calculating final score.
- Apply disqualification override.
- Return score decision and provenance explanation.

## `/alpha-signals`

```py
detectAlphaSignals()
```

Responsibilities:

- Match prospects against Alpha Signal definitions.
- Allow manual override in MVP 0.
- Track validation status.
- Keep Alpha Signal contribution separate from base score.

## `/campaigns`

```py
createCampaignBatch()
trackOutcome()
```

Responsibilities:

- Create campaign batches.
- Attach prospects.
- Record contacted/replied/call/proposal/pilot outcomes.

## `/evidence`

```py
addEvidenceEntry()
```

Responsibilities:

- Convert outcomes into evidence entries.
- Keep evidence auditable.
- Feed signal and Alpha Signal performance analytics.

## `/confidence`

```py
updateConfidence()
```

Responsibilities:

- Apply [[ConfidenceEngine|Confidence Engine]] impact rules.
- Record before/after confidence.
- Prevent internal-only work from changing confidence.
- Use evidence to recommend signal weight changes.

## `/profitability`

```py
calculateHourlyRate()
```

Responsibilities:

- Track hours.
- Track revenue.
- Track delivery economics.
- Support [[ProfitabilityLedger|Profitability Ledger]] review.

---

# Database Tables

```text
prospects
signals
alpha_signals
prospect_alpha_signals
scores
score_explanations
campaign_batches
campaign_batch_prospects
campaign_outcomes
evidence_entries
confidence_updates
profitability_entries
signal_performance
alpha_signal_performance
```

---

# Campaign Intelligence Metrics

The dashboard should report:

| Metric | Purpose |
|---|---|
| Reply Rate | Did prospects respond? |
| Call Rate | Did replies become calls? |
| Proposal Rate | Did calls become buying intent? |
| Pilot Rate | Did the campaign create revenue? |
| Score Band Performance | Did high scores outperform lower scores? |
| Base Score Performance | Did raw scoring predict outcomes? |
| Alpha Signal Performance | Which Alpha Signals predict outcomes? |
| Signal Performance | Which individual signals predict outcomes? |
| Expected vs Actual | Did campaign results match hypothesis? |
| Signal Weight Adjustment | Which signals should change? |

The key learning loop is:

```text
Campaign Outcomes
        ->
Evidence Ledger
        ->
Confidence Updates
        ->
Signal Weight Updates
```

The Prospect module is data collection.

The Evidence Ledger is where DNGun becomes smarter over time.

## Signal Performance

Track performance for every signal:

| Field | Purpose |
|---|---|
| signal_name | Which signal was observed? |
| times_seen | How often has it appeared? |
| reply_rate | Did it predict replies? |
| call_rate | Did it predict calls? |
| proposal_rate | Did it predict proposals? |
| pilot_rate | Did it predict revenue? |
| confidence | How much trust should the system place in this signal? |

Example:

| Signal | Reply Rate |
|---|---:|
| Hiring SDR | 31% |
| Founder Posting Weekly | 11% |
| Recent Funding | 48% |

## Alpha Signal Validation

Track Alpha Signal performance separately:

| Field | Purpose |
|---|---|
| alpha_signal_code | Which Alpha Signal matched? |
| segment | Where did it match? |
| times_seen | How often has it appeared? |
| reply_rate | Did it predict replies? |
| call_rate | Did it predict calls? |
| proposal_rate | Did it predict proposals? |
| pilot_rate | Did it predict revenue? |
| confidence | How much trust should the system place in this Alpha Signal? |

This should eventually show patterns like:

- `AS-001` works.
- `AS-002` does not work.
- `AS-003` works only for SEO agencies.

---

# What Not To Build First

Avoid:

- email sending,
- LinkedIn automation,
- CRM replacement,
- full SaaS auth,
- billing,
- payment flows,
- AI agent automation,
- scrapers,
- complex dashboards,
- multi-user permissions,
- integrations before evidence.

These are execution-stack features.

The moat is prospect intelligence, not sending messages.

---

# First Implementation Prompt

Use this prompt for Claude Code, Codex, or another coding agent:

```text
Build DNGun MVP as an internal prospect intelligence tool.

Stack:
Next.js frontend
FastAPI backend
SQLite database

Core features:
1. Create prospect
2. Add tiered signals
3. Calculate prospect score:
   base_score = (Tier1 total * 3) + (Tier2 total * 2) + Tier3 total
4. Detect Alpha Signal matches manually for now
5. Calculate final_score = base_score + Alpha Signal bonus
6. Return score provenance explaining every score contribution
7. Rank prospects:
   80+ Contact Immediately
   60-79 Secondary Queue
   <60 Ignore
   Deal-killer present = Disqualify
8. Create campaign batch
9. Track outcome:
   contacted, replied, call booked, proposal requested, paid pilot
10. Add evidence entries
11. Update confidence score using ConfidenceEngine rules
12. Show Campaign Intelligence dashboard:
   reply rate, call rate, proposal rate, pilot rate by score band
13. Track signal performance and Alpha Signal performance

Do not build email automation.
Do not build CRM.
Do not build payment.
Do not build scraping.
```

---

# Implementation Roadmap

Build in this order:

## Phase 1

- Prospect
- Signal
- Score
- Score provenance

## Phase 2

- Alpha Signals
- Campaign batches
- Separate base score from Alpha Signal contribution

## Phase 3

- Campaign outcomes
- Evidence Ledger

## Phase 4

- Confidence Engine
- Evidence-to-confidence updates

## Phase 5

- Campaign Intelligence Dashboard
- Score band performance
- Alpha Signal performance

## Phase 6

- Profitability Ledger
- Delivery economics

## Phase 7

- Rule Registry
- Signal performance analytics
- Alpha Signal validation analytics

At this point DNGun becomes a Prospect Intelligence Operating System, not another outreach tool.

## Future Architecture

```text
MVP 0
Manual Signals
Manual Alpha Signals
Manual Outreach
Manual Evidence

MVP 1
Semi-Automatic Discovery

MVP 2
Automated Discovery

MVP 3
Automated Outreach
```

Many founders try to start at MVP 3.

DNGun starts at MVP 0 because the intelligence layer must be proven before the execution layer is automated.

---

# Architecture Decision

DNGun's first coded version should be:

```text
DNGun MVP 0
Internal Prospect Intelligence Console
```

Not SaaS.

Not CRM.

Not scraper.

Not email automation.

## Strategic Reason

DNGun learns which buyers are real before automation is added.

That is the potential moat.

Every campaign should improve:

- signal weights,
- Alpha Signal bonuses,
- disqualification rules,
- outreach angles,
- expected conversion rates,
- confidence score,
- profitability assumptions.

---

# Success Criteria for MVP 0

MVP 0 succeeds if it can:

1. Input 25 prospects.
2. Score each prospect.
3. Explain each score with provenance.
4. Keep base score separate from Alpha Signal contribution.
5. Rank prospects correctly.
6. Create one campaign batch.
7. Track campaign outcomes.
8. Produce Campaign Intelligence metrics.
9. Add evidence entries.
10. Update confidence.
11. Export a learning report.
12. Identify at least one signal, Alpha Signal, or disqualification rule that should change.

If it cannot learn from campaign outcomes, it is not DNGun.
