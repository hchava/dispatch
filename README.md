# Dispatch

**AI agent that triages data-pipeline oncall alerts using RAG over institutional knowledge — runbooks, data contracts, prior incidents, code patterns, and validation examples.**

Engineers rebuilding context from scratch every on-call shift is the most expensive form of toil in a data platform org. Dispatch eliminates it: when an alert fires, the agent retrieves the relevant runbook, prior incident resolutions, the owning pipeline's data contract, the right repair pattern, and the expected validation thresholds — then produces a structured triage report with severity, root cause, step-by-step action, and a confidence-gated escalation decision. All before a human touches the page.

---

## Architecture

```
                         ┌─────────────────────────────────────────────────────┐
   Alert fires           │  DISPATCH AGENT                                     │
   (row count drop,      │                                                     │
    null rate spike,     │  Orchestrator  (Claude — tool use)                  │
    SLA breach, ...)     │                                                     │
         │               │  Round 1: search_context("orders-fact schema drift")│
         ▼               │    ┌──────────────────────────────────────────────┐ │
   ┌───────────┐         │    │  ChromaDB vector store                       │ │
   │  Alert    │──────►  │    │                                              │ │
   │  Parser   │         │    │  ┌────────────┐  ┌──────────────────────┐   │ │
   └───────────┘         │    │  │  Runbooks  │  │   Data Contracts     │   │ │
                         │    │  │ (triage    │  │ (schema · SLA ·      │   │ │
                         │    │  │  steps)    │  │  owner · lineage)    │   │ │
                         │    │  └────────────┘  └──────────────────────┘   │ │
                         │    │  ┌────────────┐  ┌──────────────────────┐   │ │
                         │    │  │  Prior     │  │   Code Patterns      │   │ │
                         │    │  │  Incidents │  │ (backfill · repair · │   │ │
                         │    │  │(resolutions│  │  exactly-once write) │   │ │
                         │    │  └────────────┘  └──────────────────────┘   │ │
                         │    │  ┌────────────────────────────────────────┐  │ │
                         │    │  │  Validation Examples                   │  │ │
                         │    │  │  (row count · null rate · distribution)│  │ │
                         │    │  └────────────────────────────────────────┘  │ │
                         │    │                                              │ │
                         │    │  Metadata filter: pipeline_id + source_type  │ │
                         │    │  → top-k semantic search over filtered subset │ │
                         │    └──────────────────────────────────────────────┘ │
                         │                                                     │
                         │  Round 2 (optional): search_context("backfill      │
                         │    pattern nullable column schema drift")           │
                         │                                                     │
                         │  Reason over retrieved context                      │
                         │    → severity       P0 / P1 / P2                   │
                         │    → root cause     concise description             │
                         │    → action steps   ordered, executable             │
                         │    → confidence     0.0 – 1.0                      │
                         │                                                     │
                         └──────────────────────┬──────────────────────────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          │                                            │
                   confidence ≥ 0.70                          confidence < 0.70
                   (or escalate=false)                        (or escalate=true)
                          │                                            │
                          ▼                                            ▼
                  ┌───────────────┐                       ┌──────────────────────┐
                  │ Triage Report │                       │  Escalation Packet   │
                  │               │                       │                      │
                  │ severity: P1  │                       │ pre-filled context:  │
                  │ root_cause: …│                       │  · alert summary     │
                  │ actions: […] │                       │  · retrieved chunks  │
                  │ confidence:   │                       │  · agent reasoning   │
                  │   0.87        │                       │  · recommended steps │
                  └───────────────┘                       │                      │
                                                          │ → PagerDuty / Slack  │
                                                          └──────────────────────┘
```

---

## Design decisions

**Why RAG over a fine-tuned model?**
Runbooks and data contracts change weekly. Fine-tuning captures a snapshot; retrieval always returns current state. The knowledge base *is* the source of truth — the model just reasons over it.

**Why metadata filtering before semantic search?**
A bare "pipeline failure" query returns noise across all pipelines. Filtering by `pipeline_id` and `source_type` first narrows the candidate set so every top-k result is scoped to the specific alert context. Precision before recall.

**Why five corpus types?**
Each type answers a different question the agent needs to resolve:

| Corpus type | Question answered |
|---|---|
| Runbook | What are the triage steps for this class of failure? |
| Data contract | Who owns this pipeline? What's the schema, SLA, lineage? |
| Prior incident | Has this exact failure happened before? How was it resolved? |
| Code pattern | What's the correct implementation for the fix (backfill, schema repair, dedup)? |
| Validation example | What are the expected thresholds? What counts as passing? |

A single "knowledge base" query conflates all five. Typed retrieval lets the agent pick the right lens per round.

**Why a confidence threshold for HITL escalation?**
Agents fail silently at knowledge-base boundaries. An explicit confidence score — derived from retrieval relevance and reasoning certainty — makes the failure mode observable. Low confidence routes to a human with a pre-filled context packet instead of producing a plausible-but-wrong recommendation.

**Why tool use instead of a single prompt?**
Separating retrieval from reasoning lets each step be tested in isolation. The retrieval call is deterministic and inspectable. The reasoning step is the only LLM call. Iterative retrieval (up to N rounds) lets the agent follow a thread — first fetch the runbook, then fetch the matching code pattern — instead of over-fetching on a single broad query.

---

## Quickstart

```bash
git clone https://github.com/hchava/dispatch
cd dispatch
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export ANTHROPIC_API_KEY=sk-...

# Index the full corpus (all 5 document types)
python -m dispatch.ingest.loader --corpus corpus/

# Run a demo alert through the agent
python demo/run_demo.py

# Try the second sample alert (Kafka late-arrival spike)
python demo/run_demo.py --alert 1
```

