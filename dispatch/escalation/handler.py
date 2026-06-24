"""HITL escalation — package context and route to human."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from dispatch.agent.orchestrator import Alert, TriageReport


@dataclass
class EscalationPacket:
    alert: Alert
    report: TriageReport
    timestamp: str
    context_summary: str

    def to_slack_block(self) -> dict:
        """Format as a Slack Block Kit message for paging."""
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"🚨 Dispatch Escalation — {self.alert.pipeline}"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:*\n{self.report.severity}"},
                        {"type": "mrkdwn", "text": f"*Confidence:*\n{self.report.confidence:.0%}"},
                        {"type": "mrkdwn", "text": f"*Alert:*\n{self.alert.message}"},
                        {"type": "mrkdwn", "text": f"*Likely cause:*\n{self.report.likely_root_cause}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Why escalated:* {self.report.escalation_reason or 'Low confidence'}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Recommended actions (verify before executing):*\n"
                        + "\n".join(f"{i+1}. {a}" for i, a in enumerate(self.report.recommended_actions)),
                    },
                },
            ]
        }


def maybe_escalate(
    alert: Alert,
    report: TriageReport,
    threshold: float,
) -> EscalationPacket | None:
    """Return an escalation packet if the report warrants human review."""
    if not report.escalate and report.confidence >= threshold:
        return None

    return EscalationPacket(
        alert=alert,
        report=report,
        timestamp=datetime.now(timezone.utc).isoformat(),
        context_summary=(
            f"Agent used {report.context_chunks_used} context chunks. "
            f"Confidence: {report.confidence:.0%}. "
            f"Reason: {report.escalation_reason or 'below threshold'}"
        ),
    )
