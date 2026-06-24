---
pipeline: "*"
tags: [null-rate, data-quality, validation, schema, completeness]
severity: P1
pattern_type: validation_example
---
# Validation: Null Rate Check

## What it tests
The fraction of NULL values in a column stays within the contract-specified threshold.
Catches: upstream schema changes that flip nullable, missing join keys, ingestion gaps.

## Implementation

```python
from dataclasses import dataclass

@dataclass
class NullRateResult:
    column: str
    null_rate: float
    threshold: float
    passed: bool
    severity: str
    message: str

def null_rate_check(
    column: str,
    null_count: int,
    total_count: int,
    threshold: float = 0.001,     # 0.1% default; use 0.0 for NOT NULL columns
    severity_on_breach: str = "P1",
) -> NullRateResult:
    if total_count == 0:
        return NullRateResult(column, 0.0, threshold, False, "P1", "Table is empty")

    null_rate = null_count / total_count

    if null_rate > threshold:
        return NullRateResult(
            column=column, null_rate=null_rate, threshold=threshold, passed=False,
            severity=severity_on_breach,
            message=(
                f"{column}: null rate {null_rate:.2%} exceeds threshold {threshold:.2%} "
                f"({null_count:,} nulls in {total_count:,} rows)"
            )
        )
    return NullRateResult(
        column=column, null_rate=null_rate, threshold=threshold, passed=True,
        severity="OK", message=f"{column}: null rate {null_rate:.2%} within threshold"
    )
```

## Batch check across all contract columns

```python
def validate_nulls_against_contract(df, contract: dict) -> list[NullRateResult]:
    results = []
    total = df.count()
    for col_spec in contract.get("schema", []):
        col = col_spec["name"]
        nullable = col_spec.get("nullable", True)
        threshold = 0.0 if not nullable else 0.001
        null_count = df.filter(df[col].isNull()).count()
        results.append(null_rate_check(col, null_count, total, threshold))
    return results
```

## Expected test cases

| Column | nullable | null_count | total | Expected |
|---|---|---|---|---|
| order_id | false | 0 | 1,000,000 | PASS |
| order_id | false | 5 | 1,000,000 | FAIL P1 |
| user_id | true | 1,500 | 1,000,000 | PASS (0.15% < 0.1% threshold) — FAIL actually |
| properties | true | 200,000 | 1,000,000 | PASS (20% allowed for JSON blob) |

## Column-specific thresholds
Set threshold in the data contract per column:

```yaml
schema:
  - name: order_id
    nullable: false       # threshold = 0.0%
  - name: user_id
    nullable: true
    null_threshold: 0.05  # 5% allowed (anonymous sessions)
  - name: properties
    nullable: true
    null_threshold: 0.30  # 30% allowed (optional event metadata)
```
