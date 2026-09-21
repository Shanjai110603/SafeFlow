"""Tests validating canonical schemas and generic role-based field redaction."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from safeflow.core.roles import CreatorStatus, RoleRedactor, UserRole
from safeflow.core.schema import (
    SCHEMA_VERSION,
    Actor,
    AudienceContext,
    Content,
    ContentKind,
    Decision,
    GateDecision,
    Link,
    LinkSurface,
    Media,
    MediaRole,
    MediaTag,
    PopularityMetric,
    Relation,
    RelationType,
    RescanRequest,
    RiskLevel,
    Signal,
    Space,
    SpaceKind,
)


def test_canonical_models_schema_version_and_serialization():
    """Verify all canonical entities instantiate with schema_version 1.0.0 and serialize cleanly."""
    now = datetime.now(timezone.utc)

    # Actor
    actor = Actor(
        actor_id="actor_h_123",
        platform_id="video_comments",
        display_name_hash="hash_abc",
        description_history=["Previous bio", "Current bio"],
        avatar_media_id="media_456"
    )
    assert actor.schema_version == SCHEMA_VERSION
    dumped_actor = actor.model_dump()
    assert dumped_actor["actor_id"] == "actor_h_123"

    # Space
    space = Space(
        space_id="space_vid_1",
        kind=SpaceKind.VIDEO,
        popularity=PopularityMetric(raw_count=10000, percentile=95.5),
        audience_context=AudienceContext.GENERAL
    )
    assert space.schema_version == SCHEMA_VERSION
    assert space.popularity.percentile == 95.5

    # Content
    content = Content(
        content_id="comment_789",
        actor_id="actor_h_123",
        space_id="space_vid_1",
        kind=ContentKind.COMMENT,
        text="Great analysis, check out my profile!"
    )
    assert content.schema_version == SCHEMA_VERSION

    # Media
    media = Media(
        media_id="media_456",
        actor_id="actor_h_123",
        role=MediaRole.AVATAR,
        perceptual_hashes={"phash": "1234567812345678", "mirror_phash": "8765432187654321"},
        gate_result=GateDecision.ALLOW_TAGGED,
        tags=[MediaTag(name="suggestive_presentation")]
    )
    assert media.schema_version == SCHEMA_VERSION

    # Link
    link = Link(
        link_id="link_001",
        actor_id="actor_h_123",
        surface=LinkSurface.PROFILE_DESCRIPTION,
        url_normalized="https://short.local/xyz",
        domain="short.local",
        redirect_chain=["https://short.local/xyz", "https://target.local/landing"]
    )
    assert link.schema_version == SCHEMA_VERSION

    # Relation
    relation = Relation(
        src="actor_h_123",
        dst="space_vid_1",
        type=RelationType.REPLIES_TO,
        ts=now
    )
    assert relation.schema_version == SCHEMA_VERSION

    # Signal
    signal = Signal(
        subject_type="media",
        subject_id="media_456",
        family="IMAGE_LINK",
        name="suggestive_presentation",
        value=0.75,
        confidence=1.0,
        evidence_refs=["media_456"],
        producer="image_gate",
        producer_version="1.0.0",
        ts=now
    )
    assert signal.schema_version == SCHEMA_VERSION

    # Decision
    decision = Decision(
        subject="actor_h_123",
        level=RiskLevel.MEDIUM,
        score=45.0,
        families_triggered=["IMAGE_LINK"],
        evidence=["suggestive_presentation_avatar"],
        counter_evidence=["comment_text_benign"],
        recommended_action="Route to human review queue"
    )
    assert decision.schema_version == SCHEMA_VERSION

    # RescanRequest
    rescan = RescanRequest(
        actor_id="actor_h_123",
        media_id="media_456",
        reason="model_version_bump",
        requested_at=now
    )
    assert rescan.schema_version == SCHEMA_VERSION


def test_json_schema_generation():
    """Verify JSON Schema generation on all models."""
    for model in [Actor, Space, Content, Media, Link, Relation, Signal, Decision, RescanRequest]:
        schema = model.model_json_schema()
        assert "properties" in schema
        assert "schema_version" in schema["properties"]
        assert schema["properties"]["schema_version"]["default"] == SCHEMA_VERSION


def test_generic_role_redaction_on_decision_model():
    """Verify RoleRedactor strips analyst-only fields when redacting for CREATOR."""
    decision = Decision(
        subject="actor_h_123",
        level=RiskLevel.HIGH,
        score=75.0,
        families_triggered=["IMAGE_LINK", "BEHAVIOR", "DESTINATION"],
        evidence=["reused_avatar_cluster", "high_targeting_ratio"],
        counter_evidence=["account_age_old"],
        recommended_action="Route to senior review queue"
    )

    # 1. Redact for CREATOR
    creator_dict = RoleRedactor.redact(decision, role=UserRole.CREATOR)
    # Allowed fields
    assert creator_dict["subject"] == "actor_h_123"
    assert creator_dict["level"] == "HIGH"
    assert creator_dict["score"] == 75.0
    assert creator_dict["recommended_action"] == "Route to senior review queue"
    # Stripped analyst-only fields
    assert "families_triggered" not in creator_dict
    assert "evidence" not in creator_dict
    assert "counter_evidence" not in creator_dict
    assert "visibility" not in creator_dict

    # 2. Redact for ANALYST -> all fields visible
    analyst_dict = RoleRedactor.redact(decision, role=UserRole.ANALYST)
    assert "families_triggered" in analyst_dict
    assert "evidence" in analyst_dict
    assert "counter_evidence" in analyst_dict
    assert analyst_dict["families_triggered"] == ["IMAGE_LINK", "BEHAVIOR", "DESTINATION"]


def test_creator_response_utility():
    """Verify standardized non-revealing creator response helper."""
    # Allow
    resp_allow = RoleRedactor.to_creator_response("ALLOW", media_id="med_1")
    assert resp_allow.status == CreatorStatus.ACCEPTED
    assert "approved" in resp_allow.message.lower()
    assert resp_allow.appeal_token is None

    # Review
    resp_review = RoleRedactor.to_creator_response("REVIEW", media_id="med_2", appeal_token="tok_rev")
    assert resp_review.status == CreatorStatus.UNDER_REVIEW
    assert "pending review" in resp_review.message.lower()
    assert resp_review.appeal_token == "tok_rev"

    # Block
    resp_block = RoleRedactor.to_creator_response("BLOCK", media_id="med_3", appeal_token="tok_blk")
    assert resp_block.status == CreatorStatus.REJECTED
    assert "does not meet" in resp_block.message.lower()
    assert resp_block.appeal_token == "tok_blk"
