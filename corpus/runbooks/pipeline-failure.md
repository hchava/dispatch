---
pipeline: "*"
tags: [pipeline-failure, refresh-failure, row-count-drop]
severity: P1
---
# Pipeline Failure Runbook

## Symptoms
- Daily refresh job did not complete by SLA window
- Row count dropped more than 20% vs 7-day average
- Downstream dashboards show stale or null data

## Immediate triage steps

1. Check job scheduler logs for exit code and last successful run timestamp
2. Verify upstream source availability — confirm source table or API responded
3. Check partition counts for today vs yesterday; large drop indicates incomplete ingestion
4. Look for schema changes in the upstream source using the data contract diff tool
5. If a backfill is safe, trigger a manual re-run scoped to the affected date partition

## Common root causes

**Schema drift** — upstream source added, renamed, or dropped a column without updating the data contract. Partition pruning logic or nullable checks fail silently.
Resolution: update the data contract, add schema validation at ingestion, trigger backfill.

**SLA breach on upstream dependency** — the upstream pipeline feeding this one did not complete in time.
Resolution: check upstream SLA status; if upstream is delayed, hold the dependent job and alert upstream owner.

**Infra failure** — executor node OOM, spot instance preemption, or network timeout.
Resolution: check executor logs; re-run with larger instance or checkpointed restart.

**Duplicate processing** — idempotency key missing; job processed the same partition twice causing dedup to drop legitimate rows.
Resolution: verify idempotency keys; inspect dedup logic; restore from checkpoint.

## Escalation criteria
Escalate to on-call lead if:
- Root cause cannot be determined within 30 minutes
- Backfill would take more than 4 hours
- SLA breach will impact a downstream product or executive dashboard
