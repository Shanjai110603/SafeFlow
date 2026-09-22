"""SafeFlow Platform Adapters: Convert external platform schemas into canonical entities."""

from safeflow.adapters.base import PlatformAdapter
from safeflow.adapters.activitypub import ActivityPubAdapter

__all__ = ["PlatformAdapter", "ActivityPubAdapter"]
