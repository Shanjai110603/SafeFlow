"""Tests for SafeFlow Milestone 9 Privacy Controls, Research Report, and Portability.

Validates:
1. Right-to-be-forgotten deletion cascade (deleting actor purges all related entities).
2. GDPR/CCPA data export.
3. Automated Research Report generation.
4. Portability: dynamic support for a 4th throwaway platform profile with zero core changes.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from safeflow.core.database import (
    AppealRecord,
    DatabaseManager,
    MediaRecord,
    ReviewQueueRecord,
)
from safeflow.core.decision.engine import DecisionEngine
from safeflow.core.schema import (
    Actor,
    AudienceContext,
    Content,
    ContentKind,
    Link,
    LinkSurface,
    Media,
    PopularityMetric,
    RiskLevel,
    Signal,
    Space,
    SpaceKind,
)
from safeflow.privacy.manager import PrivacyManager
from safeflow.report.generator import ResearchReportGenerator


@pytest.fixture
def db_session():
    db = DatabaseManager(db_url="sqlite:///:memory:")
    db.init_db() if hasattr(db, "init_db") else None
    with db.get_session() as session:
        yield session


def test_right_to_be_forgotten_deletion_cascade(db_session):
    actor_id = "actor_gdpr_victim"

    # Insert media record, review queue item, and appeal
    db_session.add(MediaRecord(
        media_id="m_1",
        actor_id=actor_id,
        phash="0x123",
        decision="HELD",
        model_name="ensemble",
        model_version="1.0.0",
    ))
    db_session.add(ReviewQueueRecord(
        review_id="rev_1",
        media_id="m_1",
        actor_id=actor_id,
        expires_at=datetime.now(timezone.utc),
    ))
    db_session.add(AppealRecord(
        appeal_id="app_1",
        media_id="m_1",
        actor_id=actor_id,
        reason="Mistake in classification",
    ))
    db_session.commit()

    # Execute deletion
    res = PrivacyManager.delete_actor_data(actor_id=actor_id, session=db_session)
    assert res["status"] == "PURGED"
    assert res["deleted_entities"]["media_records"] == 1
    assert res["deleted_entities"]["review_queue_items"] == 1
    assert res["deleted_entities"]["appeals"] == 1

    # Verify zero persistence
    assert db_session.query(MediaRecord).filter_by(actor_id=actor_id).first() is None
    assert db_session.query(ReviewQueueRecord).filter_by(actor_id=actor_id).first() is None
    assert db_session.query(AppealRecord).filter_by(actor_id=actor_id).first() is None


def test_gdpr_data_export(db_session):
    actor_id = "actor_gdpr_export"
    db_session.add(MediaRecord(
        media_id="m_exp",
        actor_id=actor_id,
        phash="0xabc",
        decision="ALLOW",
        model_name="ensemble",
        model_version="1.0.0",
    ))
    db_session.add(ReviewQueueRecord(
        review_id="rev_exp",
        media_id="m_exp",
        actor_id=actor_id,
        expires_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    exported = PrivacyManager.export_actor_data(actor_id=actor_id, session=db_session)
    assert exported["subject_id"] == actor_id
    assert len(exported["media_records"]) == 1
    assert exported["media_records"][0]["media_id"] == "m_exp"
    assert len(exported["review_queue_items"]) == 1
    assert exported["review_queue_items"][0]["review_id"] == "rev_exp"


def test_research_report_generation(tmp_path: Path):
    out_file = tmp_path / "RESEARCH_REPORT.md"
    report_text = ResearchReportGenerator.generate_report(out_file=out_file, seed=42, sample_actors=40)
    assert out_file.exists()
    assert "SafeFlow: Multi-Modal Detection of Coordinated Pathways" in report_text
    assert "Real-World Prevalence Reweighting" in report_text
    assert "Cross-Platform Generalization Transfer Matrix" in report_text


def test_platform_portability_throwaway_4th_profile():
    """Verify that a 4th throwaway platform profile can be instantiated and evaluated without core changes."""
    # 4th platform: microblog_stream
    space = Space(
        space_id="feed_stream_01",
        kind=SpaceKind.POST,
        popularity=PopularityMetric(raw_count=5000, percentile=92.0),
        audience_context=AudienceContext.GENERAL,
    )
    actor = Actor(
        actor_id="microblog_actor_01",
        platform_id="microblog_stream",
        display_name_hash="display_hash_444",
    )
    content = Content(
        content_id="post_01",
        actor_id=actor.actor_id,
        space_id=space.space_id,
        kind=ContentKind.POST,
        text="Check out my new project link in bio!",
    )
    link = Link(
        link_id="link_01",
        actor_id=actor.actor_id,
        surface=LinkSurface.PROFILE_DESCRIPTION,
        url_normalized="https://promo.funnel.local",
        domain="funnel.local",
    )

    signals = [
        Signal(
            subject_type="actor",
            subject_id=actor.actor_id,
            family="PROFILE_CHANGE",
            name="profile_bio_callout_score",
            value=0.85,
            confidence=0.9,
            producer="actor_profile",
            producer_version="1.0.0",
        ),
        Signal(
            subject_type="actor",
            subject_id=actor.actor_id,
            family="DESTINATION",
            name="link_max_dest_risk",
            value=0.88,
            confidence=0.9,
            producer="link_destination",
            producer_version="1.0.0",
        ),
        Signal(
            subject_type="actor",
            subject_id=actor.actor_id,
            family="TARGETING",
            name="targeting_percentile_conc",
            value=0.92,
            confidence=0.9,
            producer="targeting",
            producer_version="1.0.0",
        ),
    ]

    engine = DecisionEngine()
    decision = engine.evaluate_actor(actor.actor_id, signals)
    assert decision.level == RiskLevel.HIGH
    assert decision.score >= 42.0
    assert len(decision.families_triggered) == 3
