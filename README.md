# Dispatch

**AI agent that triages pipeline oncall incidents using RAG over runbooks, data contracts, and prior resolutions.**

Engineers rebuilding context from scratch every on-call shift is the most expensive form of toil in a data platform org. Dispatch eliminates it: when an alert fires, the agent retrieves the relevant runbook, matches it against prior incidents, checks the owning pipeline's data contract, and produces a structured triage report — severity, likely root cause, recommended action, and an escalation decision — before a human touches the page.

Built as a clean-room reference implementation of the pattern described in [this write-up](#architecture).

---

## What it does

```
Alert fires
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  Orchestrator (Claude — tool use)                        │
│                                                          │
│  1. search_context("pipeline failure orders-fact")       │──► ChromaDB
│     returns: runbook chunks + prior incident summaries   │    (runbooks /
│              + data contract for owning pipeline         │     contracts /
│                                                          │     incidents)
│  2. Reason over retrieved context                        │
│     → severity (P0/P1/P2)                               │
│     → likely root cause (schema drift / SLA breach /    │
│       data quality / infra)                              │
│     → recommended action (step-by-step)                 │
│     → confidence score                                   │
│                                                          │
│  3. If confidence < threshold → escalate to human        │
│     with pre-filled context packet                       │
└──────────────────────────────────────────────────────────┘
    │
    ▼
Triage report  (or)  Escalation packet → PagerDuty / Slack
```

---

## Architecture

### Three layers

| Layer | Component | What it does |
|-------|-----------|-------------|
| **Ingest** | `dispatch/ingest/` | Chunks runbooks, contracts, incidents → embeds → loads into ChromaDB |
| **Retrieve** | `dispatch/retrieve/` | Semantic search with metadata filtering (by source type, pipeline, severity) |
| **Agent** | `dispatch/agent/` | Claude orchestrator uses `search_context` as a tool; reasons over results; emits structured triage |

### Design decisions

**Why RAG over a fine-tuned model?** Runbooks and data contracts change weekly. Fine-tuning captures a snapshot; retrieval always returns current state. The knowledge base is the source of truth.

**Why metadata filtering before semantic search?** A generic "pipeline failure" query returns noise across all pipelines. Filtering by `pipeline_id` and `source_type` first narrows the search space so the top-k results are always relevant to the specific alert.

**Why a confidence threshold for HITL escalation?** Agents fail silently at knowledge boundaries. An explicit confidence score — computed from retrieval relevance and reasoning certainty — makes the failure mode visible and routes low-confidence cases to humans before they cause damage.

**Why tool use instead of a single prompt?** Separating retrieval from reasoning lets each step be tested independently. The retrieval call is deterministic; the reasoning step is the only LLM call. Easier to debug, easier to improve.

---

## Quickstart

```bash
git clone https://github.com/hchava/dispatch
cd dispatch
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export ANTHROPIC_API_KEY=sk-...

# Build the vector store from the sample corpus
python -m dispatch.ingest.loader --corpus corpus/

# Run a demo alert through the agent
python demo/run_demo.py
```

---

## Demo

```
$ python demo/run_demo.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DISPATCH — Pipeline Oncall Triage Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Alert: orders-fact daily refresh failed — row count dropped 94% vs 7d avg

[retrieve] search_context("orders-fact row count drop daily refresh")
  → runbook: pipeline-failure.md (score 0.91)
  → contract: orders-fact.yaml (score 0.88)
  → incident: inc-002.md — "orders-fact schema drift, upstream source added nullable col" (score 0.85)

[reason] Analyzing 3 context chunks...

┌─ Triage Report ──────────────────────────────────┐
│ Pipeline:    orders-fact                          │
│ Severity:    P1                                   │
│ Root cause:  Schema drift — nullable column added │
│              to upstream source without contract  │
│              update; partition pruning dropped    │
│              all rows post-schema change          │
│ Action:      1. Validate schema vs contract       │
│              2. Run backfill for affected date    │
│              3. Update contract + notify owners   │
│ Confidence:  0.87                                 │
│ Escalate:    No — confidence above threshold      │
└───────────────────────────────────────────────────┘
```

---

## Corpus format

### Runbooks (`corpus/runbooks/*.md`)

```markdown
---
pipeline: "*"
tags: [row-count-drop, refresh-failure, schema-drift]
severity: P1
---
# Pipeline Failure Runbook
...
```

### Data contracts (`corpus/contracts/*.yaml`)

```yaml
pipeline: orders-fact
owner: data-platform-team
sla: daily by 08:00 UTC
schema:
  - name: order_id
    type: STRING
    nullable: false
...
```

### Prior incidents (`corpus/incidents/*.md`)

```markdown
---
pipeline: orders-fact
date: 2026-03-14
severity: P1
resolution: schema drift — upstream added nullable col
---
...
```

---

## Project layout

```
dispatch/
├── dispatch/
│   ├── ingest/        # chunk, embed, load corpus
│   ├── retrieve/      # ChromaDB wrapper + semantic search
│   ├── agent/         # Claude orchestrator + tool definitions
│   └── escalation/    # HITL handler
├── corpus/
│   ├── runbooks/      # markdown runbooks
│   ├── contracts/     # yaml data contracts
│   └── incidents/     # prior incident write-ups
├── demo/
│   └── run_demo.py    # end-to-end demo
└── tests/
```

---

## Relationship to Anvil

[Anvil](https://github.com/hchava/anvil) handles the **coordination** layer — multiple agents critiquing each other's reasoning before converging on a design.

Dispatch handles the **retrieval** layer — making sure an agent has the right context before it reasons at all.

In production, these compose: Dispatch retrieves, Anvil coordinates across specialized sub-agents (researcher, developer, reviewer), HITL escalation gates the output.

---

## License

MIT
