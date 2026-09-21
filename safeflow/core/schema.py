"""Canonical Pydantic v2 schemas for SafeFlow.

All models adhere to schema_version 1.0.0 and maintain platform neutrality.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: str = "1.0.0"


class SpaceKind(str, Enum):
    VIDEO = "video"
    THREAD = "thread"
    CHANNEL = "channel"
    COMMUNITY = "community"
    SERVER = "server"
    POST = "post"
    OTHER = "other"


class AudienceContext(str, Enum):
    GENERAL = "general"
    MIXED = "mixed"
    YOUTH_ORIENTED = "youth_oriented"
    ADULT_ONLY = "adult_only"


class ContentKind(str, Enum):
    COMMENT = "comment"
    POST = "post"
    MESSAGE = "message"
    REPLY = "reply"


class MediaRole(str, Enum):
    AVATAR = "avatar"
    BANNER = "banner"
    POST_MEDIA = "post_media"


class LinkSurface(str, Enum):
    PROFILE_DESCRIPTION = "profile_description"
    CONTENT = "content"
    FEATURED = "featured"
    OTHER = "other"


class RelationType(str, Enum):
    FOLLOWS = "follows"
    FEATURES = "features"
    MEMBER_OF = "member_of"
    REPLIES_TO = "replies_to"
    OTHER = "other"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GateDecision(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_TAGGED = "ALLOW_TAGGED"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class CanonicalBase(BaseModel):
    """Base class for all canonical SafeFlow entities."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_version: str = Field(default=SCHEMA_VERSION, description="Canonical schema semantic version")


class Actor(CanonicalBase):
    """Platform actor (user or channel), identified pseudonymously."""
    actor_id: str = Field(..., description="Pseudonymous actor identifier (salted HMAC)")
    platform_id: str = Field(..., description="Platform identifier (e.g. video_comments, forum_communities)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    display_name_hash: str = Field(..., description="Cryptographic hash of the display name")
    description_history: list[str] = Field(default_factory=list, description="Historical bio/profile texts")
    avatar_media_id: str | None = Field(default=None, description="Current avatar media identifier")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Platform-neutral attributes")


class PopularityMetric(CanonicalBase):
    raw_count: int = Field(default=0, ge=0)
    percentile: float = Field(default=0.0, ge=0.0, le=100.0, description="Platform-normalized percentile (0-100)")


class Space(CanonicalBase):
    """Contextual container (video, thread, channel, server)."""
    space_id: str
    kind: SpaceKind
    parent_space_id: str | None = None
    popularity: PopularityMetric = Field(default_factory=PopularityMetric)
    audience_context: AudienceContext = Field(default=AudienceContext.GENERAL)


class Content(CanonicalBase):
    """User-generated text or message content."""
    content_id: str
    actor_id: str
    space_id: str
    kind: ContentKind
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reply_to: str | None = None


class MediaTag(CanonicalBase):
    name: str = Field(..., description="Internal tag name, e.g. suggestive_presentation")
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = Field(default=None, description="TTL expiration for tag")


class Media(CanonicalBase):
    """Visual or uploaded media item."""
    media_id: str
    actor_id: str
    role: MediaRole = MediaRole.AVATAR
    perceptual_hashes: dict[str, str] = Field(
        default_factory=dict,
        description="Perceptual hashes: phash, dhash, whash, mirror_phash"
    )
    embedding_ref: str | None = None
    gate_result: GateDecision | None = None
    tags: list[MediaTag] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})


class Link(CanonicalBase):
    """Hyperlink or URL destination extracted from content or profile."""
    link_id: str
    actor_id: str
    surface: LinkSurface
    url_normalized: str
    domain: str
    redirect_chain: list[str] = Field(default_factory=list)


class Relation(CanonicalBase):
    """Directed connection between canonical entities."""
    src: str
    dst: str
    type: RelationType
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Signal(CanonicalBase):
    """Objective observation emitted by a SignalPlugin."""
    subject_type: Literal["actor", "space", "content", "media", "link", "network"]
    subject_id: str
    family: str = Field(..., description="Signal family (e.g. IMAGE_LINK, BEHAVIOR, TARGETING, DESTINATION, PROFILE_CHANGE)")
    name: str = Field(..., description="Machine-readable signal name")
    value: float = Field(..., description="Normalized signal value (typically 0.0 to 1.0)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list, description="IDs of supporting entities")
    producer: str = Field(..., description="SignalPlugin identifier")
    producer_version: str = Field(..., description="Version of the producing plugin")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Decision(CanonicalBase):
    """Explainable moderation recommendation produced by DecisionEngine."""
    subject: str = Field(..., description="Subject entity ID (e.g. actor_id)")
    level: RiskLevel = Field(..., description="Evaluated risk level")
    score: float = Field(..., ge=0.0, le=100.0, description="Composite risk score (0-100)")
    families_triggered: list[str] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})
    evidence: list[str] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})
    counter_evidence: list[str] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})
    recommended_action: str = Field(..., description="Policy pack recommendation (e.g. route to review)")
    visibility: Literal["analyst"] = Field(default="analyst", json_schema_extra={"visibility": "analyst"})


class RescanRequest(CanonicalBase):
    """Event emitted when an actor profile media requires re-assessment."""
    actor_id: str
    media_id: str
    reason: Literal["model_version_bump", "profile_image_change", "periodic_schedule"]
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
