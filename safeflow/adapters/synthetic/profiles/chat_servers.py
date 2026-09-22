"""Chat Servers platform profile (Discord-like topology and behavior)."""

from __future__ import annotations

import random
from safeflow.adapters.synthetic.profiles.base import BasePlatformProfile
from safeflow.core.schema import AudienceContext, ContentKind, SpaceKind

CHAT_SERVERS = [
    ("StudyAndHomeworkHangout", AudienceContext.YOUTH_ORIENTED),
    ("DevelopersGuildGlobal", AudienceContext.GENERAL),
    ("MinecraftAndRobloxPlayers", AudienceContext.YOUTH_ORIENTED),
    ("NightOwlChillLounge", AudienceContext.ADULT_ONLY),
    ("EsportsAndTournaments", AudienceContext.MIXED),
    ("MusicProductionCommunity", AudienceContext.GENERAL),
    ("CryptoTradersLounge", AudienceContext.GENERAL),
    ("AnimeWatchPartyClub", AudienceContext.MIXED),
]

CHANNEL_NAMES = [
    "#general-chat",
    "#bot-commands",
    "#media-and-memes",
    "#lounge-talk",
    "#announcements",
    "#introductions",
]

BENIGN_TEMPLATES_A = [
    "hey everyone! anyone online right now?",
    "gg on that last match, that clutch was crazy haha",
    "brb grabbing a snack",
    "can someone tag the mod team? question about role assignments",
    "check out the meme in media channel lol",
    "what time is the tournament starting today?",
    "yooo welcome to the server @newuser!",
    "pinging @here for anyone free to queue up",
]

BENIGN_TEMPLATES_B = [
    "hello folks! hope everyone is having a good week",
    "that game update broke so many mods rip",
    "thanks for the invite link @admin!",
    "anyone playing on the new server region tonight?",
    "awesome voice call earlier today, learned a lot",
]

SPAM_TEMPLATES = [
    "FREE DISCORD NITRO 3 MONTHS!! Click link in my bio before it expires!!",
    "Hey cute guy, DM me or check the link on my profile for spicy pics 💋",
    "Robux generator 2026 working no verification, visit url on my bio banner!",
    "Exclusive leak server invite link in my profile description, join now!!",
]

FANDOM_TEMPLATES = [
    "HYPEEEEE {topic} IS FINALLY LIVE EVERYONE JOIN THE STREAM!!",
    "SPAM THE CHAT WITH {topic} EMOJIS LETS GOOOOO",
    "100k viewers reached for {topic}! Keep going everyone!",
    "{topic} ON TOP NO COMPETITION!!",
]


class ChatServersProfile(BasePlatformProfile):
    """Discord-like chat server platform profile."""

    @property
    def platform_id(self) -> str:
        return "chat_servers"

    @property
    def primary_space_kind(self) -> SpaceKind:
        return SpaceKind.CHANNEL

    @property
    def container_space_kind(self) -> SpaceKind:
        return SpaceKind.SERVER

    @property
    def content_kind(self) -> ContentKind:
        return ContentKind.MESSAGE

    def sample_space_names(self, count: int, rng: random.Random) -> list[tuple[str, str, AudienceContext]]:
        results = []
        for _ in range(count):
            server_name, audience = rng.choice(CHAT_SERVERS)
            channel_name = f"{server_name} / {rng.choice(CHANNEL_NAMES)}"
            results.append((server_name, channel_name, audience))
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
            # Rapid micro-bursts in chat (0.5 to 10 seconds)
            return rng.uniform(0.5, 10.0) if variant == "A" else rng.uniform(1.0, 15.0)
        else:
            # Chat messages spaced between 10s and 30 minutes
            return rng.expovariate(1.0 / 300.0)
