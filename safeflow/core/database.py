"""Database persistence layer using SQLAlchemy 2.

Features:
- Stores metadata, perceptual hashes, tags, and decisions.
- STRICT INVARIANT: ZERO raw image bytes are stored in the database.
- SQLite default with optional external connection string.
- Automatic tag TTL expiry filtering.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class MediaRecord(Base):
    """Stores visual media metadata and perceptual hashes. ZERO image bytes."""
    __tablename__ = "media_records"

    media_id = Column(String(64), primary_key=True)
    actor_id = Column(String(64), nullable=False, index=True)
    phash = Column(String(32), nullable=True, index=True)
    dhash = Column(String(32), nullable=True)
    whash = Column(String(32), nullable=True)
    mirror_phash = Column(String(32), nullable=True, index=True)
    decision = Column(String(20), nullable=False)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    tags_json = Column(Text, default="[]")  # JSON array of {name, applied_at, expires_at}
    tag_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    def get_active_tags(self, now: datetime | None = None) -> list[str]:
        """Return list of active tags whose TTL has not expired."""
        current_time = now or datetime.now(timezone.utc)
        try:
            raw_tags = json.loads(self.tags_json or "[]")
        except Exception:
            return []

        active = []
        for tag in raw_tags:
            exp_str = tag.get("expires_at")
            if exp_str:
                exp_dt = datetime.fromisoformat(exp_str)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if current_time >= exp_dt:
                    continue  # expired
            active.append(tag.get("name", ""))
        return active


class AuditLogRecord(Base):
    """Hash-chained immutable audit log table."""
    __tablename__ = "audit_records"

    record_id = Column(String(64), primary_key=True)
    timestamp = Column(String(64), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    actor_id = Column(String(64), nullable=True)
    media_id = Column(String(64), nullable=True)
    details_json = Column(Text, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    record_hash = Column(String(64), nullable=False, unique=True)


class ReviewQueueRecord(Base):
    """Items held for human review triage."""
    __tablename__ = "review_queue"

    review_id = Column(String(64), primary_key=True)
    media_id = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)


class AppealRecord(Base):
    """Appeals submitted by creators for rejected or held uploads."""
    __tablename__ = "appeals"

    appeal_id = Column(String(64), primary_key=True)
    media_id = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, UPHELD, OVERTURNED
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class DatabaseManager:
    """Initializes and provides session access to the SafeFlow database."""

    def __init__(self, db_url: str = "sqlite:///:memory:") -> None:
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()
