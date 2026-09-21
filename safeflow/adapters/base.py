"""Base PlatformAdapter protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from safeflow.core.schema import Actor, Content, Link, Media, Relation, Space


@runtime_checkable
class PlatformAdapter(Protocol):
    """Protocol for converting raw platform data into canonical entities."""

    @property
    def platform_id(self) -> str:
        """Unique platform profile identifier (e.g. 'video_comments', 'forum_communities')."""
        ...

    def ingest(self, raw_data: Any) -> dict[str, list[Any]]:
        """Parse raw platform payload and return mapped canonical entities."""
        ...
