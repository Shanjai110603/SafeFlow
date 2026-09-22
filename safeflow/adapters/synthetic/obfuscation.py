"""Text and link obfuscation generator and normalization utilities."""

from __future__ import annotations

import random
import unicodedata

HOMOGLYPH_MAP: dict[str, list[str]] = {
    "a": ["а", "а", "ạ", "α"],  # Cyrillic, Latin with dot, Greek
    "c": ["с", "ϲ", "ƈ"],
    "e": ["е", "ė", "ẹ", "ε"],
    "i": ["і", "í", "ï", "ι"],
    "j": ["ј"],
    "o": ["о", "ο", "օ", "0"],
    "p": ["р", "ρ"],
    "s": ["ѕ", "$", "5"],
    "x": ["х", "ҳ"],
    "y": ["у", "ý", "γ"],
    "v": ["ν", "v"],
    "k": ["к", "κ"],
    "n": ["п", "η"],
    "t": ["т", "+", "7"],
}

REVERSE_CONFUSABLE_MAP: dict[str, str] = {
    "а": "a", "ạ": "a", "α": "a",
    "с": "c", "ϲ": "c", "ς": "c", "ƈ": "c",
    "е": "e", "ė": "e", "ẹ": "e", "ε": "e",
    "і": "i", "í": "i", "ï": "i", "ι": "i",
    "ј": "j",
    "о": "o", "ο": "o", "օ": "o", "0": "o",
    "р": "p", "ρ": "p",
    "ѕ": "s", "$": "s", "5": "s", "σ": "s",
    "х": "x", "ҳ": "x",
    "у": "y", "ý": "y", "γ": "y",
    "ν": "v",
    "к": "k", "κ": "k",
    "п": "n", "η": "n",
    "т": "t", "+": "t", "7": "t",
}

EMOJI_SEPARATORS = ["🔥", "✨", "👉", "💖", "💋", "⭐", "🔞", "👇", "👀", "💎"]
ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]


class ObfuscationEngine:
    """Generates and normalizes adversarial text obfuscations."""

    @classmethod
    def apply_homoglyphs(cls, text: str, probability: float = 0.6, rng: random.Random | None = None) -> str:
        """Replace latin characters with homoglyphs with given probability."""
        r = rng or random.Random()
        chars = []
        for ch in text:
            lower = ch.lower()
            if lower in HOMOGLYPH_MAP and r.random() < probability:
                sub = r.choice(HOMOGLYPH_MAP[lower])
                chars.append(sub.upper() if ch.isupper() else sub)
            else:
                chars.append(ch)
        return "".join(chars)

    @classmethod
    def apply_emoji_spacing(cls, phrase: str, rng: random.Random | None = None) -> str:
        """Insert emojis or punctuation between words or letters (e.g. l.i.n.k 🔥 i.n 🔥 b.i.o)."""
        r = rng or random.Random()
        words = phrase.split()
        sep = r.choice(EMOJI_SEPARATORS)
        spaced_words = []
        for word in words:
            if r.random() < 0.5:
                # Delimit characters in word
                delimit = r.choice([".", "-", "_", " "])
                spaced_words.append(delimit.join(list(word)))
            else:
                spaced_words.append(word)
        return f" {sep} ".join(spaced_words)

    @classmethod
    def apply_zero_width_spaces(cls, text: str, rng: random.Random | None = None) -> str:
        """Insert invisible zero-width spaces to break lexical tokenizers."""
        r = rng or random.Random()
        chars = []
        for ch in text:
            chars.append(ch)
            if r.random() < 0.4:
                chars.append(r.choice(ZERO_WIDTH_CHARS))
        return "".join(chars)

    @classmethod
    def obfuscate_bio_prompt(cls, base_prompt: str, rng: random.Random | None = None) -> str:
        """Combine multiple obfuscation strategies for bio descriptions."""
        r = rng or random.Random()
        style = r.choice(["homoglyph", "emoji", "zero_width", "combined"])
        if style == "homoglyph":
            return cls.apply_homoglyphs(base_prompt, probability=0.7, rng=r)
        elif style == "emoji":
            return cls.apply_emoji_spacing(base_prompt, rng=r)
        elif style == "zero_width":
            return cls.apply_zero_width_spaces(base_prompt, rng=r)
        else:
            t = cls.apply_homoglyphs(base_prompt, probability=0.5, rng=r)
            t = cls.apply_emoji_spacing(t, rng=r)
            return cls.apply_zero_width_spaces(t, rng=r)

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Normalize obfuscated text into canonical ASCII/Latin string for detection."""
        # 1. Strip zero-width characters
        for zw in ZERO_WIDTH_CHARS:
            text = text.replace(zw, "")
        # 2. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)
        # 3. Confusable character replacement
        chars = []
        for ch in normalized:
            lower = ch.lower()
            if lower in REVERSE_CONFUSABLE_MAP:
                rep = REVERSE_CONFUSABLE_MAP[lower]
                chars.append(rep.upper() if ch.isupper() else rep)
            else:
                chars.append(ch)
        return "".join(chars)
