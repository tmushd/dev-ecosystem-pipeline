# Tableau dashboard

The portfolio BI deliverable is the packaged workbook
[`Open_Source_Ecosystem_Intelligence.twbx`](../outputs/dashboard/Open_Source_Ecosystem_Intelligence.twbx).
It embeds the governed 50-row repository momentum extract, so a reviewer can open it without
configuring Snowflake, AWS, or local file paths.

## Dashboard contents

| View | Question answered | Encodings |
| --- | --- | --- |
| Repository Landscape | Are popular projects also recently maintained? | Stars × days since push; fork count by size; maintenance risk by color |
| Evaluation Ranking | Which repositories merit technical review first? | Evaluation score by repository; maintenance risk by color |
| Maintenance Risk | How is the evaluated portfolio distributed across risk tiers? | Repository count by risk category |
| Executive Overview | What should a technology evaluator investigate next? | All three views in a 1400 × 900 executive layout |

## Refresh and publish

```bash
python3 -m analytics.tableau_dashboard
```

The command rebuilds both the editable `.twb` source and the shareable `.twbx` package from
`outputs/analytics/tableau_repo_momentum_extract.csv`. Open the package in Tableau Desktop or
Tableau Public, review the views, and publish it to a Tableau Public profile if a public hosted
portfolio URL is desired.

The automated release gate validates the XML, embedded-data path, workbook views, dashboard name,
and ZIP integrity. Visual rendering still belongs in Tableau because Tableau's rendering engine is
not bundled with this repository.
