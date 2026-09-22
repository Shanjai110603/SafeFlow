"""Abstract base platform profile behavioral template."""

from __future__ import annotations

from abc import ABC, abstractmethod
import random
from typing import Any
from safeflow.core.schema import SpaceKind, ContentKind, AudienceContext


class BasePlatformProfile(ABC):
    """Defines topology, content vocabulary, timing, and popularity for a synthetic platform."""

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Identifier string, e.g. 'video_comments', 'forum_communities', 'chat_servers'."""
        ...

    @property
    @abstractmethod
    def primary_space_kind(self) -> SpaceKind:
        """Kind of primary leaf space (e.g. video, thread, channel)."""
        ...

    @property
    @abstractmethod
    def container_space_kind(self) -> SpaceKind:
        """Kind of parent space (e.g. channel, community, server)."""
        ...

    @property
    @abstractmethod
    def content_kind(self) -> ContentKind:
        """Kind of generated content (e.g. comment, post, message)."""
        ...

    @abstractmethod
    def sample_space_names(self, count: int, rng: random.Random) -> list[tuple[str, str, AudienceContext]]:
        """Sample (container_name, leaf_name, audience_context) tuples."""
        ...

    @abstractmethod
    def sample_benign_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        """Sample conversational, benign comments appropriate for the platform."""
        ...

    @abstractmethod
    def sample_spam_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        """Sample overtly promotional spam comments."""
        ...

    @abstractmethod
    def sample_fandom_comments(self, count: int, rng: random.Random, topic: str) -> list[str]:
        """Sample coordinated legitimate fan comments."""
        ...

    @abstractmethod
    def get_timing_delta_seconds(self, is_attack: bool, rng: random.Random, variant: str = "A") -> float:
        """Sample inter-arrival time between actions in seconds."""
        ...
