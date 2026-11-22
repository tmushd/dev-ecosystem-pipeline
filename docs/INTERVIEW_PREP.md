# Interview preparation

## Concise project explanation

“I built an open-source ecosystem intelligence platform. Airflow collects daily public signals, S3 keeps replayable raw partitions, Snowflake performs transaction-scoped idempotent merges, and dbt publishes a tested repository-day fact and decision mart. I then used statistical analysis and an interactive dashboard to determine which projects warrant deeper evaluation.”

## High-value questions

### Why use repository/date as the grain?

It makes each daily state explicit, supports deterministic replay keys, prevents accidental event/snapshot mixing, and enables later star/fork growth calculations.

### How is the load idempotent?

The target key is a SHA-256 of source/table, source record ID, and snapshot date. Snowflake `MERGE` updates an existing key and inserts a new one. All source merges and audit writes share one transaction. Locally, the same batch is applied three times as a release gate.

### Why `dbt source freshness` followed by `dbt build`?

Freshness blocks stale inputs first. `dbt build` then runs models and tests in dependency order, avoiding tests against marts that do not yet exist on a fresh warehouse.

### How do you handle missing data?

Missing is distinct from zero. Required stars and forks fail local validation and dbt not-null tests. Public issue counts that cannot be collected remain null with a reason/status, so issue-burden metrics can exclude unavailable observations.

### What did the analysis find?

In the selected 50-repository snapshot, recent activity was 84.6% for top-quartile starred projects versus 40.5% for the remainder, a 44.1-point difference with Fisher p=0.0092. The direction remained positive across four activity windows.

### What can you not conclude?

The sample is popularity-sorted and observational. The result is not representative of all open source and does not show that stars cause maintenance. Repository age, organization capacity, and search selection can confound it.

### Why block the second hypothesis?

Star growth must precede a separate fork-growth window. With one snapshot there is no longitudinal order, so the pipeline marks the analysis insufficient until at least 14 daily snapshots exist.

### Is the Snowflake path proven live?

The merge and security logic are implemented, statically validated, and unit-tested. The committed three-replay proof is local, not a live Snowflake replay. I state that boundary explicitly rather than overstating deployment proof.

### Is this a Tableau project?

It currently includes an interactive Plotly dashboard and a Tableau-ready CSV. A native Tableau workbook is not claimed as completed.

## Strong closing point

“The project demonstrates that I can move from messy public data to governed analytical products, quantify uncertainty, communicate limitations, and convert a finding into a stakeholder action.”
