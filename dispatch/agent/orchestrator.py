"""
Dispatch orchestrator — retrieve → reason → triage.

Claude uses search_context as a tool. The agent loop continues until
Claude stops calling tools and emits the final triage JSON.
"""

from __future__ import annotations
import json
from dataclasses import dataclass

import anthropic

from dispatch.config import CONFIG
from dispatch.retrieve.search import search, SearchResult
from dispatch.retrieve.store import VectorStore
from dispatch.agent.prompts import SYSTEM, TRIAGE_SCHEMA
from dispatch.agent.tools import SEARCH_CONTEXT_TOOL


@dataclass
class Alert:
    pipeline: str
    message: str
    metric: str = ""
    threshold_breached: str = ""


@dataclass
class TriageReport:
    severity: str
    likely_root_cause: str
    recommended_actions: list[str]
    confidence: float
    escalate: bool
    escalation_reason: str = ""
    context_chunks_used: int = 0


def _format_results(results: list[SearchResult]) -> str:
    if not results:
        return "No relevant context found."
    lines = []
    for r in results:
        lines.append(
            f"[{r.source_type.upper()} — {r.source_file} — score {r.score:.2f}]\n{r.text}"
        )
    return "\n\n---\n\n".join(lines)


def triage(alert: Alert, store: VectorStore, verbose: bool = False) -> TriageReport:
    client = anthropic.Anthropic()
    system = SYSTEM.format(
        max_rounds=CONFIG.max_retrieval_rounds,
        threshold=CONFIG.confidence_threshold,
    )

    alert_text = (
        f"Pipeline: {alert.pipeline}\n"
        f"Alert: {alert.message}\n"
    )
    if alert.metric:
        alert_text += f"Metric: {alert.metric}\n"
    if alert.threshold_breached:
        alert_text += f"Threshold: {alert.threshold_breached}\n"

    messages = [{"role": "user", "content": alert_text}]
    total_chunks = 0
    rounds = 0

    # Agentic loop: run until Claude stops calling search_context
    while rounds < CONFIG.max_retrieval_rounds:
        response = client.messages.create(
            model=CONFIG.model,
            max_tokens=2048,
            system=system,
            tools=[SEARCH_CONTEXT_TOOL],
            messages=messages,
        )

        # Collect assistant message (may contain text + tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:
            break  # Claude is done retrieving — emit triage

        # Execute all tool calls and return results
        tool_results = []
        for call in tool_calls:
            args = call.input
            results = search(
                query=args["query"],
                store=store,
                pipeline_filter=args.get("pipeline", alert.pipeline),
                source_types=args.get("source_types"),
            )
            total_chunks += len(results)
            context_text = _format_results(results)

            if verbose:
                print(f"  [retrieve] {args['query']!r} → {len(results)} chunks")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": context_text,
            })

        messages.append({"role": "user", "content": tool_results})
        rounds += 1

    # Final pass: ask Claude to emit structured triage JSON
    messages.append({
        "role": "user",
        "content": (
            "Based on the context retrieved, produce the triage report as JSON matching "
            "this schema:\n" + json.dumps(TRIAGE_SCHEMA, indent=2)
        ),
    })
    final = client.messages.create(
        model=CONFIG.model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    text = "".join(
        b.text for b in final.content if hasattr(b, "text")
    )
    # Extract JSON from the response (Claude may wrap it in a code block)
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    raw = json.loads(match.group()) if match else {}

    return TriageReport(
        severity=raw.get("severity", "P1"),
        likely_root_cause=raw.get("likely_root_cause", "Unknown"),
        recommended_actions=raw.get("recommended_actions", []),
        confidence=float(raw.get("confidence", 0.0)),
        escalate=bool(raw.get("escalate", True)),
        escalation_reason=raw.get("escalation_reason", ""),
        context_chunks_used=total_chunks,
    )
