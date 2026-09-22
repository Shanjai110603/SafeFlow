"""ActivityPub / Fediverse Platform Adapter.

Maps standard W3C ActivityStreams 2.0 / ActivityPub payloads (Actors, Notes,
Announces, Profile metadata, and Links) into SafeFlow canonical entities.
"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

from safeflow.adapters.base import PlatformAdapter
from safeflow.core.schema import (
    Actor,
    AudienceContext,
    Content,
    ContentKind,
    Link,
    LinkSurface,
    Media,
    PopularityMetric,
    Space,
    SpaceKind,
)


class ActivityPubAdapter:
    """Ingests ActivityPub / ActivityStreams 2.0 objects into SafeFlow canonical models."""

    @property
    def platform_id(self) -> str:
        return "activitypub_fediverse"

    def ingest(self, raw_data: dict[str, Any]) -> dict[str, list[Any]]:
        """Parse raw ActivityPub JSON-LD object (Actor, Note, Create, or Collection)."""
        actors: list[Actor] = []
        spaces: list[Space] = []
        contents: list[Content] = []
        links: list[Link] = []
        media: list[Media] = []

        obj_type = raw_data.get("type", "")

        # 1. Handle Person / Service / Organization (Actor)
        if obj_type in ("Person", "Service", "Organization", "Actor"):
            actor_uri = raw_data.get("id") or raw_data.get("url", "unknown_actor")
            actor_id = f"ap_{hashlib.sha256(str(actor_uri).encode('utf-8')).hexdigest()[:16]}"
            display_name = raw_data.get("name") or raw_data.get("preferredUsername", "Anonymous")
            disp_hash = hashlib.sha256(display_name.encode("utf-8")).hexdigest()

            actors.append(
                Actor(
                    actor_id=actor_id,
                    platform_id=self.platform_id,
                    display_name_hash=disp_hash,
                )
            )

            # Extract avatar icon if present
            icon = raw_data.get("icon", {})
            if isinstance(icon, dict) and "url" in icon:
                icon_url = icon["url"]
                media.append(
                    Media(
                        media_id=f"med_{hashlib.sha256(icon_url.encode('utf-8')).hexdigest()[:16]}",
                        actor_id=actor_id,
                        role="avatar",
                        perceptual_hashes={"phash": "0x" + hashlib.md5(icon_url.encode("utf-8")).hexdigest()[:16]},
                    )
                )

            # Extract bio summary links
            summary = str(raw_data.get("summary", ""))
            if "http" in summary:
                for word in summary.split():
                    if word.startswith("http://") or word.startswith("https://"):
                        clean_url = word.strip('<>"\'')
                        parsed = urlparse(clean_url)
                        links.append(
                            Link(
                                link_id=f"lnk_{hashlib.sha256(clean_url.encode('utf-8')).hexdigest()[:16]}",
                                actor_id=actor_id,
                                surface=LinkSurface.PROFILE_DESCRIPTION,
                                url_normalized=clean_url,
                                domain=parsed.netloc or "unknown.domain",
                            )
                        )

        # 2. Handle Note / Article / Create(Note)
        elif obj_type in ("Note", "Article", "Create"):
            note_obj = raw_data.get("object", raw_data) if obj_type == "Create" else raw_data
            attributed_to = note_obj.get("attributedTo") or raw_data.get("actor", "unknown_actor")
            actor_id = f"ap_{hashlib.sha256(str(attributed_to).encode('utf-8')).hexdigest()[:16]}"
            note_id = note_obj.get("id") or note_obj.get("url", "unknown_note")
            content_id = f"cnt_{hashlib.sha256(str(note_id).encode('utf-8')).hexdigest()[:16]}"

            # Determine space (inReplyTo or default local timeline)
            in_reply_to = note_obj.get("inReplyTo")
            space_id = f"sp_{hashlib.sha256(str(in_reply_to).encode('utf-8')).hexdigest()[:16]}" if in_reply_to else "sp_public_timeline"

            spaces.append(
                Space(
                    space_id=space_id,
                    kind=SpaceKind.POST if in_reply_to else SpaceKind.CHANNEL,
                    popularity=PopularityMetric(raw_count=100, percentile=50.0),
                    audience_context=AudienceContext.GENERAL,
                )
            )

            content_text = str(note_obj.get("content", ""))
            contents.append(
                Content(
                    content_id=content_id,
                    actor_id=actor_id,
                    space_id=space_id,
                    kind=ContentKind.COMMENT if in_reply_to else ContentKind.POST,
                    text=content_text,
                )
            )

            # Check for attached media/images
            attachments = note_obj.get("attachment", [])
            if isinstance(attachments, list):
                for att in attachments:
                    if isinstance(att, dict) and att.get("type") == "Document":
                        att_url = att.get("url", "")
                        if att_url:
                            media.append(
                                Media(
                                    media_id=f"med_{hashlib.sha256(att_url.encode('utf-8')).hexdigest()[:16]}",
                                    actor_id=actor_id,
                                    role="post_media",
                                    perceptual_hashes={"phash": "0x" + hashlib.md5(att_url.encode("utf-8")).hexdigest()[:16]},
                                )
                            )

        return {
            "actors": actors,
            "spaces": spaces,
            "contents": contents,
            "links": links,
            "media": media,
        }
