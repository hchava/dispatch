---
pipeline: "*"
tags: [data-quality, anomaly, z-score, IQR, feature-drift]
severity: P1
---
# Data Quality Alert Runbook

## Symptoms
- Z-score or IQR anomaly detector fired on a metric
- Null rate spiked above baseline
- Distribution shift detected on a key feature or dimension

## Triage steps

1. Identify which column(s) triggered the alert and the detection method (Z-score vs IQR)
2. Compare today's distribution against the 7-day and 30-day baselines
3. Check if the shift is isolated to one partition (date, region, product) or global
4. Trace the column back to its upstream source using the lineage graph
5. Check if any schema change, backfill, or upstream pipeline restatement coincided with the shift

## Detection notes

**Z-score fires on spikes** — sudden single-day anomalies. High sensitivity; can false-positive on legitimate seasonal events.
**IQR fires on gradual drift** — sustained distribution shift over multiple days. Lower false-positive rate for slow-moving features.

Use both detectors in combination: Z-score catches the acute cases, IQR catches slow degradation that would otherwise go undetected for weeks.

## Common root causes

**Upstream restatement** — source system corrected historical data; the pipeline ingested the correction as new rows.
**Experiment exposure change** — A/B experiment changed the population, shifting the feature distribution legitimately.
**Missing data** — ingestion gap caused nulls to propagate; null rate spike is an artifact of missing rows, not schema change.

## Escalation criteria
Escalate if the affected column is used in an active ML model, a certified metric, or an executive KPI dashboard.
