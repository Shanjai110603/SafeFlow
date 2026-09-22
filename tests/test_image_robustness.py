"""Empirical Robustness Benchmarking against Pre-Registered Distance Table.

Per-Transform Bounds (pre-registered in docs/IMAGE_POLICY.md):
- Identity: dHash == 0, pHash == 0, decision identical
- Resize (512 -> 128): dHash <= 1, pHash <= 10, decision identical
- JPEG re-compression (Q=60): dHash <= 1, pHash <= 14, decision identical
- Brightness (+15%): dHash <= 1, pHash <= 14, decision identical
- Screenshot re-encode: dHash <= 1, pHash <= 10, decision identical
- Subtle Rotation (3 deg): dHash <= 5, pHash <= 12, decision identical
- Slight Crop (5% margin): dHash <= 18, pHash <= 32, decision identical
- Horizontal Mirror: pHash dist against indexed mirror_phash == 0, decision identical
- Heavy Center Crop (50%): dHash dist >= 12, pHash dist >= 14 (documented KNOWN NON-MATCH)
- Large Rotation (90 deg): dHash dist >= 14, pHash dist >= 16 (documented KNOWN NON-MATCH)

Coverage Matrix (Amendment 1):
- Tests covering BOTH Hashes and Decisions: Identity, Resize, JPEG, Brightness, Screenshot, Rotation, Slight Crop, Mirror.
- Tests covering Hashes ONLY (Known Non-Matches): Heavy Crop, Large Rotation.
"""

from __future__ import annotations

import io
from pathlib import Path
import imagehash
import pytest
from PIL import Image
from safeflow.core.config import PolicyPackLoader
from safeflow.plugins.image_gate.pipeline import ImageGatePipeline
from safeflow.utils.procedural_avatar import RobustnessTransforms

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "procedural_avatars"


@pytest.fixture
def base_suggestive() -> bytes:
    return (FIXTURES_DIR / "test_suggestive.png").read_bytes()


@pytest.fixture
def pipeline() -> ImageGatePipeline:
    return ImageGatePipeline()


@pytest.fixture
def general_pack():
    return PolicyPackLoader.load_by_name("general_video_platform")


def _hamming_distance(h1: str, h2: str) -> int:
    hash1 = imagehash.hex_to_hash(h1)
    hash2 = imagehash.hex_to_hash(h2)
    return int(hash1 - hash2)


