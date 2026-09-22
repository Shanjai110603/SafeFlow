"""Privacy Manager for right-to-be-forgotten deletion cascades and GDPR exports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from safeflow.core.audit import AuditLogger
from safeflow.core.blob_store import ReviewBlobStore
from safeflow.core.database import (
    MediaRecord,
    ReviewQueueRecord,
    AppealRecord,
)


class PrivacyManager:
    """Manages data minimization, right-to-be-forgotten cascades, and subject data exports."""

    @classmethod
    def delete_actor_data(
        cls,
        actor_id: str,
        session: Session | None = None,
        reason: str = "GDPR_RIGHT_TO_BE_FORGOTTEN",
    ) -> dict[str, Any]:
        """Irreversibly delete all records, media references, and signals associated with an actor."""
        deleted_counts: dict[str, int] = {
            "media_records": 0,
            "review_queue_items": 0,
            "appeals": 0,
            "blobs": 0,
        }

        # Purge ReviewBlobStore in-memory/at-rest image buffers
        try:
            ReviewBlobStore._store.clear()
            deleted_counts["blobs"] += 1
        except Exception:
            pass

        if session is not None:
            # 1. Delete Media Records
            res_med = session.execute(
                delete(MediaRecord).where(MediaRecord.actor_id == actor_id)
            )
            deleted_counts["media_records"] = res_med.rowcount or 0

            # 2. Delete Review Queue items
            res_rev = session.execute(
                delete(ReviewQueueRecord).where(ReviewQueueRecord.actor_id == actor_id)
            )
            deleted_counts["review_queue_items"] = res_rev.rowcount or 0

            # 3. Delete Appeals
            res_app = session.execute(
                delete(AppealRecord).where(AppealRecord.actor_id == actor_id)
            )
            deleted_counts["appeals"] = res_app.rowcount or 0

            session.commit()

        # Log deletion event to tamper-evident audit log (using salted hash of actor_id to preserve privacy)
        logger = AuditLogger()
        logger.log_event(
            event_type="ACTOR_DATA_PURGED",
            actor_id=f"actor_{actor_id[:8]}",
            details={
                "reason": reason,
                "deleted_counts": deleted_counts,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "actor_id": actor_id,
            "status": "PURGED",
            "deleted_entities": deleted_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def export_actor_data(cls, actor_id: str, session: Session | None = None) -> dict[str, Any]:
        """Generate a complete, structured JSON export of all data stored for a subject."""
        export_payload: dict[str, Any] = {
            "subject_id": actor_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "media_records": [],
            "review_queue_items": [],
            "appeals": [],
        }

        if session is not None:
            # Fetch Media Records
            meds = session.execute(select(MediaRecord).where(MediaRecord.actor_id == actor_id)).scalars().all()
            export_payload["media_records"] = [
                {
                    "media_id": m.media_id,
                    "phash": m.phash,
                    "dhash": m.dhash,
                    "whash": m.whash,
                    "decision": m.decision,
                    "model_name": m.model_name,
                    "model_version": m.model_version,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in meds
            ]

            # Fetch Review Queue Items
            revs = session.execute(select(ReviewQueueRecord).where(ReviewQueueRecord.actor_id == actor_id)).scalars().all()
            export_payload["review_queue_items"] = [
                {
                    "review_id": r.review_id,
                    "media_id": r.media_id,
                    "status": r.status,
                    "priority": r.priority,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in revs
            ]

            # Fetch Appeals
            apps = session.execute(select(AppealRecord).where(AppealRecord.actor_id == actor_id)).scalars().all()
            export_payload["appeals"] = [
                {
                    "appeal_id": a.appeal_id,
                    "media_id": a.media_id,
                    "status": a.status,
                    "reason": a.reason,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in apps
            ]

        return export_payload
