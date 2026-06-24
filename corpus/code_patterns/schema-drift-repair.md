---
pipeline: "*"
tags: [schema-drift, schema-evolution, contract, column-added, column-dropped, repair]
severity: P1
pattern_type: code_pattern
---
# Pattern: Schema Drift Detection and Repair

## When to use
Upstream source added, renamed, dropped, or changed the type of a column without
updating the data contract. Ingestion job fails or silently drops rows.

## Detection

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class SchemaDiff:
    added: list[str]
    dropped: list[str]
    type_changed: list[tuple[str, str, str]]   # (col, old_type, new_type)
    nullable_changed: list[tuple[str, bool, bool]]  # (col, was, now)

def detect_schema_drift(
    actual: dict[str, Any],      # {"col": {"type": "STRING", "nullable": False}, ...}
    contract: dict[str, Any],    # same shape, from data contract yaml
) -> SchemaDiff:
    actual_cols = set(actual)
    contract_cols = set(contract)

    added   = list(actual_cols - contract_cols)
    dropped = list(contract_cols - actual_cols)

    type_changed = []
    nullable_changed = []
    for col in actual_cols & contract_cols:
        if actual[col]["type"] != contract[col]["type"]:
            type_changed.append((col, contract[col]["type"], actual[col]["type"]))
        if actual[col].get("nullable") != contract[col].get("nullable"):
            nullable_changed.append((col, contract[col].get("nullable"), actual[col].get("nullable")))

    return SchemaDiff(added, dropped, type_changed, nullable_changed)
```

## Repair decision tree

```
Schema drift detected
        │
        ├── Column ADDED (nullable)
        │       → Safe to ingest: select only contract columns
        │       → Update contract to include new column
        │       → Alert owner: "New column {col} available — add to contract to surface it"
        │
        ├── Column ADDED (not-null, no default)
        │       → BLOCK ingestion — rows will fail null checks
        │       → Alert owner: requires contract update + default value agreement
        │
        ├── Column DROPPED
        │       → BLOCK ingestion if column is non-nullable in contract
        │       → If nullable: ingest with NULL for missing column, alert owner
        │
        ├── Type WIDENED (INT → BIGINT, VARCHAR(50) → VARCHAR(255))
        │       → Usually safe — ingest and update contract
        │
        └── Type NARROWED or INCOMPATIBLE
                → BLOCK ingestion — data loss risk
                → Escalate to upstream owner immediately
```

## Key invariants
- Never silently absorb a schema change — every drift must be logged and the contract updated
- Prefer failing fast at the ingestion boundary over letting bad data reach certified tables
- Column additions are the safest drift; type narrowing is the most dangerous
