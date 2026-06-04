# Phase 1 Domain Mapping

Phase 1 implements only:

- Prospect
- Signal
- Score

It does not yet implement Alpha Signals, campaign batches, evidence, confidence,
profitability, or the Rule Registry.

## Source Theory Files

Phase 1 is informed by these Obsidian files:

- `E:/KnowledgeVault/DNGun/ProspectDiscoveryEngine.md`
- `E:/KnowledgeVault/DNGun/ProspectDiscoveryModels/PDM-AIAutomation.md`
- `E:/KnowledgeVault/DNGun/ProspectDiscoveryModels/PDM-RevOps.md`
- `E:/KnowledgeVault/DNGun/ProspectDiscoveryModels/PDM-SEO.md`
- `E:/KnowledgeVault/DNGun/ProspectDiscoveryModels/PDM-Webflow.md`

## Supported Segments

The backend supports the four active Prospect Discovery Models:

- `AI_AUTOMATION`
- `REVOPS`
- `SEO`
- `WEBFLOW`

These segment values are available on `Prospect`.

## Signal Handling

Signals are manual and free-form in Phase 1.

Each signal stores:

- `signal_type`
- `tier`
- `score`
- `source_url`
- `observed_at`
- `notes`

This matches the Prospect Discovery Engine's manual discovery workflow while
avoiding premature hardcoding of PDM-specific rules.

## Scoring Behavior

Phase 1 implements the base scoring formula:

```text
Base Score = (Tier 1 Total * 3) + (Tier 2 Total * 2) + (Tier 3 Total * 1)
```

Phase 1 always returns:

- `base_score`
- `alpha_matches`
- `alpha_bonus`
- `final_score`
- `decision`
- `explanation`

For now:

```text
alpha_matches = []
alpha_bonus = 0
final_score = base_score
```

This keeps the score shape compatible with Phase 2, where Alpha Signals will be
added without changing the API contract.

## PDM Assumptions Deferred To Later Phases

The PDM files contain priority signals, Alpha Signals, disqualifiers, outreach
angles, expected outcomes, and learning loops.

These should not be hardcoded in Phase 1.

They belong in later phases:

| PDM Concept | Implementation Phase |
|---|---|
| Priority Alpha Signals | Phase 2 |
| Campaign batches | Phase 2 |
| Campaign outcomes | Phase 3 |
| Evidence Ledger | Phase 3 |
| Confidence updates | Phase 4 |
| Campaign Intelligence metrics | Phase 5 |
| Expected outcome comparison | Phase 5 |
| Profitability assumptions | Phase 6 |
| Signal weights | Phase 7 |
| Disqualification rules | Phase 7 |
| Segment-specific rule files | Phase 7 |

## Segment Hypotheses

The current theory ranking from the PDM files is:

1. `AI_AUTOMATION`: strongest early target because of offer validation, founder-led
   growth, and active market discovery.
2. `REVOPS`: strong target because operators understand pipeline economics,
   revenue systems, CAC, and conversion.
3. `SEO`: medium priority when strong proof exists but predictable acquisition is
   weak.
4. `WEBFLOW`: lower urgency unless recent change signals and high-ticket economics
   are visible.

This ranking should guide manual discovery, but it should not change the Phase 1
score formula.

## Guardrail

The PDM files are theory.

Campaign Intelligence is reality.

Do not convert PDM assumptions into permanent scoring rules until campaign outcomes
produce evidence.
