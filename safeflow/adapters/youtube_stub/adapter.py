"""YouTube Platform Adapter Stub.

DISABLED BY DEFAULT.
SafeFlow does NOT perform live scraping, automated interaction, or unauthorized API calls.
Any future activation requires:
1. Authorized YouTube Data API v3 credentials.
2. Compliance with YouTube Terms of Service & Developer Policies.
3. Legal and privacy compliance review (data retention, GDPR, India DPDP Act).
"""

from __future__ import annotations

from typing import Any
from safeflow.adapters.base import PlatformAdapter


class YouTubeAdapterStub(PlatformAdapter):
    """Interface stub for YouTube platform ingestion."""

    platform_id: str = "youtube"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.enabled = False

    def ingest(self, raw_data: Any) -> dict[str, list[Any]]:
        if not self.enabled:
            raise PermissionError(
                "YouTube adapter is a disabled stub. SafeFlow runs strictly on synthetic/local data in MVP. "
                "Live platform interaction requires official API credentials, adherence to platform terms, "
                "and an institutional privacy/legal compliance review."
            )
        return {"actors": [], "spaces": [], "content": [], "media": [], "links": []}
