---
pipeline: "*"
tags: [exactly-once, idempotency, deduplication, streaming, late-arrival]
severity: P1
pattern_type: code_pattern
---
# Pattern: Exactly-Once Write Semantics

## When to use
Streaming pipeline (Kafka, Kinesis, Pub/Sub) where records may be delivered more
than once (at-least-once). Without deduplication, downstream metrics overcount.

## The pattern: dedup key + upsert

```python
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from delta.tables import DeltaTable

def write_exactly_once(
    batch_df: DataFrame,
    target_table: str,
    dedup_key: str,           # e.g. "event_id"
    event_time_col: str = "event_ts",
    watermark_delay: str = "5 minutes",
) -> None:
    """
    For each dedup_key, keep only the latest record by event_time.
    Merge into target (upsert) — safe to re-run on the same batch.
    """
    # Step 1: Deduplicate within the micro-batch first
    window = (
        F.window_spec()
        .partitionBy(dedup_key)
        .orderBy(F.col(event_time_col).desc())
    )
    deduped = (
        batch_df
        .withWatermark(event_time_col, watermark_delay)
        .withColumn("_rank", F.rank().over(window))
        .filter(F.col("_rank") == 1)
        .drop("_rank")
    )

    # Step 2: Merge into Delta target (upsert)
    target = DeltaTable.forName(SparkSession.getActiveSession(), target_table)
    (
        target.alias("t")
        .merge(deduped.alias("s"), f"t.{dedup_key} = s.{dedup_key}")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
```

## Late-arrival handling
Events that arrive after the watermark window are dropped by default.
For pipelines where late data matters (billing, compliance):

```python
# Store late events in a quarantine table for manual review
late_events = batch_df.filter(
    F.col(event_time_col) < F.current_timestamp() - F.expr(f"INTERVAL {watermark_delay}")
)
if late_events.count() > 0:
    late_events.write.format("delta").mode("append").saveAsTable(f"{target_table}_late_quarantine")
    alert(f"{late_events.count()} late events quarantined from {target_table}")
```

## Key invariants
- Dedup within the micro-batch BEFORE the merge — merge is idempotent, but dedup-after-merge misses intra-batch dupes
- The dedup key must be globally unique, not just within a session or day
- Watermark delay must be tuned to the actual late-arrival distribution — too tight = data loss, too loose = state bloat
- Always emit a `late_arrival_rate` metric — a spike signals the watermark needs adjustment
