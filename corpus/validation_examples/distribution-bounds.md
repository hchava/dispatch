---
pipeline: "*"
tags: [distribution, z-score, IQR, anomaly-detection, feature-drift, data-quality]
severity: P1
pattern_type: validation_example
---
# Validation: Distribution Bounds Check (Z-score + IQR)

## What it tests
A numeric column's distribution (mean, stddev, percentiles) stays within expected
bounds derived from historical data. Two complementary detectors:
- **Z-score**: catches acute single-day spikes (high sensitivity)
- **IQR**: catches gradual multi-day drift (lower false-positive rate)

## Implementation

```python
from dataclasses import dataclass
import statistics, math

@dataclass
class DistributionCheckResult:
    column: str
    method: str          # "z_score" | "iqr"
    passed: bool
    value: float
    threshold: float
    severity: str
    message: str

def z_score_check(
    column: str,
    today_mean: float,
    historical_means: list[float],
    z_threshold: float = 3.0,
) -> DistributionCheckResult:
    if len(historical_means) < 7:
        return DistributionCheckResult(column, "z_score", True, 0, z_threshold, "OK", "Insufficient history")

    mu = statistics.mean(historical_means)
    sigma = statistics.stdev(historical_means)
    if sigma == 0:
        return DistributionCheckResult(column, "z_score", True, 0, z_threshold, "OK", "Zero variance in history")

    z = abs(today_mean - mu) / sigma
    passed = z <= z_threshold
    return DistributionCheckResult(
        column=column, method="z_score", passed=passed, value=z, threshold=z_threshold,
        severity="OK" if passed else "P1",
        message=f"{column} z-score={z:.2f} ({'within' if passed else 'exceeds'} threshold {z_threshold})"
    )

def iqr_check(
    column: str,
    today_value: float,
    historical_values: list[float],
    multiplier: float = 1.5,
) -> DistributionCheckResult:
    if len(historical_values) < 14:
        return DistributionCheckResult(column, "iqr", True, 0, multiplier, "OK", "Insufficient history")

    sorted_vals = sorted(historical_values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    passed = lower <= today_value <= upper
    return DistributionCheckResult(
        column=column, method="iqr", passed=passed, value=today_value, threshold=multiplier,
        severity="OK" if passed else "P1",
        message=(
            f"{column} IQR bounds=[{lower:.2f}, {upper:.2f}], today={today_value:.2f} "
            f"({'within' if passed else 'OUTSIDE'} bounds)"
        )
    )
```

## When to use each detector

| Scenario | Use |
|---|---|
| Single-day revenue spike after a promo | Z-score |
| Gradual null rate creep over 2 weeks | IQR |
| ML feature used in daily retraining | Both |
| Certified KPI on executive dashboard | Both + alert on first breach |

## Expected test cases

| Column | today | 30d_mean | 30d_std | Expected |
|---|---|---|---|---|
| order_total_usd mean | $52.10 | $51.80 | $0.40 | PASS z=0.75 |
| order_total_usd mean | $38.00 | $51.80 | $0.40 | FAIL z=34.5 |
| late_arrival_rate | 0.31 | 0.008 | 0.002 | FAIL z=151 |
| conversion_rate | 0.048 | 0.051 | 0.003 | PASS z=1.0 |
