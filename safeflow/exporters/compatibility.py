"""Compatibility formatters for Coop and Osprey Trust & Safety engines."""

from __future__ import annotations

from typing import Any
from safeflow.core.schema import Decision, RiskLevel


class TSCompatibilityFormatter:
    """Translates canonical SafeFlow Decisions into industry standard T&S workflow formats."""

    @classmethod
    def to_osprey_action(cls, decision: Decision) -> dict[str, Any]:
        """Format as an Osprey moderation rule action record."""
        action_type = "ALLOW"
        if decision.level == RiskLevel.CRITICAL:
            action_type = "TAKEDOWN_ACTOR"
        elif decision.level == RiskLevel.HIGH:
            action_type = "ROUTE_TO_QUEUE"
        elif decision.level == RiskLevel.MEDIUM:
            action_type = "RATE_LIMIT_AND_VERIFY"

        return {
            "entity_id": decision.subject,
            "entity_type": "actor",
            "action": action_type,
            "confidence": round(decision.score / 100.0, 4),
            "tags": [f"safeflow_{f.lower()}" for f in decision.families_triggered],
            "rule_name": f"safeflow_{decision.level.value.lower()}_rule",
            "reasons": decision.evidence,
        }

    @classmethod
    def to_coop_incident(cls, decision: Decision) -> dict[str, Any]:
        """Format as a Coop incident triage payload."""
        return {
            "incident_id": f"sf_inc_{decision.subject[:8]}",
            "target": {
                "id": decision.subject,
                "type": "USER",
            },
            "severity": decision.level.value,
            "policy_violation": "COORDINATED_FUNNEL_ABUSE" if decision.level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else "NONE",
            "signals_triggered": decision.families_triggered,
            "evidence_summary": "\n".join(f"- {e}" for e in decision.evidence),
            "counter_evidence_summary": "\n".join(f"- {c}" for c in decision.counter_evidence),
            "suggested_enforcement": decision.recommended_action,
        }
