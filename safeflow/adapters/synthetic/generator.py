"""Master deterministic synthetic dataset generator for SafeFlow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import random
from typing import Any
import imagehash
from PIL import Image

from safeflow.adapters.synthetic.destinations import DestinationGenerator
from safeflow.adapters.synthetic.models import (
    AttackCategory,
    GeneratorConfig,
    GroundTruthMetadata,
    LegitCategory,
)
from safeflow.adapters.synthetic.obfuscation import ObfuscationEngine
from safeflow.adapters.synthetic.profiles import get_platform_profile
from safeflow.core.schema import (
    Actor,
    AudienceContext,
    Content,
    ContentKind,
    GateDecision,
    Link,
    LinkSurface,
    Media,
    MediaRole,
    MediaTag,
    PopularityMetric,
    Relation,
    RelationType,
    Space,
    SpaceKind,
)
from safeflow.utils.procedural_avatar import ProceduralAvatarGenerator, RobustnessTransforms


def _hash_id(raw_id: str, salt: str) -> str:
    """Generate deterministic pseudonymous identifier via salted HMAC-SHA256."""
    return hmac.new(salt.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


class SyntheticDataset:
    """Container holding synthesized canonical entities and ground truth."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.actors: list[Actor] = []
        self.spaces: list[Space] = []
        self.content: list[Content] = []
        self.media: list[Media] = []
        self.links: list[Link] = []
        self.relations: list[Relation] = []
        self.ground_truth: dict[str, GroundTruthMetadata] = {}  # keyed by actor_id


