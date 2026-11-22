# Analytical findings and recommendations

## Decision question

Which open-source data engineering repositories appear sufficiently important and actively maintained to justify deeper technical evaluation?

## Dataset

The evidence snapshot contains 50 public repositories returned by GitHub search for `topic:data-engineering language:Python`, ordered by stars, on November 21, 2026. The unit is a repository on a snapshot date. This is a purposive ecosystem sample, not a random sample of all open-source software.

## Hypothesis A: popularity and maintenance recency

- Null: the proportion of repositories pushed within 30 days is the same for top-quartile starred and lower-star groups.
- Alternative: the top-quartile group has a greater recent-maintenance proportion.
- High-star cutoff: 7,051 stars.
- Top quartile: 11 of 13 recently maintained, 84.6%; Wilson 95% CI 57.8%–95.7%.
- Lower three quartiles: 15 of 37 recently maintained, 40.5%; Wilson 95% CI 26.3%–56.5%.
- Absolute difference: +44.1 percentage points.
- Fisher exact odds ratio: 8.07; two-sided p=0.0092.

### Interpretation

Within this selected ecosystem snapshot, highly starred repositories were much more likely to show a commit in the prior 30 days. The effect is large enough to matter for triage: popularity and maintenance recency should be considered together rather than treating stars as a standalone quality measure.

The result is not causal. Organization capacity, repository age, product maturity, mirrored activity, release practices, and GitHub search ranking can affect both stars and activity. A commit is also an imperfect proxy for healthy maintenance.

### Activity-window sensitivity

| Definition of recent maintenance | High-star rate | Other rate | Absolute difference | Fisher p-value |
| ---: | ---: | ---: | ---: | ---: |
| 14 days | 84.6% | 37.8% | +46.8 points | 0.0083 |
| 30 days | 84.6% | 40.5% | +44.1 points | 0.0092 |
| 60 days | 92.3% | 45.9% | +46.4 points | 0.0037 |
| 90 days | 92.3% | 54.1% | +38.3 points | 0.0180 |

The direction remains stable across all four definitions. This reduces dependence on the specific 30-day policy threshold, but it does not remove sampling or confounding concerns.

### Repository-age context

| Age quartile | n | Median age | Recent-maintenance rate |
| --- | ---: | ---: | ---: |
| Youngest | 12 | 920 days | 58.3% |
| Mid-young | 13 | 1,736 days | 46.2% |
| Mid-mature | 12 | 2,352 days | 33.3% |
| Oldest | 13 | 3,183 days | 69.2% |

Activity does not decline monotonically with repository age in this sample; the oldest quartile is highly active. That pattern reinforces why age should be treated as context rather than assuming older repositories are less maintained.

## Missing-data note

Open-issue counts were observable for 25 of 50 repositories. The other 25 are stored as null with an explicit collection status rather than being converted to zero. Issue-burden comparisons should therefore be restricted to observed rows and treated as secondary in this snapshot.

## Hypothesis B: star growth and subsequent fork growth

Status: **INSUFFICIENT_HISTORY**. Only one daily snapshot is available, while the predeclared minimum is 14. The analysis requires a star-growth window that precedes a separate fork-growth window. Running it now would reuse the same period or invent history, so the pipeline blocks the test and publishes its readiness state.

## Recommendations

1. Start technical evaluation with repositories in the high evaluation-score tier that are also `ACTIVE`; this avoids equating accumulated popularity with current health.
2. Route `WATCH` and `HIGH` maintenance-risk repositories to manual review before adoption, especially where operational dependency would be high.
3. Continue daily snapshots for at least 14 days before assessing momentum. Do not present single-snapshot popularity as growth.
4. Re-run the finding across broader query definitions and stratify by repository age or organization type before generalizing beyond this selected ecosystem.

## Reproduction

Run `python3 scripts/build_portfolio_evidence.py --snapshot-date 2026-11-21 --pages 5`. The exact normalized records, DQ output, hypothesis JSON, momentum mart, and run manifest are committed under `data/` and `outputs/`.
