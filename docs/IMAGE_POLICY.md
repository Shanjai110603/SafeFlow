# SafeFlow Profile Image Safety Policy

## 1. Scope & Purpose

The Profile Image Safety Gate acts as an upload-time filter and signal generator. It enforces visual safety on identity surfaces (avatars and profile banners), prevents explicit material from being published, holds ambiguous material for human review, and tags borderline suggestive presentations for downstream pathway correlation.

> [!NOTE]
> All numerical thresholds and multipliers documented herein are **uncalibrated research placeholders**. Deploying platforms must empirically calibrate these thresholds on platform-specific distributions.

---

## 2. Canonical Classification Classes & Actions

SafeFlow maps native classifier scores into five platform-neutral classes:

| Class | Definition | Standard Policy Action (`general_video_platform`) | Youth-Oriented Action (`youth_oriented_service`) |
|---|---|---|---|
| **`EXPLICIT`** | Sexual acts, extreme sexually explicit content, or explicit text overlays. | **`BLOCK`** | **`BLOCK`** |
| **`NUDITY`** | Exposed genitalia, buttocks, and (in profile `strict_avatar`) female nipples or sheer revealing garments. | **`BLOCK`** | **`BLOCK`** |
| **`SUGGESTIVE`** | Lingerie, swimwear, sexualized posture, heavy body emphasis without exposed anatomical nudity (`suggestive_presentation`). | **`ALLOW_TAGGED`** (published, internal tag recorded with TTL) | **`REVIEW`** (held for human review with blurred preview; in strict profile: **`BLOCK`**) |
| **`AMBIGUOUS`** | Classical art/sculpture, breastfeeding, medical imagery, heavy cropping, low-contrast skin-dominant textures. | **`REVIEW`** (default placeholder served; analyst triage) | **`REVIEW`** |
| **`NEUTRAL`** | Everyday benign avatars, objects, animals, landscapes, standard portraits. | **`ALLOW`** | **`ALLOW`** |

---

## 3. Decision Pipeline & Execution Flow

```
Upload Stream
     │
     ▼
[1. Validation & Hardening]
 - Check format (PNG, JPEG, WebP only; SVG rejected)
 - Enforce pixel cap (< 25 megapixels)
 - Read pre-strip metadata / markers (MockClassifier)
 - Apply EXIF orientation via ImageOps.exif_transpose
 - Strip all metadata & re-encode in-memory
     │
     ▼
[2. Known-Bad Hash Check]
 - Compare against simulated blocklist (e.g. mock CSAM/exploitative hashes)
 - If MATCH ──► Immediate BLOCK (zero byte persistence)
     │
     ▼
[3. Dual-Crop Classification]
 - Classify BOTH:
     (a) Full pre-processed image
     (b) Circular avatar display crop (centered or focal thumbnail)
 - Take MAXIMUM risk score: max(full_score, crop_score)
 - Record crop_used ("full" or "display_crop")
     │
     ▼
[4. Pluggable OCR Text Overlay Check]
 - Inspect image for sexually explicit text strings (stub in MVP)
 - If explicit text detected ──► BLOCK
     │
     ▼
[5. Policy Pack Evaluation]
 - Apply active policy pack thresholds and mapping rules
     │
     ├── BLOCK ────────► Zero bytes persisted; hash retained; creator receives REJECTED
     ├── REVIEW ───────► Store in ReviewBlobStore (encrypted/in-memory); default avatar served; analyst queue item
     ├── ALLOW_TAGGED ─► Compute perceptual hashes; store suggestive_presentation tag on image record with TTL
     └── ALLOW ────────► Compute perceptual hashes; publish image
     │
     ▼
[6. Tamper-Evident Audit Logging]
 - Append decision record with model version, active thresholds, and hash-chain link
```

---

## 4. Policy Pack Variations

### 1. `default_research` & `general_video_platform`
- `policy_profile`: `strict_avatar`
- `nudity_block_threshold`: $0.85$
- `nudity_review_threshold`: $0.50$
- `suggestive_tag_threshold`: $0.60$
- `suggestive_action`: `ALLOW_TAGGED`
- `review_behavior`: `HOLD_DEFAULT_AVATAR`
- `classifier_unavailable_action`: `HOLD_DEFAULT_AVATAR` (fail-closed)

### 2. `youth_oriented_service`
- `policy_profile`: `strict_avatar`
- `nudity_block_threshold`: $0.70$ (stricter)
- `nudity_review_threshold`: $0.35$ (stricter)
- `suggestive_tag_threshold`: $0.45$
- **`suggestive_action`: `REVIEW`** (suggestive presentation is held for human review instead of published)
- Non-negotiable: minors must not be exposed to provocative redirection avatars.

### 3. `adult_permitted_platform`
- Standard spaces permit adult media, but profile avatars visible across shared public spaces enforce:
  - `nudity_block_threshold`: $0.90$
  - `suggestive_action`: `ALLOW` (untagged) or `ALLOW_TAGGED`
  - Fundamental safety invariants (known-bad hashes, fail-closed) remain active.

---

## 5. Storage, Retention & Lifecycle Rules

1. **Blocked Images**: Image bytes are immediately purged from memory. Only the perceptual hash (pHash, dHash, wHash), decision outcome, classifier scores, model version, active thresholds, and timestamp are retained.
2. **Review Images**: Held in `ReviewBlobStore` (in-memory or AES-GCM encrypted).
   - Server-side Gaussian blurred thumbnail served to review queue.
   - Revealing unblurred source requires logged analyst action.
   - Max 50 reveals per analyst session.
   - Unreviewed items auto-purged after SLA expiration (`review_sla_hours: 24`).
3. **Internal Tags (`suggestive_presentation`)**:
   - Tag is bound to the **image media record**, never to the human actor or account profile.
   - Expiration via TTL (`tag_ttl_days: 30`); expired tags are automatically removed.
   - Accessible exclusively to `ANALYST` and `ADMIN` roles. Every inspection is logged in the audit trail.
4. **Rescan Lifecycle**:
   - Rescans are triggered when:
     1. Actor uploads a new avatar.
     2. Classifier model version increments (`model_version` bump).
     3. Periodic verification interval elapses (`rescan_interval_days: 30`).
   - Host platform fetches image bytes via `MediaFetcher` protocol; SafeFlow does not store permanent cached copies unless `cache_allowed_media: true`.
