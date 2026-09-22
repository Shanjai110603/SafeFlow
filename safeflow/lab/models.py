"""Data models for Threat Simulation Lab and Link Verification Queue."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from safeflow.core.schema import RiskLevel


class ThreatScenarioKind(str, Enum):
    CURIOSITY_SURGE = "curiosity_surge"
    AVATAR_MUTATION_RING = "avatar_mutation_ring"
    DORMANT_HIJACK_BURST = "dormant_hijack_burst"
    CLOAKED_REDIRECT_EVASION = "cloaked_redirect_evasion"
    LEGIT_VIRAL_MEME_WAVE = "legit_viral_meme_wave"


class QueueItemStatus(str, Enum):
    PENDING = "PENDING"
    RELEASED = "RELEASED"
    BLOCKED = "BLOCKED"


class QueueItem(BaseModel):
    """Item held in the risk-adaptive link verification queue."""
    model_config = ConfigDict(extra="forbid")

    item_id: str
    link_id: str
    actor_id: str
    url: str
    domain: str
    submitted_at: datetime
    release_at: datetime
    status: QueueItemStatus = QueueItemStatus.PENDING
    actor_risk: RiskLevel = RiskLevel.LOW
    is_attack_ground_truth: bool = False
    delayed_activation_hours: float = 0.0
    is_cloaked: bool = False
    reasons: list[str] = Field(default_factory=list)


class TradeoffPoint(BaseModel):
    """Performance measurements at a specific queue hold window."""
    model_config = ConfigDict(extra="forbid")

    window_minutes: int
    attack_interception_rate: float
    creator_delay_rate: float
    delayed_activation_interception_rate: float
    mean_hold_seconds_legit: float


class TradeoffReport(BaseModel):
    """Multi-window tradeoff evaluation report."""
    model_config = ConfigDict(extra="forbid")

    scenario: str
    points: list[TradeoffPoint] = Field(default_factory=list)
    optimal_window_minutes: int = 30
    recommendation: str = ""
