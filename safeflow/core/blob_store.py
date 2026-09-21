"""ReviewBlobStore: Secure, ephemeral storage for media pending human review.

Features:
- Encrypted storage (AES-GCM) with in-memory keying
- Server-side Gaussian blurred previews by default
- Automatic TTL purge based on review SLA
- Audit-logged unblurred reveals
- Per-analyst session reveal limits
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image, ImageFilter


class RevealCapExceededError(Exception):
    """Raised when an analyst session exceeds the maximum permitted unblurred reveals."""
    pass


class BlobEntry:
    def __init__(
        self,
        media_id: str,
        encrypted_bytes: bytes,
        nonce: bytes,
        blurred_bytes: bytes,
        created_at: datetime,
        expires_at: datetime
    ) -> None:
        self.media_id = media_id
        self.encrypted_bytes = bytearray(encrypted_bytes)
        self.nonce = nonce
        self.blurred_bytes = blurred_bytes
        self.created_at = created_at
        self.expires_at = expires_at

    def zero_out(self) -> None:
        """Overwrite encrypted bytes in memory."""
        for i in range(len(self.encrypted_bytes)):
            self.encrypted_bytes[i] = 0
        self.encrypted_bytes = bytearray()
        self.blurred_bytes = b""


class ReviewBlobStore:
    """Ephemeral, encrypted blob store for review queue items."""

    def __init__(self, session_reveal_cap: int = 50) -> None:
        self.session_reveal_cap = session_reveal_cap
        self._key = AESGCM.generate_key(bit_length=256)
        self._aesgcm = AESGCM(self._key)
        self._store: dict[str, BlobEntry] = {}
        # Tracks {session_id: count_of_reveals}
        self._session_reveals: dict[str, int] = {}

    def store(
        self,
        media_id: str,
        image_bytes: bytes,
        ttl_hours: int = 24
    ) -> None:
        """Encrypt and store an image with server-side blurred preview."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        # Generate server-side heavy blur preview
        blurred_bytes = self._generate_blurred_preview(image_bytes)

        # Encrypt raw image bytes with AES-GCM
        nonce = os.urandom(12)
        encrypted = self._aesgcm.encrypt(nonce, image_bytes, associated_data=media_id.encode("utf-8"))

        entry = BlobEntry(
            media_id=media_id,
            encrypted_bytes=encrypted,
            nonce=nonce,
            blurred_bytes=blurred_bytes,
            created_at=now,
            expires_at=expires_at
        )
        self._store[media_id] = entry

    def get_preview(self, media_id: str) -> bytes | None:
        """Return the safe server-side blurred thumbnail."""
        entry = self._store.get(media_id)
        if not entry:
            return None
        return entry.blurred_bytes

    def reveal(
        self,
        media_id: str,
        analyst_id: str,
        session_id: str,
        audit_logger: Any | None = None
    ) -> bytes:
        """Decrypt and return unblurred source image, subject to session cap and audit."""
        entry = self._store.get(media_id)
        if not entry:
            raise KeyError(f"Media '{media_id}' not found in review blob store.")

        current_reveals = self._session_reveals.get(session_id, 0)
        if current_reveals >= self.session_reveal_cap:
            raise RevealCapExceededError(
                f"Analyst session '{session_id}' reached the reveal cap of {self.session_reveal_cap}."
            )

        # Increment session count
        self._session_reveals[session_id] = current_reveals + 1

        # Audit log the reveal event
        if audit_logger is not None:
            audit_logger.log_analyst_reveal(
                analyst_id=analyst_id,
                media_id=media_id,
                session_id=session_id,
                reveal_count=self._session_reveals[session_id]
            )

        # Decrypt payload
        decrypted = self._aesgcm.decrypt(
            entry.nonce,
            bytes(entry.encrypted_bytes),
            associated_data=media_id.encode("utf-8")
        )
        return decrypted

    def get_session_reveal_count(self, session_id: str) -> int:
        return self._session_reveals.get(session_id, 0)

    def delete(self, media_id: str) -> bool:
        """Purge and zero-out a specific media blob."""
        entry = self._store.pop(media_id, None)
        if entry:
            entry.zero_out()
            return True
        return False

    def purge_expired(self, now: datetime | None = None) -> int:
        """Scan and securely purge all entries exceeding their review SLA."""
        current_time = now or datetime.now(timezone.utc)
        expired_ids = [
            mid for mid, entry in self._store.items()
            if current_time >= entry.expires_at
        ]
        for mid in expired_ids:
            entry = self._store.pop(mid)
            entry.zero_out()
        return len(expired_ids)

    def count(self) -> int:
        return len(self._store)

    @staticmethod
    def _generate_blurred_preview(image_bytes: bytes) -> bytes:
        """Create a heavily blurred preview image."""
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Convert to RGB if needed
                rgb_img = img.convert("RGB")
                # Resize down for safety & efficiency, blur, then export
                rgb_img.thumbnail((256, 256))
                blurred = rgb_img.filter(ImageFilter.GaussianBlur(radius=20))
                out = io.BytesIO()
                blurred.save(out, format="JPEG", quality=75)
                return out.getvalue()
        except Exception:
            # Fallback blank gray canvas if decode fails
            fallback = Image.new("RGB", (256, 256), color=(128, 128, 128))
            out = io.BytesIO()
            fallback.save(out, format="JPEG")
            return out.getvalue()
