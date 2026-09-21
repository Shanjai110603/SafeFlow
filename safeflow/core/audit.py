"""Cryptographic tamper-evident audit logger for SafeFlow.

Maintains an append-only hash-chained audit log for all gate decisions,
analyst inspections, reveal operations, and system events.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

GENESIS_HASH = "0" * 64

AuditEventType = Literal[
    "GATE_DECISION",
    "ANALYST_TAG_READ",
    "ANALYST_REVEAL",
    "CLASSIFIER_ERROR",
    "REVIEW_DECISION",
    "APPEAL_SUBMITTED",
    "TAG_EXPIRED",
    "RESCAN_TRIGGERED"
]


class AuditRecord(BaseModel):
    """Immutable, hash-chained audit record."""
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: AuditEventType
    actor_id: str | None = None
    media_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    record_hash: str

    @classmethod
    def compute_hash(
        cls,
        prev_hash: str,
        timestamp: str,
        event_type: str,
        actor_id: str | None,
        media_id: str | None,
        details: dict[str, Any]
    ) -> str:
        payload = {
            "prev_hash": prev_hash,
            "timestamp": timestamp,
            "event_type": event_type,
            "actor_id": actor_id,
            "media_id": media_id,
            "details": details,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AuditLogger:
    """Manages append-only audit trail with hash-chain verification."""

    def __init__(self, initial_prev_hash: str = GENESIS_HASH) -> None:
        self.last_hash: str = initial_prev_hash
        self._records: list[AuditRecord] = []

    @property
    def records(self) -> list[AuditRecord]:
        return list(self._records)

    def log_event(
        self,
        event_type: AuditEventType,
        details: dict[str, Any],
        actor_id: str | None = None,
        media_id: str | None = None
    ) -> AuditRecord:
        """Create and append a new hash-chained audit entry."""
        ts = datetime.now(timezone.utc).isoformat()
        rec_hash = AuditRecord.compute_hash(
            prev_hash=self.last_hash,
            timestamp=ts,
            event_type=event_type,
            actor_id=actor_id,
            media_id=media_id,
            details=details
        )
        record = AuditRecord(
            timestamp=ts,
            event_type=event_type,
            actor_id=actor_id,
            media_id=media_id,
            details=details,
            prev_hash=self.last_hash,
            record_hash=rec_hash
        )
        self.last_hash = rec_hash
        self._records.append(record)
        return record

    def log_gate_decision(
        self,
        actor_id: str,
        media_id: str,
        decision: str,
        model_name: str,
        model_version: str,
        policy_pack: str,
        thresholds: dict[str, Any],
        reasons: list[str],
        crop_used: str,
        scores: dict[str, float]
    ) -> AuditRecord:
        """Log an upload-time profile image safety gate evaluation."""
        return self.log_event(
            event_type="GATE_DECISION",
            actor_id=actor_id,
            media_id=media_id,
            details={
                "decision": decision,
                "model_name": model_name,
                "model_version": model_version,
                "policy_pack": policy_pack,
                "thresholds": thresholds,
                "reasons": reasons,
                "crop_used": crop_used,
                "scores": scores,
            }
        )

    def log_analyst_tag_read(
        self,
        analyst_id: str,
        media_id: str,
        tag_name: str
    ) -> AuditRecord:
        """Log an access inspection event when an analyst inspects internal tags."""
        return self.log_event(
            event_type="ANALYST_TAG_READ",
            media_id=media_id,
            details={
                "analyst_id": analyst_id,
                "tag_name": tag_name,
            }
        )

    def log_analyst_reveal(
        self,
        analyst_id: str,
        media_id: str,
        session_id: str,
        reveal_count: int
    ) -> AuditRecord:
        """Log an analyst action un-blurring a held image in the review queue."""
        return self.log_event(
            event_type="ANALYST_REVEAL",
            media_id=media_id,
            details={
                "analyst_id": analyst_id,
                "session_id": session_id,
                "session_reveal_count": reveal_count,
            }
        )

    def log_classifier_error(
        self,
        media_id: str,
        error_message: str,
        fallback_action: str
    ) -> AuditRecord:
        """Log a classifier failure and fail-closed resolution."""
        return self.log_event(
            event_type="CLASSIFIER_ERROR",
            media_id=media_id,
            details={
                "error": error_message,
                "fallback_action": fallback_action,
            }
        )

    @classmethod
    def verify_chain(cls, records: list[AuditRecord], expected_genesis: str = GENESIS_HASH) -> bool:
        """Validate the cryptographic integrity of an audit record chain."""
        if not records:
            return True

        current_prev = expected_genesis
        for rec in records:
            if rec.prev_hash != current_prev:
                return False
            expected_hash = AuditRecord.compute_hash(
                prev_hash=rec.prev_hash,
                timestamp=rec.timestamp,
                event_type=rec.event_type,
                actor_id=rec.actor_id,
                media_id=rec.media_id,
                details=rec.details
            )
            if rec.record_hash != expected_hash:
                return False
            current_prev = rec.record_hash

        return True
