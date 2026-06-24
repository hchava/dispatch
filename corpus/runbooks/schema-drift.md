---
pipeline: "*"
tags: [schema-drift, contract-violation, nullable, column-added, column-dropped]
severity: P1
---
# Schema Drift Runbook

## Symptoms
- Ingestion job fails with column not found or type mismatch error
- Row count drops to near zero after an upstream change
- Partition pruning eliminates all rows (nullable column added without default)

## Triage steps

1. Run schema diff: compare current upstream schema against the data contract on file
2. Identify the changed columns (added / dropped / renamed / type changed / nullable flipped)
3. Determine if the change is intentional (coordinated with the upstream owner) or accidental
4. If intentional: update the data contract, adjust ingestion logic, trigger backfill
5. If accidental: alert upstream owner; hold ingestion until schema is restored or contract is updated

## Prevention

- Require upstream owners to update the data contract before deploying schema changes
- Add schema validation at ingestion boundary — fail fast rather than propagating corrupt data silently
- Use column-level lineage to identify all downstream consumers before a schema change is approved

## Escalation criteria
Escalate immediately if a dropped or renamed column is referenced in a certified metric or an active ML feature.
