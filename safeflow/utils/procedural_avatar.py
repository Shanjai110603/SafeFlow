"""Procedural Avatar Generator and Robustness Utilities.

Features:
- STRICT ZERO-HARM: Generates purely geometric, abstract patterns (shapes, gradients, rings, initials).
  Zero depictive, explicit, or real human imagery is ever generated.
- Embeds ground-truth labels in pre-strip PNG metadata (safeflow_ground_truth).
- Embeds non-depictive pixel markers at defined regions (perimeter corners vs center)
  so scores can differ between full image and circular display crop and survive JPEG/resize/mirror.
- Transformation utilities for empirical robustness evaluation.
"""

from __future__ import annotations

import io
import math
from typing import Literal
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, PngImagePlugin

GroundTruthLabel = Literal["NEUTRAL", "SUGGESTIVE", "NUDITY", "EXPLICIT", "AMBIGUOUS"]

# Color signatures for non-depictive pixel markers (tolerates JPEG compression artifacts)
MARKER_SIGNATURES: dict[str, tuple[int, int, int]] = {
    "EXPLICIT": (245, 15, 15),     # Near-red
    "NUDITY": (245, 20, 140),      # Near-magenta
    "SUGGESTIVE": (245, 130, 20),   # Near-orange
    "AMBIGUOUS": (130, 20, 245),    # Near-purple
    "NEUTRAL": (20, 180, 245),      # Near-cyan
}


def _is_marker_match(rgb: tuple[int, int, int], target: tuple[int, int, int], tolerance: int = 35) -> bool:
    """Check if a sampled pixel matches a marker signature within JPEG tolerance."""
    return (
        abs(rgb[0] - target[0]) <= tolerance
        and abs(rgb[1] - target[1]) <= tolerance
        and abs(rgb[2] - target[2]) <= tolerance
    )


