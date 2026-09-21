"""Host-provided MediaFetcher protocol and rescan coordination.

Defines the interface through which SafeFlow queries platforms for media bytes
during rescan events, without performing unauthorized scraping or direct network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from safeflow.core.schema import RescanRequest


@runtime_checkable
class MediaFetcher(Protocol):
    """Protocol implemented by host platform to supply media bytes to SafeFlow."""

    def fetch_media(self, media_id: str) -> bytes | None:
        """Retrieve media bytes for a given media_id. Return None if not found/deleted."""
        ...


class FixtureMediaFetcher:
    """In-memory mock MediaFetcher used for testing rescan and re-evaluation flows."""

    def __init__(self, media_store: dict[str, bytes] | None = None) -> None:
        self._store: dict[str, bytes] = dict(media_store) if media_store else {}
        self.fetch_calls: list[str] = []

    def register_media(self, media_id: str, image_bytes: bytes) -> None:
        self._store[media_id] = image_bytes

    def fetch_media(self, media_id: str) -> bytes | None:
        self.fetch_calls.append(media_id)
        return self._store.get(media_id)


class RescanCoordinator:
    """Manages emission and dispatch of RescanRequest events."""

    def __init__(self, fetcher: MediaFetcher | None = None) -> None:
        self.fetcher = fetcher
        self.emitted_requests: list[RescanRequest] = []

    def request_rescan(
        self,
        actor_id: str,
        media_id: str,
        reason: str
    ) -> RescanRequest:
        """Emit a canonical RescanRequest event."""
        if reason not in ("model_version_bump", "profile_image_change", "periodic_schedule"):
            raise ValueError(f"Invalid rescan reason: '{reason}'")

        event = RescanRequest(
            actor_id=actor_id,
            media_id=media_id,
            reason=reason,  # type: ignore[arg-type]
            requested_at=datetime.now(timezone.utc)
        )
        self.emitted_requests.append(event)
        return event

    def fetch_for_request(self, request: RescanRequest) -> bytes | None:
        """Resolve a rescan request using the host fetcher."""
        if not self.fetcher:
            raise RuntimeError("No MediaFetcher registered with RescanCoordinator.")
        return self.fetcher.fetch_media(request.media_id)
