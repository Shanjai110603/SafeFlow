"""Platform profiles registry and factory for synthetic adapter."""

from __future__ import annotations

from safeflow.adapters.synthetic.profiles.base import BasePlatformProfile
from safeflow.adapters.synthetic.profiles.video_comments import VideoCommentsProfile
from safeflow.adapters.synthetic.profiles.forum_communities import ForumCommunitiesProfile
from safeflow.adapters.synthetic.profiles.chat_servers import ChatServersProfile

PROFILE_MAP: dict[str, type[BasePlatformProfile]] = {
    "video_comments": VideoCommentsProfile,
    "forum_communities": ForumCommunitiesProfile,
    "chat_servers": ChatServersProfile,
}


def get_platform_profile(name: str) -> BasePlatformProfile:
    """Retrieve platform profile instance by name."""
    if name not in PROFILE_MAP:
        raise ValueError(f"Unknown platform profile: '{name}'. Available: {list(PROFILE_MAP.keys())}")
    return PROFILE_MAP[name]()
