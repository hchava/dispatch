---
pipeline: "*"
tags: [row-count, data-quality, validation, anomaly-detection]
severity: P1
pattern_type: validation_example
---
# Validation: Row Count Check

## What it tests
The daily refresh produced a row count that is within expected bounds relative
to the 7-day rolling average. Catches: ingestion failures, upstream truncation,
bad partition pruning, silent schema drift that filters rows.

## Implementation

```python
from dataclasses import dataclass
import statistics

@dataclass
class RowCountCheckResult:
    passed: bool
    today: int
    baseline_avg: float
    pct_change: float
    severity: str
    message: str

def row_count_check(
    today_count: int,
    historical_counts: list[int],     # last 7 days
    drop_threshold: float = 0.20,     # 20% drop → P1
    spike_threshold: float = 3.00,    # 3x spike → P1 (possible duplicate ingestion)
) -> RowCountCheckResult:
    if not historical_counts:
        return RowCountCheckResult(True, today_count, 0, 0, "P2", "No baseline — skipping check")

    avg = statistics.mean(historical_counts)
    pct_change = (today_count - avg) / avg if avg > 0 else 0

    if pct_change < -drop_threshold:
        return RowCountCheckResult(
            passed=False, today=today_count, baseline_avg=avg,
            pct_change=pct_change, severity="P1",
            message=f"Row count dropped {abs(pct_change):.0%} vs 7d avg ({avg:,.0f} → {today_count:,})"
        )
    if pct_change > spike_threshold:
        return RowCountCheckResult(
            passed=False, today=today_count, baseline_avg=avg,
            pct_change=pct_change, severity="P1",
            message=f"Row count spiked {pct_change:.0%} vs 7d avg — possible duplicate ingestion"
        )
    return RowCountCheckResult(
        passed=True, today=today_count, baseline_avg=avg,
        pct_change=pct_change, severity="OK",
        message=f"Row count within bounds ({pct_change:+.1%} vs 7d avg)"
    )
```

## Tuning guidance
- 20% drop threshold works for stable B2C pipelines; use 40% for seasonal pipelines
- Add day-of-week normalization for pipelines with strong weekly patterns (e.g., Monday always 30% higher than Sunday)
- Spike detection (3x) catches duplicate ingestion — a silent failure mode that passes all other checks
- Store check results in a quality_history table for trend analysis

## Expected test cases

| Scenario | today | 7d_avg | Expected |
|---|---|---|---|
| Normal day | 1,000,000 | 980,000 | PASS |
| 94% drop (schema drift) | 60,000 | 1,000,000 | FAIL P1 |
| 25% drop (upstream delay) | 750,000 | 1,000,000 | FAIL P1 |
| 3.5x spike (duplicate ingest) | 3,500,000 | 1,000,000 | FAIL P1 |
| 18% drop (within threshold) | 820,000 | 1,000,000 | PASS |
