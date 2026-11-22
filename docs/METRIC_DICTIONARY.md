# Metric dictionary

| Metric | Definition | Decision use | Limitation |
| --- | --- | --- | --- |
| `days_since_last_push` | Snapshot date minus latest default-branch commit date | Maintenance recency | Commits can occur outside the default branch |
| `is_recently_maintained_30d` | `days_since_last_push <= 30` | Active/inactive comparison | Thirty days is a declared policy threshold, not a universal standard |
| `star_growth` | Current stars minus prior daily snapshot stars | Interest momentum | Requires at least two snapshots |
| `fork_growth` | Current forks minus prior daily snapshot forks | Adoption/development proxy | Forks do not always represent active usage |
| `fork_to_star_ratio` | Forks divided by stars | Relative participation | Undefined for zero stars |
| `issue_to_star_ratio` | Open issues divided by stars | Support burden proxy | Issue workflows vary greatly by project |
| `evaluation_score` | 40% activity recency, 35% star percentile, 25% fork percentile | Transparent triage ordering | Not a quality probability; weights are policy choices |
| `maintenance_risk` | `ACTIVE` ≤90 days, `WATCH` 91–180, `HIGH` >180 | Manual-review routing | Mature stable projects may commit infrequently |
| `growth_evidence_status` | `READY` only with at least 14 snapshots | Prevent premature trend claims | Snapshot count alone does not guarantee causal identification |