---

## Demo output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DISPATCH — Pipeline Oncall Triage Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╭─ Incoming Alert ───────────────────────────────╮
│ Pipeline:  orders-fact                         │
│ Alert:     Daily refresh completed but row     │
│            count dropped 94% vs 7-day average  │
│ Metric:    row_count  |  Threshold: drop > 20% │
╰────────────────────────────────────────────────╯

[retrieve] "orders-fact row count drop daily refresh"
  → runbook: pipeline-failure.md        (score 0.91)
  → contract: orders-fact.yaml          (score 0.88)
  → incident: inc-002.md                (score 0.85)

[retrieve] "schema drift nullable column backfill repair"
  → code_pattern: schema-drift-repair.md  (score 0.89)
  → code_pattern: idempotent-backfill.md  (score 0.84)
  → validation:   row-count-check.md      (score 0.81)

╭─ Triage Report ────────────────────────────────╮
│ Pipeline:   orders-fact                        │
│ Severity:   P1                                 │
│ Root cause: Schema drift — nullable column     │
│             added upstream without contract    │
│             update; partition pruning silently │
│             dropped all rows post-change       │
│ Actions:    1. Run schema diff vs contract     │
│             2. Fix ingestion to select only    │
│                contract columns                │
│             3. Backfill affected partition     │
│                (idempotent delete → reinsert)  │
│             4. Update data contract            │
│             5. Add schema validation gate at   │
│                ingestion boundary              │
│ Confidence: 0.89                               │
│ Escalate:   No                                 │
╰────────────────────────────────────────────────╯
```

---

## Corpus

The knowledge base is a directory of structured documents. Each type uses YAML frontmatter for metadata-filtered retrieval.

### Runbooks (`corpus/runbooks/*.md`)
Triage playbooks for classes of failure. Pipeline `"*"` applies to all pipelines.

```markdown
---
pipeline: "*"
tags: [row-count-drop, schema-drift]
severity: P1
---
# Pipeline Failure Runbook
Step 1: Check job scheduler logs...
```

### Data contracts (`corpus/contracts/*.yaml`)
Schema, SLA, ownership, and lineage per pipeline.

```yaml
pipeline: orders-fact
owner: data-platform-team
sla: daily by 08:00 UTC
schema:
  - name: order_id
    type: STRING
    nullable: false
downstream_consumers:
  - revenue-metrics-cube
  - ml-feature-order-history
```

### Prior incidents (`corpus/incidents/*.md`)
Write-ups of past failures with root cause and resolution.

```markdown
---
pipeline: orders-fact
date: 2026-04-22
severity: P1
resolution: schema drift — upstream added nullable col
---
# INC-002 — row count dropped 94%
```

### Code patterns (`corpus/code_patterns/*.md`)
Reusable, tested implementation patterns for common repairs: idempotent backfill, schema drift repair, exactly-once writes.

```markdown
---
pipeline: "*"
tags: [backfill, idempotent, recovery]
pattern_type: code_pattern
---
# Pattern: Idempotent Partition Backfill
def backfill_partition(...):
    # 1. validate source non-empty
    # 2. delete target partition atomically
    # 3. reinsert from source
    # 4. validate counts match
```

### Validation examples (`corpus/validation_examples/*.md`)
Expected thresholds and test cases for data quality checks.

```markdown
---
pipeline: "*"
tags: [row-count, anomaly-detection]
pattern_type: validation_example
---
# Validation: Row Count Check
# drop > 20% vs 7d avg → P1
# spike > 3x vs 7d avg → P1 (duplicate ingestion)
```

---

## Project layout

```
dispatch/
├── dispatch/
│   ├── config.py              # model, embedding model, confidence threshold
│   ├── ingest/
│   │   ├── chunker.py         # sliding-window chunking + frontmatter extraction
│   │   └── loader.py          # walks all 5 corpus dirs → embeds → upserts ChromaDB
│   ├── retrieve/
│   │   ├── store.py           # ChromaDB wrapper (sentence-transformers embeddings)
│   │   └── search.py          # metadata-filtered semantic search
│   ├── agent/
│   │   ├── orchestrator.py    # Claude tool-use loop: retrieve → reason → triage JSON
│   │   ├── tools.py           # search_context tool definition (5 source types)
│   │   └── prompts.py         # system prompt + triage JSON schema
│   └── escalation/
│       └── handler.py         # confidence gate → Slack Block Kit escalation packet
├── corpus/
│   ├── runbooks/              # pipeline-failure · data-quality · schema-drift
│   ├── contracts/             # orders-fact · user-events
│   ├── incidents/             # inc-001 · inc-002 · inc-003
│   ├── code_patterns/         # idempotent-backfill · schema-drift-repair · exactly-once-write
│   └── validation_examples/   # row-count-check · null-rate-check · distribution-bounds
├── demo/
│   └── run_demo.py            # end-to-end demo: index → alert → triage report
└── tests/
    ├── test_chunker.py        # unit: frontmatter extraction, chunk boundaries
    └── test_search.py         # integration: ingest corpus → search → validate results
```

---

## Relationship to Anvil

[Anvil](https://github.com/hchava/anvil) handles the **coordination** layer — multiple specialized agents (researcher, developer, reviewer) critiquing each other's work through iterative feedback loops before converging on a decision.

Dispatch handles the **retrieval** layer — making sure any agent has the right institutional context before it reasons. Agents that lack context hallucinate; agents grounded in runbooks, contracts, and prior resolutions don't.

In production these compose:

```
Alert
  └─► Dispatch retrieves context
        └─► Anvil coordinates specialist agents over that context
              └─► HITL escalation gates the output
```

---

## License

MIT