class ProceduralAvatarGenerator:
    """Generates synthetic, mathematically structured avatars with metadata and pixel markers."""

    @classmethod
    def generate(
        cls,
        label: GroundTruthLabel = "NEUTRAL",
        size: int = 512,
        pattern: str = "rings",
        crop_marker_label: GroundTruthLabel | None = None,
        perimeter_marker_label: GroundTruthLabel | None = None,
        initials: str = "SF",
        seed: int = 42
    ) -> bytes:
        """Create a procedural avatar and return PNG bytes with metadata and pixel markers."""
        img = Image.new("RGB", (size, size), color=(240, 242, 245))
        draw = ImageDraw.Draw(img)

        # Draw base geometric abstract background
        if pattern == "rings":
            center = size // 2
            for r in range(center, 10, -25):
                color = (
                    (seed * 37 + r * 3) % 256,
                    (seed * 59 + r * 5) % 256,
                    (seed * 71 + r * 7) % 256,
                )
                draw.ellipse([center - r, center - r, center + r, center + r], fill=color, outline=(255, 255, 255))
        elif pattern == "stripes":
            for x in range(0, size, 32):
                color = ((seed * 23 + x) % 256, (seed * 41 + x) % 256, 200)
                draw.rectangle([x, 0, x + 16, size], fill=color)
        elif pattern == "gradient":
            for y in range(size):
                r = int(100 + 155 * (y / size))
                g = int(120 + 100 * (math.sin(y / 20) + 1) / 2)
                b = (seed * 17) % 256
                draw.line([(0, y), (size, y)], fill=(r, g, b))
        else:  # checkerboard
            tile = size // 8
            for i in range(8):
                for j in range(8):
                    if (i + j) % 2 == 0:
                        draw.rectangle([i * tile, j * tile, (i + 1) * tile, (j + 1) * tile], fill=(220, 225, 230))

        # Central geometric shape representing initials/badge
        center = size // 2
        radius = size // 4
        draw.ellipse([center - radius, center - radius, center + radius, center + radius], fill=(255, 255, 255), outline=(180, 180, 180), width=3)
        # Draw abstract cross/monogram lines
        draw.line([center - radius // 2, center, center + radius // 2, center], fill=(80, 80, 80), width=4)
        draw.line([center, center - radius // 2, center, center + radius // 2], fill=(80, 80, 80), width=4)

        # Amendment 1: Pixel markers for dual-crop differentiation
        # Perimeter markers placed in the 4 corners (outside circular avatar crop)
        p_label = perimeter_marker_label or label
        if p_label in MARKER_SIGNATURES:
            color = MARKER_SIGNATURES[p_label]
            block = 16
            # Draw in corners
            draw.rectangle([8, 8, 8 + block, 8 + block], fill=color)
            draw.rectangle([size - 8 - block, 8, size - 8, 8 + block], fill=color)
            draw.rectangle([8, size - 8 - block, 8 + block, size - 8], fill=color)
            draw.rectangle([size - 8 - block, size - 8 - block, size - 8, size - 8], fill=color)

        # Center marker placed inside the circular avatar crop
        c_label = crop_marker_label or label
        if c_label in MARKER_SIGNATURES:
            color = MARKER_SIGNATURES[c_label]
            block = 12
            draw.rectangle([center - block // 2, center - block // 2, center + block // 2, center + block // 2], fill=color)

        # Embed pre-strip ground truth metadata
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("safeflow_ground_truth", label)
        if crop_marker_label:
            png_info.add_text("safeflow_crop_ground_truth", crop_marker_label)
        if perimeter_marker_label:
            png_info.add_text("safeflow_perimeter_ground_truth", perimeter_marker_label)

        out = io.BytesIO()
        img.save(out, format="PNG", pnginfo=png_info)
        return out.getvalue()

    @classmethod
    def detect_pixel_marker(
        cls,
        img: Image.Image,
        region: Literal["crop", "perimeter"]
    ) -> GroundTruthLabel | None:
        """Inspect geometric marker blocks to identify ground-truth label from pixels."""
        rgb_img = img.convert("RGB")
        w, h = rgb_img.size

        if region == "crop":
            # Sample center pixel block
            cx, cy = w // 2, h // 2
            pixel = rgb_img.getpixel((cx, cy))
            for lbl, target in MARKER_SIGNATURES.items():
                if _is_marker_match(pixel, target):  # type: ignore[arg-type]
                    return lbl  # type: ignore[return-value]
        else:
            # Sample top-left and top-right corner markers
            corners = [(12, 12), (w - 12, 12), (12, h - 12), (w - 12, h - 12)]
            for cx, cy in corners:
                if 0 <= cx < w and 0 <= cy < h:
                    pixel = rgb_img.getpixel((cx, cy))
                    for lbl, target in MARKER_SIGNATURES.items():
                        if _is_marker_match(pixel, target):  # type: ignore[arg-type]
                            return lbl  # type: ignore[return-value]

        return None


class RobustnessTransforms:
    """Applies standardized image transformations for empirical robustness benchmarking."""

    @staticmethod
    def crop(image_bytes: bytes, percent: float = 0.05) -> bytes:
        """Crop margins by percent (e.g. 0.05 for 5% crop)."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            dx = int(w * percent)
            dy = int(h * percent)
            cropped = img.crop((dx, dy, w - dx, h - dy))
            out = io.BytesIO()
            cropped.save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def resize(image_bytes: bytes, target_size: int = 128) -> bytes:
        """Resize image to target_size x target_size."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            resized = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            resized.save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def jpeg_compress(image_bytes: bytes, quality: int = 60) -> bytes:
        """Re-encode image as JPEG with specified quality factor."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb = img.convert("RGB")
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=quality)
            return out.getvalue()

    @staticmethod
    def brightness(image_bytes: bytes, factor: float = 1.15) -> bytes:
        """Adjust image brightness."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            enhancer = ImageEnhance.Brightness(img)
            enhanced = enhancer.enhance(factor)
            out = io.BytesIO()
            enhanced.save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def rotate(image_bytes: bytes, degrees: float = 3.0) -> bytes:
        """Apply planar rotation with edge expansion."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            rotated = img.rotate(degrees, expand=False, resample=Image.Resampling.BICUBIC)
            out = io.BytesIO()
            rotated.save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def mirror(image_bytes: bytes) -> bytes:
        """Horizontally flip (mirror) image."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            mirrored = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            out = io.BytesIO()
            mirrored.save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def screenshot_reencode(image_bytes: bytes) -> bytes:
        """Simulate screenshot re-encoding (slight compression + subtle color shift)."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb = img.convert("RGB")
            # Apply subtle contrast shift then re-encode JPEG 85
            contrasted = ImageEnhance.Contrast(rgb).enhance(1.03)
            out = io.BytesIO()
            contrasted.save(out, format="JPEG", quality=85)
            return out.getvalue()
