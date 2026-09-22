"""Synthetic generator configuration and ground truth data models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class AttackCategory(str, Enum):
    SPAM = "SPAM"
    CURIOSITY_FUNNEL = "CURIOSITY_FUNNEL"
    AI_IMAGE_NETWORK = "AI_IMAGE_NETWORK"
    IMAGE_REUSE_NETWORK = "IMAGE_REUSE_NETWORK"
    LINK_ABUSE = "LINK_ABUSE"
    ACCOUNT_ROTATION = "ACCOUNT_ROTATION"
    MIXED_ATTACK = "MIXED_ATTACK"
    HIJACKED_ACCOUNT = "HIJACKED_ACCOUNT"
    AGED_ACCOUNT_ATTACK = "AGED_ACCOUNT_ATTACK"
    HUMAN_FARM = "HUMAN_FARM"


class LegitCategory(str, Enum):
    NORMAL = "NORMAL"
    NORMAL_HIGH_ENGAGEMENT = "NORMAL_HIGH_ENGAGEMENT"
    LEGIT_FANDOM = "LEGIT_FANDOM"
    LEGIT_AVATAR_REUSE = "LEGIT_AVATAR_REUSE"
    LEGIT_LINK_CREATOR = "LEGIT_LINK_CREATOR"
    LEGIT_SUGGESTIVE_AVATAR = "LEGIT_SUGGESTIVE_AVATAR"


EntityCategory = AttackCategory | LegitCategory


class MockDestination(BaseModel):
    """Synthetic target destination ending in *.local."""
    url: str
    domain: str
    category: str = "adult_dating"
    redirect_chain: list[str] = Field(default_factory=list)
    uses_shortener: bool = False
    cloaking: bool = False  # If True, scanner sees benign content while user sees flagged destination
    activation_delay_hours: float = 0.0  # Dormant hours before redirect activates
    known_bad: bool = False


class GroundTruthMetadata(BaseModel):
    """Ground-truth metadata attached to synthetic entities (analyst/test only)."""
    category: str
    is_attack: bool
    cluster_id: str | None = None
    funnel_depth: int = 0
    ai_likelihood_ground_truth: float = 0.0
    intended_destination: str | None = None
    notes: str = ""


class GeneratorConfig(BaseModel):
    """Configuration for deterministic synthetic data generation."""
    seed: int = 42
    variant: Literal["A", "B"] = "A"
    platform_profile: Literal["video_comments", "forum_communities", "chat_servers"] = "video_comments"
    actor_count: int = Field(default=1000, ge=20)
    base_rate: float = Field(default=0.05, ge=0.0001, le=1.0, description="Prevalence of attack actors (e.g. 0.05 = 5%)")
    start_time: datetime = Field(default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    duration_days: int = 30
    hmac_salt: str = "safeflow_synthetic_salt_2026"