class SyntheticGenerator:
    """Deterministic generator for SafeFlow synthetic benchmarks."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.profile = get_platform_profile(config.platform_profile)
        self.rng = random.Random(config.seed)
        self.salt = config.hmac_salt

    def generate(self) -> SyntheticDataset:
        """Generate a complete synthetic dataset."""
        dataset = SyntheticDataset(self.config)

        # 1. Generate Spaces (Containers & Leaf spaces) with power-law popularity
        num_spaces = max(20, self.config.actor_count // 10)
        raw_space_samples = self.profile.sample_space_names(num_spaces, self.rng)

        container_ids: dict[str, str] = {}
        space_idx = 0
        for container_name, leaf_name, audience in raw_space_samples:
            space_idx += 1
            if container_name not in container_ids:
                c_id = f"space_cnt_{_hash_id(container_name, self.salt)}"
                container_ids[container_name] = c_id
                dataset.spaces.append(
                    Space(
                        space_id=c_id,
                        kind=self.profile.container_space_kind,
                        parent_space_id=None,
                        popularity=PopularityMetric(raw_count=self.rng.randint(1000, 100000), percentile=self.rng.uniform(70.0, 99.9)),
                        audience_context=audience,
                    )
                )

            # Leaf space with Zipfian popularity distribution
            rank = self.rng.randint(1, num_spaces)
            raw_views = int(1000000 / (rank ** 0.8)) + self.rng.randint(50, 5000)
            percentile = max(0.1, min(99.9, 100.0 - (rank / num_spaces * 100.0)))

            leaf_id = f"space_leaf_{_hash_id(f'{leaf_name}_{space_idx}', self.salt)}"
            dataset.spaces.append(
                Space(
                    space_id=leaf_id,
                    kind=self.profile.primary_space_kind,
                    parent_space_id=container_ids[container_name],
                    popularity=PopularityMetric(raw_count=raw_views, percentile=percentile),
                    audience_context=audience,
                )
            )

        leaf_spaces = [s for s in dataset.spaces if s.kind == self.profile.primary_space_kind]
        top_spaces = sorted(leaf_spaces, key=lambda s: s.popularity.percentile, reverse=True)[:max(3, len(leaf_spaces) // 5)]

        # 2. Allocate Actors across Categories
        total_actors = self.config.actor_count
        attack_categories = list(AttackCategory)
        legit_categories = list(LegitCategory)

        target_attack_count = max(len(attack_categories), int(total_actors * self.config.base_rate))
        attack_counts = {cat: 0 for cat in attack_categories}
        for i in range(target_attack_count):
            cat = attack_categories[i % len(attack_categories)]
            attack_counts[cat] += 1

        actual_attack_sum = sum(attack_counts.values())
        target_legit_count = max(len(legit_categories), total_actors - actual_attack_sum)
        legit_counts = {cat: 0 for cat in legit_categories}
        for i in range(target_legit_count):
            cat = legit_categories[i % len(legit_categories)]
            legit_counts[cat] += 1

        actor_idx = 0

        # Helper to create an avatar media record
        def make_avatar(
            a_id: str,
            label: str,
            pattern: str = "rings",
            crop_label: str | None = None,
            seed_offset: int = 0,
            transform_fn: Any = None,
            ai_likelihood: float = 0.05
        ) -> Media:
            raw_bytes = ProceduralAvatarGenerator.generate(
                label=label,  # type: ignore[arg-type]
                pattern=pattern,
                crop_marker_label=crop_label,  # type: ignore[arg-type]
                seed=self.config.seed + seed_offset
            )
            if transform_fn:
                raw_bytes = transform_fn(raw_bytes)

            with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                ph = str(imagehash.phash(pil_img))
                dh = str(imagehash.dhash(pil_img))
                wh = str(imagehash.whash(pil_img))
                mirrored = pil_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                mph = str(imagehash.phash(mirrored))

            m_id = f"media_{_hash_id(f'avatar_{a_id}_{seed_offset}', self.salt)}"
            gate_decision = GateDecision.ALLOW
            tags = []
            if label in ("EXPLICIT", "NUDITY"):
                gate_decision = GateDecision.BLOCK
            elif label == "SUGGESTIVE":
                gate_decision = GateDecision.ALLOW_TAGGED
                tags.append(MediaTag(name="suggestive_presentation", applied_at=self.config.start_time))
            elif label == "AMBIGUOUS":
                gate_decision = GateDecision.REVIEW

            m = Media(
                media_id=m_id,
                actor_id=a_id,
                role=MediaRole.AVATAR,
                perceptual_hashes={"phash": ph, "dhash": dh, "whash": wh, "mirror_phash": mph},
                gate_result=gate_decision,
                tags=tags,
                embedding_ref=f"emb_{ph[:8]}",
            )
            dataset.media.append(m)
            return m

        # --- A. SYNTHESIZE LEGITIMATE CATEGORIES ---
        content_counter = 0
        for cat in legit_categories:
            count = legit_counts[cat]
            fandom_topic = f"SuperBand_{self.rng.randint(1, 5)}"
            shared_meme_media = None

            for i in range(count):
                actor_idx += 1
                raw_name = f"user_legit_{cat.value.lower()}_{actor_idx}"
                a_id = f"act_{_hash_id(raw_name, self.salt)}"
                created_dt = self.config.start_time + timedelta(days=self.rng.uniform(0, 20))
                display_hash = hashlib.sha256(raw_name.encode()).hexdigest()[:12]

                gt = GroundTruthMetadata(category=cat.value, is_attack=False, notes=f"Legitimate {cat.value}")
                dataset.ground_truth[a_id] = gt

                desc_hist: list[str] = []

                # Category-specific legitimate behaviors
                if cat == LegitCategory.LEGIT_FANDOM:
                    avatar = make_avatar(a_id, "NEUTRAL", pattern="checkerboard", seed_offset=100 + (i % 3))
                    # Coordinated fandom comments on target top space
                    target_space = top_spaces[0]
                    comments = self.profile.sample_fandom_comments(self.rng.randint(3, 8), self.rng, topic=fandom_topic)
                    t_curr = created_dt
                    for c_text in comments:
                        content_counter += 1
                        t_curr += timedelta(seconds=self.rng.uniform(30.0, 300.0))
                        c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{t_curr.timestamp()}', self.salt)}"
                        dataset.content.append(Content(content_id=c_id, actor_id=a_id, space_id=target_space.space_id, kind=self.profile.content_kind, text=c_text, created_at=t_curr))

                elif cat == LegitCategory.LEGIT_AVATAR_REUSE:
                    # Shared viral meme avatar
                    if shared_meme_media is None:
                        shared_meme_media = make_avatar(a_id, "NEUTRAL", pattern="stripes", seed_offset=555)
                        avatar = shared_meme_media
                    else:
                        avatar = shared_meme_media
                    # Normal benign posting on random spaces
                    target_space = self.rng.choice(leaf_spaces)
                    comments = self.profile.sample_benign_comments(self.rng.randint(2, 5), self.rng, variant=self.config.variant)
                    for c_text in comments:
                        content_counter += 1
                        c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{c_text[:10]}', self.salt)}"
                        dataset.content.append(Content(content_id=c_id, actor_id=a_id, space_id=target_space.space_id, kind=self.profile.content_kind, text=c_text, created_at=created_dt))

                elif cat == LegitCategory.LEGIT_LINK_CREATOR:
                    avatar = make_avatar(a_id, "NEUTRAL", pattern="gradient", seed_offset=200 + i)
                    dest = DestinationGenerator.generate_benign_destination("portfolio", uses_shortener=self.rng.random() < 0.3, rng=self.rng)
                    l_id = f"lnk_{_hash_id(f'{a_id}_bio', self.salt)}"
                    dataset.links.append(Link(link_id=l_id, actor_id=a_id, surface=LinkSurface.PROFILE_DESCRIPTION, url_normalized=dest.url, domain=dest.domain, redirect_chain=dest.redirect_chain))
                    desc_hist = [f"Check my portfolio: {dest.url}"]

                elif cat == LegitCategory.LEGIT_SUGGESTIVE_AVATAR:
                    # Compliant suggestive avatar with NO funnel
                    avatar = make_avatar(a_id, "SUGGESTIVE", pattern="rings", seed_offset=300 + i)
                    comments = self.profile.sample_benign_comments(self.rng.randint(2, 4), self.rng, variant=self.config.variant)
                    target_space = self.rng.choice(leaf_spaces)
                    for c_text in comments:
                        content_counter += 1
                        c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{c_text[:10]}', self.salt)}"
                        dataset.content.append(Content(content_id=c_id, actor_id=a_id, space_id=target_space.space_id, kind=self.profile.content_kind, text=c_text, created_at=created_dt))
                    desc_hist = ["Cosplay creator and gaming enthusiast"]

                elif cat == LegitCategory.NORMAL_HIGH_ENGAGEMENT:
                    avatar = make_avatar(a_id, "NEUTRAL", pattern="rings", seed_offset=400 + i)
                    # Frequent comments across several top spaces
                    for _ in range(self.rng.randint(6, 12)):
                        content_counter += 1
                        sp = self.rng.choice(top_spaces)
                        c_text = self.profile.sample_benign_comments(1, self.rng, variant=self.config.variant)[0]
                        c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{self.rng.random()}', self.salt)}"
                        dataset.content.append(Content(content_id=c_id, actor_id=a_id, space_id=sp.space_id, kind=self.profile.content_kind, text=c_text, created_at=created_dt))

                else:  # NORMAL
                    avatar = make_avatar(a_id, "NEUTRAL", pattern="rings", seed_offset=500 + i)
                    sp = self.rng.choice(leaf_spaces)
                    comments = self.profile.sample_benign_comments(self.rng.randint(1, 3), self.rng, variant=self.config.variant)
                    for c_text in comments:
                        content_counter += 1
                        c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{self.rng.random()}', self.salt)}"
                        dataset.content.append(Content(content_id=c_id, actor_id=a_id, space_id=sp.space_id, kind=self.profile.content_kind, text=c_text, created_at=created_dt))

                dataset.actors.append(
                    Actor(
                        actor_id=a_id,
                        platform_id=self.config.platform_profile,
                        created_at=created_dt,
                        display_name_hash=display_hash,
                        description_history=desc_hist,
                        avatar_media_id=avatar.media_id,
                        attributes={
                            "ground_truth": gt.model_dump(),
                            "ai_likelihood": 0.05,
                        },
                    )
                )

        # --- B. SYNTHESIZE ATTACK CATEGORIES ---
        cluster_counter = 0
        for cat in attack_categories:
            count = attack_counts[cat]
            cluster_counter += 1
            cluster_id = f"cluster_{cat.value}_{cluster_counter}"
            shared_dest = DestinationGenerator.generate_attack_destination(
                uses_shortener=True,
                cloaking=(cat in (AttackCategory.MIXED_ATTACK, AttackCategory.CURIOSITY_FUNNEL)),
                activation_delay_hours=self.rng.choice([0.0, 2.0, 12.0]),
                known_bad=(cat == AttackCategory.LINK_ABUSE),
                rng=self.rng,
            )

            shared_avatar_base_seed = 1000 + cluster_counter * 50

            for i in range(count):
                actor_idx += 1
                raw_name = f"user_attack_{cat.value.lower()}_{actor_idx}"
                a_id = f"act_{_hash_id(raw_name, self.salt)}"
                display_hash = hashlib.sha256(raw_name.encode()).hexdigest()[:12]

                # Timing modeling
                if cat == AttackCategory.HIJACKED_ACCOUNT or cat == AttackCategory.AGED_ACCOUNT_ATTACK:
                    created_dt = self.config.start_time - timedelta(days=180 + self.rng.randint(1, 60))
                elif cat == AttackCategory.ACCOUNT_ROTATION:
                    # Staggered account creation
                    created_dt = self.config.start_time + timedelta(days=i * 2)
                else:
                    created_dt = self.config.start_time + timedelta(days=self.rng.uniform(15, 25))

                gt = GroundTruthMetadata(
                    category=cat.value,
                    is_attack=True,
                    cluster_id=cluster_id,
                    funnel_depth=2,
                    ai_likelihood_ground_truth=0.92 if cat == AttackCategory.AI_IMAGE_NETWORK else 0.05,
                    intended_destination=shared_dest.url,
                    notes=f"Simulated attack {cat.value}",
                )
                dataset.ground_truth[a_id] = gt

                # Avatar setup
                if cat == AttackCategory.IMAGE_REUSE_NETWORK:
                    # Mutated avatar variants (resize, crop, brightness, mirror)
                    transform_fn = self.rng.choice([
                        RobustnessTransforms.crop,
                        RobustnessTransforms.brightness,
                        RobustnessTransforms.resize,
                        RobustnessTransforms.mirror,
                        None
                    ])
                    avatar = make_avatar(a_id, "SUGGESTIVE", pattern="rings", seed_offset=shared_avatar_base_seed, transform_fn=transform_fn)
                elif cat == AttackCategory.AI_IMAGE_NETWORK:
                    avatar = make_avatar(a_id, "SUGGESTIVE", pattern="gradient", seed_offset=shared_avatar_base_seed + i, ai_likelihood=0.92)
                elif cat in (AttackCategory.CURIOSITY_FUNNEL, AttackCategory.MIXED_ATTACK):
                    avatar = make_avatar(a_id, "SUGGESTIVE", pattern="rings", seed_offset=shared_avatar_base_seed + i)
                else:
                    avatar = make_avatar(a_id, "NEUTRAL" if cat == AttackCategory.SPAM else "SUGGESTIVE", pattern="rings", seed_offset=shared_avatar_base_seed + i)

                # Link in bio
                bio_prompt = ObfuscationEngine.obfuscate_bio_prompt(f"Exclusive private content here {shared_dest.url}", rng=self.rng)
                l_id = f"lnk_{_hash_id(f'{a_id}_{shared_dest.url}', self.salt)}"
                dataset.links.append(
                    Link(
                        link_id=l_id,
                        actor_id=a_id,
                        surface=LinkSurface.PROFILE_DESCRIPTION,
                        url_normalized=shared_dest.url,
                        domain=shared_dest.domain,
                        redirect_chain=shared_dest.redirect_chain,
                    )
                )

                # Content Generation
                target_spaces = top_spaces if cat in (AttackCategory.CURIOSITY_FUNNEL, AttackCategory.SPAM, AttackCategory.MIXED_ATTACK) else [self.rng.choice(leaf_spaces)]

                if cat == AttackCategory.CURIOSITY_FUNNEL:
                    # Completely benign comments posted rapidly on high-traffic spaces
                    comments = self.profile.sample_benign_comments(self.rng.randint(3, 7), self.rng, variant=self.config.variant)
                elif cat == AttackCategory.SPAM:
                    comments = self.profile.sample_spam_comments(self.rng.randint(4, 9), self.rng, variant=self.config.variant)
                else:
                    comments = self.profile.sample_benign_comments(self.rng.randint(2, 5), self.rng, variant=self.config.variant)

                t_curr = self.config.start_time + timedelta(days=26)
                for c_text in comments:
                    content_counter += 1
                    t_delta = self.profile.get_timing_delta_seconds(is_attack=True, rng=self.rng, variant=self.config.variant)
                    t_curr += timedelta(seconds=t_delta)
                    c_id = f"cnt_{_hash_id(f'{a_id}_{content_counter}_{t_curr.timestamp()}', self.salt)}"
                    dataset.content.append(
                        Content(
                            content_id=c_id,
                            actor_id=a_id,
                            space_id=self.rng.choice(target_spaces).space_id,
                            kind=self.profile.content_kind,
                            text=c_text,
                            created_at=t_curr,
                        )
                    )

                dataset.actors.append(
                    Actor(
                        actor_id=a_id,
                        platform_id=self.config.platform_profile,
                        created_at=created_dt,
                        display_name_hash=display_hash,
                        description_history=[bio_prompt],
                        avatar_media_id=avatar.media_id,
                        attributes={
                            "ground_truth": gt.model_dump(),
                            "ai_likelihood": gt.ai_likelihood_ground_truth,
                        },
                    )
                )

        return dataset

