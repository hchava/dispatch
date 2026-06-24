---
pipeline: "*"
tags: [backfill, idempotent, partition, recovery]
severity: P1
pattern_type: code_pattern
---
# Pattern: Idempotent Partition Backfill

## When to use
A pipeline processed an incorrect partition (schema drift, upstream delay, logic bug).
You need to re-process one or more date partitions without creating duplicates.

## The pattern

```python
def backfill_partition(pipeline_id: str, date: str, spark: SparkSession) -> None:
    """
    Delete-then-reinsert is the safe backfill pattern.
    NEVER append to an existing partition without deleting first.
    """
    table = f"prod.{pipeline_id}"
    partition_col = "event_date"

    # Step 1: Validate the source is complete before touching the target
    source_count = spark.sql(
        f"SELECT COUNT(*) FROM staging.{pipeline_id} WHERE {partition_col} = '{date}'"
    ).collect()[0][0]

    if source_count == 0:
        raise ValueError(f"Source partition {date} is empty — aborting backfill")

    # Step 2: Delete the target partition atomically
    spark.sql(f"DELETE FROM {table} WHERE {partition_col} = '{date}'")

    # Step 3: Re-insert from source
    spark.sql(f"""
        INSERT INTO {table}
        SELECT * FROM staging.{pipeline_id}
        WHERE {partition_col} = '{date}'
    """)

    # Step 4: Validate row counts match
    target_count = spark.sql(
        f"SELECT COUNT(*) FROM {table} WHERE {partition_col} = '{date}'"
    ).collect()[0][0]

    if target_count != source_count:
        raise RuntimeError(
            f"Backfill row count mismatch: source={source_count}, target={target_count}"
        )
```

## Key invariants
- Always validate source is non-empty before deleting target — a corrupted source + delete = data loss
- Delete and insert in the same transaction when possible (Delta Lake / Iceberg support this)
- Validate counts after insert — silent truncation is the most common backfill failure mode
- Log the backfill in the audit table with start/end row counts and the operator who triggered it

## Common mistakes
- Appending to existing partition → duplicates that survive downstream dedup
- Backfilling without checking downstream consumers — a certified metric may have already read the bad partition
- Not scoping the delete to the exact partition — a missing WHERE clause deletes the entire table
