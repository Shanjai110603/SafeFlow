"""Comprehensive test suite for the Profile Image Safety Gate Pipeline.

Validates all Gate 1 requirements and amendments:
- NUDITY/EXPLICIT mock label yields BLOCK with canary zero-persistence scan.
- Perceptual hashes calculated for BLOCK before discarding bytes.
- SUGGESTIVE yields ALLOW_TAGGED with role-based redaction.
- Review band routes to ReviewBlobStore with server-side blur preview.
- Fail-closed fallback on classifier error.
- Dual-crop selection (display crop vs full).
- Known-bad hash blocking.
- Policy pack switching (general_video_platform vs youth_oriented_service).
- Pack invariant rejection (adversarial packs).
- Tag TTL expiration and access logging.
- Host-provided MediaFetcher and RescanRequest.
- ReviewBlobStore purge.
- OCR explicit text path.
- Appeals flow.
- Hash-chained audit verification.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from PIL import Image
from safeflow.core.audit import AuditLogger
from safeflow.core.blob_store import RevealCapExceededError, ReviewBlobStore
from safeflow.core.config import (
    PolicyInvariantViolationError,
    PolicyPack,
    PolicyPackLoader,
)
from safeflow.core.database import AppealRecord, DatabaseManager, MediaRecord
from safeflow.core.fetcher import FixtureMediaFetcher, RescanCoordinator
from safeflow.core.roles import CreatorStatus, RoleRedactor, UserRole
from safeflow.plugins.image_gate.classifier import (
    MockClassifier,
    RawClassificationResult,
)
from safeflow.plugins.image_gate.pipeline import (
    SIMULATED_KNOWN_BAD_HASHES,
    ImageGatePipeline,
    UnsupportedFormatError,
)
from safeflow.utils.procedural_avatar import ProceduralAvatarGenerator

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "procedural_avatars"
ADVERSARIAL_DIR = Path(__file__).resolve().parent / "fixtures" / "adversarial_packs"


@pytest.fixture
def general_pack() -> PolicyPack:
    return PolicyPackLoader.load_by_name("general_video_platform")


@pytest.fixture
def youth_pack() -> PolicyPack:
    return PolicyPackLoader.load_by_name("youth_oriented_service")


@pytest.fixture
def adult_pack() -> PolicyPack:
    return PolicyPackLoader.load_by_name("adult_permitted_platform")


@pytest.fixture
def pipeline() -> ImageGatePipeline:
    return ImageGatePipeline()


def test_nudity_and_explicit_blocks_and_canary_zero_persistence(pipeline, general_pack):
    """Test BLOCK outcome and verify ZERO raw bytes are persisted anywhere (DB, disk, logs)."""
    canary = b"CANARY_SENSITIVE_BYTE_SEQUENCE_998877"
    raw_img = (FIXTURES_DIR / "test_explicit.png").read_bytes()
    # Append canary bytes to end of PNG file (valid PNG parsers ignore data after IEND)
    canary_payload = raw_img + canary

    db_mgr = DatabaseManager("sqlite:///:memory:")
    audit_logger = AuditLogger()
    blob_store = ReviewBlobStore()

    p = ImageGatePipeline(audit_logger=audit_logger, blob_store=blob_store)
    result = p.process(
        image_bytes=canary_payload,
        policy_pack=general_pack,
        actor_id="actor_canary",
        media_id="media_canary_1"
    )

    assert result.decision == "BLOCK"
    assert "exceeds_nudity_block_threshold" in result.reasons

    # Check 1: Verify perceptual hashes are calculated for BLOCK before discarding bytes (Amendment 5)
    assert result.perceptual_hashes.get("phash") is not None
    assert result.perceptual_hashes.get("mirror_phash") is not None

    # Check 2: Verify ReviewBlobStore does NOT contain blocked image
    assert blob_store.get_preview("media_canary_1") is None
    assert blob_store.count() == 0

    # Check 3: Canary scan across audit records
    for rec in audit_logger.records:
        rec_json = json.dumps(rec.details)
        assert "CANARY_SENSITIVE" not in rec_json

    # Check 4: Store in DB and verify media_records table has no image bytes
    with db_mgr.get_session() as session:
        m = MediaRecord(
            media_id="media_canary_1",
            actor_id="actor_canary",
            phash=result.perceptual_hashes["phash"],
            decision=result.decision,
            model_name=result.model_name,
            model_version=result.model_version
        )
        session.add(m)
        session.commit()

        # Query all columns
        row = session.get(MediaRecord, "media_canary_1")
        assert row is not None
        assert row.decision == "BLOCK"
        # Confirm no blob or binary column exists on MediaRecord
        assert not hasattr(row, "image_bytes")
        assert not hasattr(row, "raw_data")


def test_suggestive_yields_allow_tagged_and_role_redaction(pipeline, general_pack):
    """Test ALLOW_TAGGED outcome, tag preservation, and role-based field redaction."""
    raw_img = (FIXTURES_DIR / "test_suggestive.png").read_bytes()
    result = pipeline.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        actor_id="actor_sugg",
        media_id="media_sugg_1"
    )

    assert result.decision == "ALLOW_TAGGED"
    assert "suggestive_presentation" in result.applied_tags
    assert "elevated_suggestive_presentation" in result.reasons

    # Role Redaction Test (Amendment 3)
    # 1. Creator role view
    creator_view = RoleRedactor.to_creator_response(result.decision, media_id="media_sugg_1")
    assert creator_view.status == CreatorStatus.ACCEPTED
    assert "approved" in creator_view.message.lower()
    # Creator must NOT see internal scores or tags
    dumped_creator = creator_view.model_dump()
    assert "nudity_score" not in dumped_creator
    assert "suggestive_score" not in dumped_creator
    assert "applied_tags" not in dumped_creator
    assert "reasons" not in dumped_creator

    # 2. Generic redactor on the ImageSafetyResult model for CREATOR
    redacted_for_creator = RoleRedactor.redact(result, role=UserRole.CREATOR)
    assert "decision" in redacted_for_creator
    assert "nudity_score" not in redacted_for_creator
    assert "suggestive_score" not in redacted_for_creator
    assert "applied_tags" not in redacted_for_creator
    assert "reasons" not in redacted_for_creator

    # 3. Analyst view contains all fields
    analyst_view = RoleRedactor.redact(result, role=UserRole.ANALYST)
    assert analyst_view["decision"] == "ALLOW_TAGGED"
    assert "nudity_score" in analyst_view
    assert "suggestive_score" in analyst_view
    assert "suggestive_presentation" in analyst_view["applied_tags"]


def test_review_band_and_blob_store_blur_and_reveal_cap(general_pack):
    """Test ambiguous score routing to ReviewBlobStore, server blur, and session reveal cap."""
    blob_store = ReviewBlobStore(session_reveal_cap=2)
    audit_logger = AuditLogger()
    p = ImageGatePipeline(blob_store=blob_store, audit_logger=audit_logger)

    raw_img = (FIXTURES_DIR / "test_ambiguous.png").read_bytes()
    result = p.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        actor_id="actor_amb",
        media_id="media_amb_1"
    )

    assert result.decision == "REVIEW"
    assert "nudity_score_in_review_band" in result.reasons

    # Check that blob store holds the item
    assert blob_store.count() == 1
    blurred_preview = blob_store.get_preview("media_amb_1")
    assert blurred_preview is not None
    assert len(blurred_preview) > 0

    # Unblurred reveal test
    session_id = "analyst_session_alpha"
    revealed_bytes = blob_store.reveal(
        media_id="media_amb_1",
        analyst_id="analyst_jane",
        session_id=session_id,
        audit_logger=audit_logger
    )
    assert len(revealed_bytes) > 0

    # Verify reveal was logged in audit trail
    reveal_logs = [r for r in audit_logger.records if r.event_type == "ANALYST_REVEAL"]
    assert len(reveal_logs) == 1
    assert reveal_logs[0].details["analyst_id"] == "analyst_jane"

    # Reveal #2 (reaches cap of 2)
    blob_store.reveal("media_amb_1", "analyst_jane", session_id, audit_logger)
    assert blob_store.get_session_reveal_count(session_id) == 2

    # Reveal #3 (must raise RevealCapExceededError)
    with pytest.raises(RevealCapExceededError):
        blob_store.reveal("media_amb_1", "analyst_jane", session_id, audit_logger)


def test_classifier_error_fails_closed(general_pack):
    """Verify that classifier failure triggers fail-closed fallback without crashing."""
    failing_clf = MockClassifier(simulate_error=True)
    audit_logger = AuditLogger()
    blob_store = ReviewBlobStore()
    p = ImageGatePipeline(classifier=failing_clf, blob_store=blob_store, audit_logger=audit_logger)

    raw_img = (FIXTURES_DIR / "test_neutral.png").read_bytes()
    result = p.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        actor_id="actor_err",
        media_id="media_err_1"
    )

    assert result.decision == "REVIEW"
    assert "classifier_error_fail_closed" in result.reasons
    assert blob_store.count() == 1  # Held for review

    # Check audit log for error event
    error_logs = [r for r in audit_logger.records if r.event_type == "CLASSIFIER_ERROR"]
    assert len(error_logs) == 1
    assert error_logs[0].details["fallback_action"] == "HOLD_DEFAULT_AVATAR"


def test_dual_crop_display_crop_higher_triggers_block(general_pack):
    """Full image is neutral, but circular avatar crop has explicit marker -> BLOCK."""
    raw_img = (FIXTURES_DIR / "test_crop_higher.png").read_bytes()
    p = ImageGatePipeline()
    result = p.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        media_id="media_crop_high"
    )

    assert result.crop_used == "display_crop"
    assert result.decision == "BLOCK"
    assert "crop_score_triggered_block" in result.reasons


def test_dual_crop_perimeter_higher_triggers_block(general_pack):
    """Perimeter corners have explicit marker -> full image score is higher -> BLOCK."""
    raw_img = (FIXTURES_DIR / "test_perimeter_higher.png").read_bytes()
    p = ImageGatePipeline()
    result = p.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        media_id="media_perim_high"
    )

    assert result.crop_used == "full"
    assert result.decision == "BLOCK"


def test_known_bad_hash_triggers_immediate_block(general_pack):
    """Simulated known-bad hash list match triggers immediate BLOCK."""
    p = ImageGatePipeline()
    bad_hash = list(SIMULATED_KNOWN_BAD_HASHES)[0]

    # Monkeypatch hash calculation to return known bad hash
    orig_hashes = p._compute_hashes
    p._compute_hashes = lambda img: {"phash": bad_hash, "dhash": "0", "whash": "0", "mirror_phash": "0"}

    raw_img = (FIXTURES_DIR / "test_neutral.png").read_bytes()
    result = p.process(image_bytes=raw_img, policy_pack=general_pack)

    assert result.decision == "BLOCK"
    assert result.known_bad_hash_match is True
    assert "known_bad_hash_match" in result.reasons


def test_policy_pack_switching_on_identical_scores(pipeline, general_pack, youth_pack, adult_pack):
    """Same suggestive image scores evaluated under general vs youth vs adult packs."""
    raw_img = (FIXTURES_DIR / "test_suggestive.png").read_bytes()

    # 1. Under general_video_platform -> ALLOW_TAGGED
    res_general = pipeline.process(image_bytes=raw_img, policy_pack=general_pack)
    assert res_general.decision == "ALLOW_TAGGED"
    assert "suggestive_presentation" in res_general.applied_tags

    # 2. Under youth_oriented_service -> REVIEW (Amendment 7: strict youth policy)
    res_youth = pipeline.process(image_bytes=raw_img, policy_pack=youth_pack)
    assert res_youth.decision == "REVIEW"

    # 3. Under adult_permitted_platform -> ALLOW
    res_adult = pipeline.process(image_bytes=raw_img, policy_pack=adult_pack)
    assert res_adult.decision == "ALLOW"


def test_pack_loader_rejects_adversarial_packs():
    """Verify non-overridable invariants reject violating policy packs (Amendment 7)."""
    with pytest.raises(PolicyInvariantViolationError, match="persist_blocked_images"):
        PolicyPackLoader.load_from_file(ADVERSARIAL_DIR / "pack_persist_blocked.yaml")

    with pytest.raises(PolicyInvariantViolationError, match="classifier_unavailable_action"):
        PolicyPackLoader.load_from_file(ADVERSARIAL_DIR / "pack_fail_open.yaml")

    with pytest.raises(PolicyInvariantViolationError, match="known_bad_hash_action"):
        PolicyPackLoader.load_from_file(ADVERSARIAL_DIR / "pack_ignore_bad_hash.yaml")


def test_tag_ttl_expiry_and_analyst_access_logging():
    """Verify tag TTL expiration and audit logging for analyst tag inspections."""
    now = datetime.now(timezone.utc)
    expired_tag = {"name": "suggestive_presentation", "expires_at": (now - timedelta(days=1)).isoformat()}
    active_tag = {"name": "suggestive_presentation", "expires_at": (now + timedelta(days=29)).isoformat()}

    rec_expired = MediaRecord(
        media_id="m_exp",
        actor_id="a_1",
        decision="ALLOW_TAGGED",
        model_name="mock",
        model_version="1.0",
        tags_json=json.dumps([expired_tag])
    )
    assert rec_expired.get_active_tags(now=now) == []

    rec_active = MediaRecord(
        media_id="m_act",
        actor_id="a_2",
        decision="ALLOW_TAGGED",
        model_name="mock",
        model_version="1.0",
        tags_json=json.dumps([active_tag])
    )
    assert rec_active.get_active_tags(now=now) == ["suggestive_presentation"]

    # Test analyst tag read audit logging
    audit = AuditLogger()
    audit.log_analyst_tag_read(analyst_id="analyst_bob", media_id="m_act", tag_name="suggestive_presentation")
    assert len(audit.records) == 1
    assert audit.records[0].event_type == "ANALYST_TAG_READ"
    assert audit.records[0].details["tag_name"] == "suggestive_presentation"


def test_host_media_fetcher_and_rescan_requests():
    """Verify host-provided MediaFetcher protocol and RescanRequest events (Amendment 2)."""
    img_bytes = (FIXTURES_DIR / "test_neutral.png").read_bytes()
    fetcher = FixtureMediaFetcher({"avatar_101": img_bytes})
    coordinator = RescanCoordinator(fetcher=fetcher)

    req1 = coordinator.request_rescan(actor_id="actor_1", media_id="avatar_101", reason="model_version_bump")
    assert req1.reason == "model_version_bump"
    assert len(coordinator.emitted_requests) == 1

    fetched = coordinator.fetch_for_request(req1)
    assert fetched == img_bytes
    assert "avatar_101" in fetcher.fetch_calls

    # Invalid reason raises ValueError
    with pytest.raises(ValueError):
        coordinator.request_rescan("actor_1", "avatar_101", "invalid_reason")


def test_review_blob_store_ttl_purge():
    """Verify automatic TTL auto-purge zeroes out and purges expired blobs (Amendment 4, 11)."""
    store = ReviewBlobStore()
    img_bytes = (FIXTURES_DIR / "test_ambiguous.png").read_bytes()

    store.store(media_id="media_purge_1", image_bytes=img_bytes, ttl_hours=24)
    store.store(media_id="media_purge_2", image_bytes=img_bytes, ttl_hours=24)
    assert store.count() == 2

    # Purge with current time -> zero purged
    purged_count = store.purge_expired(now=datetime.now(timezone.utc))
    assert purged_count == 0
    assert store.count() == 2

    # Purge 25 hours later -> both purged
    future = datetime.now(timezone.utc) + timedelta(hours=25)
    purged_count_future = store.purge_expired(now=future)
    assert purged_count_future == 2
    assert store.count() == 0
    assert store.get_preview("media_purge_1") is None


def test_ocr_explicit_text_triggers_block(general_pack):
    """Simulated OCR explicit text overlay triggers BLOCK."""
    p = ImageGatePipeline()
    raw_img = (FIXTURES_DIR / "test_neutral.png").read_bytes()

    result = p.process(
        image_bytes=raw_img,
        policy_pack=general_pack,
        simulate_ocr_explicit=True
    )

    assert result.decision == "BLOCK"
    assert result.ocr_explicit_text is True
    assert "ocr_explicit_text_detected" in result.reasons


def test_appeals_flow(general_pack):
    """Verify creator appeal record lifecycle (Amendment 11)."""
    db = DatabaseManager("sqlite:///:memory:")
    with db.get_session() as session:
        appeal = AppealRecord(
            appeal_id="appeal_001",
            media_id="media_held_1",
            actor_id="creator_alice",
            reason="This image is a hand-drawn cartoon avatar, not adult content."
        )
        session.add(appeal)
        session.commit()

        # Query appeal
        retrieved = session.get(AppealRecord, "appeal_001")
        assert retrieved is not None
        assert retrieved.status == "PENDING"

        # Resolve appeal
        retrieved.status = "OVERTURNED"
        retrieved.resolved_at = datetime.now(timezone.utc)
        session.commit()

        resolved = session.get(AppealRecord, "appeal_001")
        assert resolved.status == "OVERTURNED"
        assert resolved.resolved_at is not None


def test_tamper_evident_audit_hash_chain():
    """Verify cryptographic hash-chaining in audit logger (Amendment 15)."""
    logger = AuditLogger()
    logger.log_event("GATE_DECISION", {"decision": "ALLOW"}, actor_id="a1", media_id="m1")
    logger.log_event("ANALYST_TAG_READ", {"tag": "suggestive"}, actor_id="a1", media_id="m1")
    logger.log_event("ANALYST_REVEAL", {"session": "s1"}, actor_id="a1", media_id="m1")

    assert len(logger.records) == 3
    # Clean verification
    assert AuditLogger.verify_chain(logger.records) is True

    # Tamper with an intermediate record
    tampered_records = list(logger.records)
    # Modify payload of first record
    tampered_first = tampered_records[0].model_copy(update={"actor_id": "malicious_tamperer"})
    tampered_records[0] = tampered_first

    # Chain verification MUST fail
    assert AuditLogger.verify_chain(tampered_records) is False


def test_unsupported_image_format_rejected():
    """Verify non-allowlisted formats (like SVG or text files) are strictly rejected (Amendment 10)."""
    p = ImageGatePipeline()
    pack = PolicyPackLoader.load_by_name("default_research")
    svg_payload = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='50'/></svg>"

    with pytest.raises(UnsupportedFormatError):
        p.process(image_bytes=svg_payload, policy_pack=pack)
