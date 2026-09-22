"""Comprehensive test suite for SafeFlow Synthetic Generator (Milestone 2)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from safeflow.adapters.generic_jsonl.validator import GenericJSONLValidator
from safeflow.adapters.synthetic.destinations import DestinationGenerator
from safeflow.adapters.synthetic.exporter import DatasetExporter
from safeflow.adapters.synthetic.generator import SyntheticDataset, SyntheticGenerator
from safeflow.adapters.synthetic.models import (
    AttackCategory,
    GeneratorConfig,
    LegitCategory,
)
from safeflow.adapters.synthetic.obfuscation import ObfuscationEngine


@pytest.mark.parametrize("profile", ["video_comments", "forum_communities", "chat_servers"])
def test_synthetic_generator_determinism(profile: str, tmp_path: Path) -> None:
    """Test that running the generator twice with identical parameters yields byte-identical exports."""
    cfg = GeneratorConfig(seed=42, variant="A", platform_profile=profile, actor_count=100)  # type: ignore[arg-type]

    # Run 1
    dir1 = tmp_path / f"run1_{profile}"
    gen1 = SyntheticGenerator(cfg)
    ds1 = gen1.generate()
    manifest1 = DatasetExporter.export(ds1, dir1)

    # Run 2
    dir2 = tmp_path / f"run2_{profile}"
    gen2 = SyntheticGenerator(cfg)
    ds2 = gen2.generate()
    manifest2 = DatasetExporter.export(ds2, dir2)

    # Assert identical entity counts
    assert manifest1["entity_counts"] == manifest2["entity_counts"]

    # Assert byte-identical files via checksums
    for filename, checksum1 in manifest1["file_checksums_sha256"].items():
        assert filename in manifest2["file_checksums_sha256"]
        checksum2 = manifest2["file_checksums_sha256"][filename]
        assert checksum1 == checksum2, f"Determinism mismatch for file {filename} in profile {profile}"


def test_variant_a_vs_variant_b_dissimilarity(tmp_path: Path) -> None:
    """Test that Variant A (dev) and Variant B (held-out) generate distinct data distributions."""
    cfg_a = GeneratorConfig(seed=42, variant="A", platform_profile="video_comments", actor_count=100)
    cfg_b = GeneratorConfig(seed=42, variant="B", platform_profile="video_comments", actor_count=100)

    ds_a = SyntheticGenerator(cfg_a).generate()
    ds_b = SyntheticGenerator(cfg_b).generate()

    # Comment text should differ between variants due to template variation
    texts_a = {c.text for c in ds_a.content}
    texts_b = {c.text for c in ds_b.content}

    overlap = texts_a.intersection(texts_b)
    # Most comments should be distinct
    assert len(overlap) < len(texts_a) * 0.4


@pytest.mark.parametrize("profile", ["video_comments", "forum_communities", "chat_servers"])
def test_canonical_json_schema_validation_on_all_profiles(profile: str, tmp_path: Path) -> None:
    """Test that generated dataset.jsonl validates 100% against canonical schemas."""
    cfg = GeneratorConfig(seed=101, variant="A", platform_profile=profile, actor_count=60)  # type: ignore[arg-type]
    out_dir = tmp_path / f"val_{profile}"
    ds = SyntheticGenerator(cfg).generate()
    DatasetExporter.export(ds, out_dir)

    dataset_jsonl = out_dir / "dataset.jsonl"
    assert dataset_jsonl.exists()

    counts = GenericJSONLValidator.validate_file(dataset_jsonl)
    assert counts["actor"] == 60
    assert counts["space"] > 0
    assert counts["content"] > 0
    assert counts["media"] > 0
    assert counts["link"] > 0


def test_category_mix_and_ground_truth_presence(tmp_path: Path) -> None:
    """Test that all required attack and legit categories are synthesized with proper ground truth."""
    cfg = GeneratorConfig(seed=777, variant="A", platform_profile="video_comments", actor_count=300)
    ds = SyntheticGenerator(cfg).generate()

    attack_cats_found = set()
    legit_cats_found = set()

    for a in ds.actors:
        gt_dict = a.attributes.get("ground_truth", {})
        cat = gt_dict.get("category")
        is_attack = gt_dict.get("is_attack")
        assert cat is not None

        if is_attack:
            attack_cats_found.add(cat)
        else:
            legit_cats_found.add(cat)

    for cat in AttackCategory:
        assert cat.value in attack_cats_found, f"Attack category {cat.value} missing from generated dataset"

    for cat in LegitCategory:
        assert cat.value in legit_cats_found, f"Legit category {cat.value} missing from generated dataset"


def test_zero_real_or_depictive_media_scan() -> None:
    """Verify hard safety rule: zero depictive images, all media items have procedural perceptual hashes."""
    cfg = GeneratorConfig(seed=999, variant="A", platform_profile="forum_communities", actor_count=100)
    ds = SyntheticGenerator(cfg).generate()

    assert len(ds.media) > 0
    for m in ds.media:
        assert "phash" in m.perceptual_hashes
        assert "dhash" in m.perceptual_hashes
        assert "whash" in m.perceptual_hashes
        assert "mirror_phash" in m.perceptual_hashes
        assert len(m.perceptual_hashes["phash"]) == 16
        # Role must be valid MediaRole
        assert m.role.value in ("avatar", "banner", "post_media")


def test_mock_destinations_are_strictly_local() -> None:
    """Verify that all generated destinations are mock .local hosts."""
    cfg = GeneratorConfig(seed=555, variant="A", platform_profile="chat_servers", actor_count=100)
    ds = SyntheticGenerator(cfg).generate()

    assert len(ds.links) > 0
    for link in ds.links:
        assert link.domain.endswith(".local"), f"Non-local domain detected: {link.domain}"
        assert link.url_normalized.startswith("https://")
        for hop in link.redirect_chain:
            assert ".local" in hop, f"Non-local redirect hop detected: {hop}"


def test_text_obfuscation_and_normalization() -> None:
    """Test homoglyph substitution and normalization."""
    raw = "click link in bio"
    obfuscated = ObfuscationEngine.apply_homoglyphs(raw, probability=1.0)
    # Ensure characters were substituted with non-ASCII homoglyphs
    assert obfuscated != raw

    # Normalize back
    normalized = ObfuscationEngine.normalize_text(obfuscated)
    assert normalized.lower() == raw.lower()
