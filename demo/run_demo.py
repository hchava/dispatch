"""
End-to-end demo: load corpus → triage a sample alert → show report.

Run:
    python demo/run_demo.py
"""

from __future__ import annotations
import sys
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from pincer.retrieve.store import VectorStore
from pincer.ingest.loader import load_corpus
from pincer.agent.orchestrator import Alert, triage
from pincer.escalation.handler import maybe_escalate
from pincer.config import CONFIG

SAMPLE_ALERTS = [
    Alert(
        pipeline="orders-fact",
        message="Daily refresh completed but row count dropped 94% vs 7-day average.",
        metric="row_count",
        threshold_breached="drop > 20%",
    ),
    Alert(
        pipeline="user-events",
        message="Late arrival rate spiked to 31% (baseline 0.8%). Kafka consumer restarted at 14:32 UTC.",
        metric="late_arrival_rate",
        threshold_breached="> 5%",
    ),
]


def run(alert_index: int = 0) -> None:
    console = Console()
    alert = SAMPLE_ALERTS[alert_index]

    console.rule("[bold cyan]PINCER — Pipeline Oncall Triage Agent[/bold cyan]")
    console.print()

    # Build vector store from sample corpus
    corpus_path = Path(__file__).parent.parent / "corpus"
    store = VectorStore()
    n = load_corpus(corpus_path, store)
    console.print(f"[dim]Loaded {n} chunks into vector store[/dim]\n")

    # Show the incoming alert
    console.print(Panel(
        f"[bold]Pipeline:[/bold] {alert.pipeline}\n"
        f"[bold]Alert:[/bold]    {alert.message}\n"
        f"[bold]Metric:[/bold]   {alert.metric}  |  "
        f"[bold]Threshold:[/bold] {alert.threshold_breached}",
        title="[yellow]Incoming Alert[/yellow]",
        border_style="yellow",
    ))
    console.print()

    # Run triage
    console.print("[dim]Running triage agent...[/dim]")
    report = triage(alert, store, verbose=True)
    console.print()

    # Show triage report
    severity_color = {"P0": "red", "P1": "yellow", "P2": "blue"}.get(report.severity, "white")
    escalate_str = "[red]YES — escalating to human[/red]" if report.escalate else "[green]No[/green]"

    table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    table.add_column("Field", style="bold", width=22)
    table.add_column("Value")
    table.add_row("Pipeline", alert.pipeline)
    table.add_row("Severity", f"[{severity_color}]{report.severity}[/{severity_color}]")
    table.add_row("Root Cause", report.likely_root_cause)
    table.add_row("Confidence", f"{report.confidence:.0%}")
    table.add_row("Escalate", escalate_str)
    table.add_row("Context chunks", str(report.context_chunks_used))

    if report.recommended_actions:
        actions = "\n".join(f"{i+1}. {a}" for i, a in enumerate(report.recommended_actions))
        table.add_row("Recommended Actions", actions)

    console.print(Panel(table, title="[cyan]Triage Report[/cyan]", border_style="cyan"))

    # Escalation
    packet = maybe_escalate(alert, report, CONFIG.confidence_threshold)
    if packet:
        console.print()
        console.print(Panel(
            packet.context_summary,
            title="[red]Escalation Packet[/red]",
            border_style="red",
        ))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert", type=int, default=0, help="Alert index (0 or 1)")
    args = parser.parse_args()
    run(args.alert)
