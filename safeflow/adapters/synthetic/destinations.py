"""Synthetic target destination generator."""

from __future__ import annotations

import random
from safeflow.adapters.synthetic.models import MockDestination

MOCK_ATTACK_DOMAINS = [
    "spicy-dating-club.local",
    "private-cams-live.local",
    "exclusive-leaked-hub.local",
    "naughty-singles-chat.local",
    "vip-adult-content.local",
    "crypto-giveaway-claim.local",
    "free-giftcards-instant.local",
]

MOCK_BENIGN_DOMAINS = [
    "creator-merch-store.local",
    "my-design-portfolio.local",
    "personal-tech-blog.local",
    "github-project-repo.local",
    "community-newsletter.local",
    "podcasts-and-audio.local",
]

MOCK_SHORTENERS = [
    "short.local",
    "tiny.local",
    "lnk.local",
    "bio.local",
]


class DestinationGenerator:
    """Generates synthetic .local destinations with realistic redirect chains."""

    @classmethod
    def generate_attack_destination(
        cls,
        category: str = "adult_dating",
        uses_shortener: bool = True,
        cloaking: bool = False,
        activation_delay_hours: float = 0.0,
        known_bad: bool = False,
        rng: random.Random | None = None
    ) -> MockDestination:
        r = rng or random.Random()
        target_domain = r.choice(MOCK_ATTACK_DOMAINS)
        slug = f"ref_{r.randint(1000, 9999)}"
        final_url = f"https://{target_domain}/{slug}"

        redirect_chain: list[str] = []
        if uses_shortener:
            shortener = r.choice(MOCK_SHORTENERS)
            short_id = f"s{r.randint(100, 999)}"
            redirect_chain.append(f"https://{shortener}/{short_id}")
            if r.random() < 0.4:
                # Add intermediate hub page
                hub_domain = f"hub-{r.randint(1, 5)}.local"
                redirect_chain.append(f"https://{hub_domain}/profile/{slug}")

        initial_url = redirect_chain[0] if redirect_chain else final_url

        return MockDestination(
            url=initial_url,
            domain=target_domain,
            category=category,
            redirect_chain=redirect_chain + [final_url],
            uses_shortener=uses_shortener,
            cloaking=cloaking,
            activation_delay_hours=activation_delay_hours,
            known_bad=known_bad,
        )

    @classmethod
    def generate_benign_destination(
        cls,
        category: str = "portfolio",
        uses_shortener: bool = False,
        rng: random.Random | None = None
    ) -> MockDestination:
        r = rng or random.Random()
        target_domain = r.choice(MOCK_BENIGN_DOMAINS)
        slug = f"user_{r.randint(100, 999)}"
        url = f"https://{target_domain}/{slug}"

        redirect_chain: list[str] = [url]
        if uses_shortener:
            shortener = r.choice(MOCK_SHORTENERS)
            short_url = f"https://{shortener}/b{r.randint(100, 999)}"
            redirect_chain = [short_url, url]
            url = short_url

        return MockDestination(
            url=url,
            domain=target_domain,
            category=category,
            redirect_chain=redirect_chain,
            uses_shortener=uses_shortener,
            cloaking=False,
            activation_delay_hours=0.0,
            known_bad=False,
        )
