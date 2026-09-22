"""Video Comments platform profile (YouTube-like topology and behavior)."""

from __future__ import annotations

import random
from safeflow.adapters.synthetic.profiles.base import BasePlatformProfile
from safeflow.core.schema import AudienceContext, ContentKind, SpaceKind

VIDEO_CONTAINERS = [
    ("TechReviewsHub", AudienceContext.GENERAL),
    ("MinecraftWorldKids", AudienceContext.YOUTH_ORIENTED),
    ("CosmicDocumentaries", AudienceContext.GENERAL),
    ("GamingHighlightsDaily", AudienceContext.MIXED),
    ("FitnessAndWorkouts", AudienceContext.GENERAL),
    ("Top10MusicHits", AudienceContext.GENERAL),
    ("AnimationShortsForKids", AudienceContext.YOUTH_ORIENTED),
    ("NightTalkPodcast", AudienceContext.ADULT_ONLY),
    ("DIYWoodworkingPro", AudienceContext.GENERAL),
    ("DailyVlogsWorld", AudienceContext.MIXED),
]

BENIGN_TEMPLATES_A = [
    "Great explanation at {ts}, helped me understand!",
    "I've been looking for a tutorial like this for weeks. Thank you!",
    "Who else is watching this in 2026? Subscribed!",
    "The quality of your editing has improved so much.",
    "Interesting perspective, although I do think step 3 is debatable.",
    "Can you do a follow-up video on this specific topic?",
    "Loved the soundtrack you used around the 4 minute mark.",
    "Such an underrated creator, hope this video blows up!",
    "Never realized how simple this was until you broke it down.",
    "That reaction at the end was absolutely hilarious!",
]

BENIGN_TEMPLATES_B = [
    "Truly informative breakdown. Appreciate the time put into this.",
    "Subscribed right away! Quality content right here.",
    "The audio mixing is so clean in this episode.",
    "Could you share the links or tools mentioned in the description?",
    "I was skeptical at first, but your reasoning makes total sense.",
    "Watching this while having my morning coffee, perfect start to the day.",
    "Been a fan since 2023, so proud of how far this channel has come.",
    "Keep up the awesome work, looking forward to next week's upload.",
]

SPAM_TEMPLATES = [
    "OMG I made $500 today using the strategy in my profile! Check it out!",
    "Hot girls in your area want to chat right now 👉 check my page!",
    "Exclusive private videos leaked on my channel description! Free access!",
    "Earn instant gift cards and crypto just by visiting my profile link!",
    "Special rewards for the first 50 people who click the bio link!",
]

FANDOM_TEMPLATES = [
    "STREAM {topic} NOW! We need to reach 10 million views today!",
    "Keep streaming {topic} guys! Don't let the charts drop!",
    "The bridge in {topic} literally gives me chills every single time.",
    "Best release of the year without a doubt! #Stream{topic}",
    "We are breaking all records today! Let's go team!",
]


class VideoCommentsProfile(BasePlatformProfile):
    """YouTube-like video platform profile."""

    @property
    def platform_id(self) -> str:
        return "video_comments"

    @property
    def primary_space_kind(self) -> SpaceKind:
        return SpaceKind.VIDEO

    @property
    def container_space_kind(self) -> SpaceKind:
        return SpaceKind.CHANNEL

    @property
    def content_kind(self) -> ContentKind:
        return ContentKind.COMMENT

    def sample_space_names(self, count: int, rng: random.Random) -> list[tuple[str, str, AudienceContext]]:
        results = []
        for i in range(count):
            channel_name, audience = rng.choice(VIDEO_CONTAINERS)
            video_title = f"{channel_name} - Episode #{rng.randint(10, 999)}: {rng.choice(['Review', 'Guide', 'Highlights', 'Live Stream', 'Special', 'Vlog', 'Q&A'])}"
            results.append((channel_name, video_title, audience))
        return results

    def sample_benign_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        templates = BENIGN_TEMPLATES_A if variant == "A" else BENIGN_TEMPLATES_B
        comments = []
        for _ in range(count):
            tmpl = rng.choice(templates)
            mins = rng.randint(0, 15)
            secs = rng.randint(10, 59)
            comments.append(tmpl.format(ts=f"{mins}:{secs:02d}"))
        return comments

    def sample_spam_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        return [rng.choice(SPAM_TEMPLATES) for _ in range(count)]

    def sample_fandom_comments(self, count: int, rng: random.Random, topic: str) -> list[str]:
        topic_clean = topic.replace(" ", "")
        return [rng.choice(FANDOM_TEMPLATES).format(topic=topic_clean) for _ in range(count)]

    def get_timing_delta_seconds(self, is_attack: bool, rng: random.Random, variant: str = "A") -> float:
        if is_attack:
            # Bursty attack pattern (e.g. 5 to 45 seconds between comments)
            return rng.uniform(5.0, 45.0) if variant == "A" else rng.uniform(8.0, 60.0)
        else:
            # Human organic inter-arrival (e.g. 2 minutes to 48 hours)
            return rng.expovariate(1.0 / 3600.0)