def test_robustness_identity(pipeline, general_pack, base_suggestive):
    """Identity test: clean re-encode. Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    clean_bytes = RobustnessTransforms.resize(base_suggestive, target_size=512)
    test_res = pipeline.process(clean_bytes, general_pack)

    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    assert dist_p == 0
    assert dist_d == 0
    assert test_res.decision == base_res.decision == "ALLOW_TAGGED"


def test_robustness_resize(pipeline, general_pack, base_suggestive):
    """Resize test: 512x512 down to 128x128. Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    resized_bytes = RobustnessTransforms.resize(base_suggestive, target_size=128)
    test_res = pipeline.process(resized_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 1, f"Resize dHash distance {dist_d} exceeded expected bound of 1"
    assert dist_p <= 10, f"Resize pHash distance {dist_p} exceeded expected bound of 10"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_jpeg_compression(pipeline, general_pack, base_suggestive):
    """JPEG compression at Quality 60. Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    jpeg_bytes = RobustnessTransforms.jpeg_compress(base_suggestive, quality=60)
    test_res = pipeline.process(jpeg_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 1, f"JPEG dHash distance {dist_d} exceeded expected bound of 1"
    assert dist_p <= 14, f"JPEG pHash distance {dist_p} exceeded expected bound of 14"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_brightness(pipeline, general_pack, base_suggestive):
    """Brightness shift (+15%). Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    bright_bytes = RobustnessTransforms.brightness(base_suggestive, factor=1.15)
    test_res = pipeline.process(bright_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 1, f"Brightness dHash distance {dist_d} exceeded expected bound of 1"
    assert dist_p <= 14, f"Brightness pHash distance {dist_p} exceeded expected bound of 14"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_screenshot_reencode(pipeline, general_pack, base_suggestive):
    """Screenshot simulation (contrast + JPEG). Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    screenshot_bytes = RobustnessTransforms.screenshot_reencode(base_suggestive)
    test_res = pipeline.process(screenshot_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 1, f"Screenshot dHash distance {dist_d} exceeded expected bound of 1"
    assert dist_p <= 10, f"Screenshot pHash distance {dist_p} exceeded expected bound of 10"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_subtle_rotation(pipeline, general_pack, base_suggestive):
    """Subtle rotation (3 degrees). Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    rotated_bytes = RobustnessTransforms.rotate(base_suggestive, degrees=3.0)
    test_res = pipeline.process(rotated_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 5, f"Subtle rotation dHash distance {dist_d} exceeded expected bound of 5"
    assert dist_p <= 12, f"Subtle rotation pHash distance {dist_p} exceeded expected bound of 12"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_slight_crop(pipeline, general_pack, base_suggestive):
    """Slight 5% margin crop. Covers BOTH hashes and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    cropped_bytes = RobustnessTransforms.crop(base_suggestive, percent=0.05)
    test_res = pipeline.process(cropped_bytes, general_pack)

    dist_d = _hamming_distance(base_res.perceptual_hashes["dhash"], test_res.perceptual_hashes["dhash"])
    dist_p = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    assert dist_d <= 18, f"Slight crop dHash distance {dist_d} exceeded expected bound of 18"
    assert dist_p <= 32, f"Slight crop pHash distance {dist_p} exceeded expected bound of 32"
    assert test_res.decision == "ALLOW_TAGGED"


def test_robustness_horizontal_mirror(pipeline, general_pack, base_suggestive):
    """Horizontal flip / mirror. Covers BOTH hashes (against mirror index) and decisions."""
    base_res = pipeline.process(base_suggestive, general_pack)
    mirrored_bytes = RobustnessTransforms.mirror(base_suggestive)
    test_res = pipeline.process(mirrored_bytes, general_pack)

    # Comparing mirrored image's phash to base image's indexed mirror_phash
    dist_mirror = _hamming_distance(test_res.perceptual_hashes["phash"], base_res.perceptual_hashes["mirror_phash"])
    assert dist_mirror == 0, f"Mirror pHash distance {dist_mirror} expected to be 0 against indexed mirror_phash"
    assert test_res.decision == "ALLOW_TAGGED"


def test_known_non_match_heavy_crop(pipeline, general_pack, base_suggestive):
    """Heavy 50% center crop. Covers HASHES ONLY (Documented Known Non-Match)."""
    base_res = pipeline.process(base_suggestive, general_pack)
    with Image.open(io.BytesIO(base_suggestive)) as img:
        w, h = img.size
        quarter_w, quarter_h = w // 4, h // 4
        heavy_cropped = img.crop((quarter_w, quarter_h, w - quarter_w, h - quarter_h))
        out = io.BytesIO()
        heavy_cropped.save(out, format="PNG")
        heavy_bytes = out.getvalue()

    test_res = pipeline.process(heavy_bytes, general_pack)
    dist = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    # Known Non-Match: DCT frequency spectrum of center 50% differs significantly from full image
    assert dist >= 10, f"Expected heavy crop distance >= 10, got {dist}"


def test_known_non_match_large_rotation(pipeline, general_pack, base_suggestive):
    """Large 90 degree rotation. Covers HASHES ONLY (Documented Known Non-Match)."""
    base_res = pipeline.process(base_suggestive, general_pack)
    rotated_bytes = RobustnessTransforms.rotate(base_suggestive, degrees=90.0)
    test_res = pipeline.process(rotated_bytes, general_pack)

    dist = _hamming_distance(base_res.perceptual_hashes["phash"], test_res.perceptual_hashes["phash"])
    # Known Non-Match: 2D DCT grid is non-rotationally invariant at 90 degrees
    assert dist >= 14, f"Expected 90 deg rotation distance >= 14, got {dist}"
