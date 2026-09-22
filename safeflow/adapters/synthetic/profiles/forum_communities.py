"""Forum Communities platform profile (Reddit-like topology and behavior)."""

from __future__ import annotations

import random
from safeflow.adapters.synthetic.profiles.base import BasePlatformProfile
from safeflow.core.schema import AudienceContext, ContentKind, SpaceKind

FORUM_COMMUNITIES = [
    ("r/AskDiscussion", AudienceContext.GENERAL),
    ("r/TeenHangoutZone", AudienceContext.YOUTH_ORIENTED),
    ("r/GamingBattlestations", AudienceContext.GENERAL),
    ("r/ScienceAndTechToday", AudienceContext.GENERAL),
    ("r/LifeAdviceAndTips", AudienceContext.MIXED),
    ("r/LateNightUnfiltered", AudienceContext.ADULT_ONLY),
    ("r/CryptoInvestingAlpha", AudienceContext.GENERAL),
    ("r/AnimeAndMangaFans", AudienceContext.MIXED),
    ("r/FitnessTransformation", AudienceContext.GENERAL),
    ("r/MemesAndHumorDaily", AudienceContext.MIXED),
]

BENIGN_TEMPLATES_A = [
    "OP, have you tried checking the system logs? That usually solves it.",
    "Completely agree with top comment. Experienced the exact same issue last month.",
    "Thanks for posting this write-up, very helpful for beginners in this sub.",
    "Upvoted for visibility. Hope someone from the dev team responds.",
    "I'd recommend reading the documentation linked in the sidebar before attempting.",
    "Underrated post. Deserves way more upvotes than the current frontpage meme.",
    "Could you provide a source or link for that claim in paragraph 2?",
    "Nice build! What are the exact specs of your cooling unit?",
]

BENIGN_TEMPLATES_B = [
    "Great discussion topic, OP. Really enjoyed reading everyone's input here.",
    "Seconding this advice. Tried it yesterday and worked flawlessly.",
    "This should honestly be added to the community FAQ/wiki.",
    "Interesting take, but isn't there an alternative approach with lower latency?",
    "Quality contribution to the subreddit. Thanks for sharing your workflow!",
    "Came here from the front page, was not disappointed at all.",
]

SPAM_TEMPLATES = [
    "Free gift card codes working right now! Check my profile bio to grab yours!",
    "Are you single? Naughty local girls are waiting on the link in my profile!",
    "Guaranteed 10x crypto returns with this bot, check the url on my bio banner!",
    "Leaked onlyfans mega link updated for today, visit my profile page to download!",
]

FANDOM_TEMPLATES = [
    "VOTE FOR {topic} ON THE MAIN POLL! Links in the megathread!",
    "Can't believe we just won the community award for {topic}!",
    "All hands on deck! Upvote every {topic} thread today to take over r/all!",
    "{topic} fandom is undefeated! Post your favorite moments below!",
]


class ForumCommunitiesProfile(BasePlatformProfile):
    """Reddit-like forum community platform profile."""

    @property
    def platform_id(self) -> str:
        return "forum_communities"

    @property
    def primary_space_kind(self) -> SpaceKind:
        return SpaceKind.THREAD

    @property
    def container_space_kind(self) -> SpaceKind:
        return SpaceKind.COMMUNITY

    @property
    def content_kind(self) -> ContentKind:
        return ContentKind.POST

    def sample_space_names(self, count: int, rng: random.Random) -> list[tuple[str, str, AudienceContext]]:
        results = []
        for _ in range(count):
            sub_name, audience = rng.choice(FORUM_COMMUNITIES)
            thread_title = f"[{sub_name}] {rng.choice(['Discussion:', 'Help Needed:', 'PSA:', 'Guide:', 'Question:'])} {rng.choice(['Best practices in 2026', 'How to get started', 'My detailed review', 'What is your opinion on this?', 'Monthly Megathread'])}"
            results.append((sub_name, thread_title, audience))
        return results

    def sample_benign_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        templates = BENIGN_TEMPLATES_A if variant == "A" else BENIGN_TEMPLATES_B
        return [rng.choice(templates) for _ in range(count)]

    def sample_spam_comments(self, count: int, rng: random.Random, variant: str = "A") -> list[str]:
        return [rng.choice(SPAM_TEMPLATES) for _ in range(count)]

    def sample_fandom_comments(self, count: int, rng: random.Random, topic: str) -> list[str]:
        return [rng.choice(FANDOM_TEMPLATES).format(topic=topic) for _ in range(count)]

    def get_timing_delta_seconds(self, is_attack: bool, rng: random.Random, variant: str = "A") -> float:
        if is_attack:
            return rng.uniform(10.0, 75.0) if variant == "A" else rng.uniform(15.0, 90.0)
        else:
            return rng.expovariate(1.0 / 7200.0)
