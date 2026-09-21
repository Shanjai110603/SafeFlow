# SafeFlow Project Status & Gate Verification Checklist

This living document tracks milestone completion, test results, and pre-registered gate verification outputs.

---

## Milestone Progress Summary

- [x] **Milestone 0: Foundations, Governance & Architecture** (Gate 0: PASSED)
- [ ] **Milestone 1: Core Skeleton & Profile Image Safety Gate** (Gate 1: PENDING EXECUTION)
- [ ] **Milestone 2: Synthetic Generator & Platform Profiles** (Gate 2: PENDING)
- [ ] **Milestone 3: Signal Plugins Suite** (Gate 3: PENDING)
- [ ] **Milestone 4: Graph & Clustering Engine** (Gate 4: PENDING)
- [ ] **Milestone 5: Explainable Decision Engine** (Gate 5: PENDING)
- [ ] **Milestone 6: Evaluation Framework & Ablations** (Gate 6: PENDING)
- [ ] **Milestone 7: Threat Simulation Lab & Link Verification Queue** (Gate 7: PENDING)
- [ ] **Milestone 8: REST API, SDK, Exporters & Dashboard** (Gate 8: PENDING)
- [ ] **Milestone 9: Privacy Controls, Reports & Packaging** (Gate 9: PENDING)

---

## Gate 1 Pre-Registered Specifications

### 1. Pre-Registered Expected CLI Outputs (Amendment 14)

Before running CLI verification commands, their exact expected behaviors and output structures are pre-registered below:

#### Command 1: Analyst Role on Suggestive Image under `general_video_platform`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role analyst
```
- **Pre-Registered Expected Output**:
  - `Decision`: `ALLOW_TAGGED`
  - `Action`: Image published, internal tag `suggestive_presentation` attached to media record with 30-day TTL.
  - `Visibility`: Analyst role displays full breakdown: `nudity_score` ~ 0.05, `suggestive_score` ~ 0.75, `crop_used`, `model_name="mock_classifier"`, `reasons=["elevated_suggestive_presentation"]`.

#### Command 2: Analyst Role on Suggestive Image under `youth_oriented_service`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack youth_oriented_service --role analyst
```
- **Pre-Registered Expected Output**:
  - `Decision`: `REVIEW`
  - `Action`: Default placeholder avatar served; image routed to `ReviewBlobStore` with server-side blur; analyst triage ticket created.
  - `Visibility`: Full analyst scores and policy reasoning displayed.

#### Command 3: Creator Role on Suggestive Image under `general_video_platform`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role creator
```
- **Pre-Registered Expected Output**:
  - `Status`: `ACCEPTED`
  - `Message`: "Your profile image has been approved and published."
  - `Redaction`: Zero internal scores, zero tags, zero model identifiers, zero reasons.

#### Command 4: Creator Role on Explicit Image under Any Pack
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_explicit.png --pack general_video_platform --role creator
```
- **Pre-Registered Expected Output**:
  - `Status`: `REJECTED`
  - `Message`: "The uploaded image does not meet community guidelines."
  - `Redaction`: Zero internal scores, zero tags; image bytes discarded immediately (zero persistence verified).

---

### 2. Pre-Registered Robustness & Hamming-Distance Table (Amendment 6)

Perceptual hash distances ($64$-bit pHash/dHash/wHash) evaluated against procedural test avatars:

| Transformation | Parameters | Target Hashes Evaluated | Expected Hamming Distance | Expected Gate Decision |
|---|---|---|---|---|
| **Identity** | None (clean re-encode) | pHash, dHash, wHash | $0$ | Identical to source |
| **Resize** | $512\times 512 \to 128\times 128$ | pHash, dHash | $\le 2$ | Identical to source |
| **JPEG Re-compression** | Quality factor $60$ | pHash, dHash | $\le 2$ | Identical to source |
| **Brightness Perturbation** | $\pm 15\%$ luminance shift | pHash, dHash | $\le 4$ | Identical to source |
| **Slight Crop / Padding** | $5\%$ margin crop | pHash | $\le 6$ | Identical to source |
| **Subtle Rotation** | $\le 3^\circ$ planar rotation | pHash | $\le 6$ | Identical to source |
| **Horizontal Mirror / Flip** | Left-Right reflection | Indexed mirror pHash | $0$ (against mirror hash) | Identical to source |
| **Heavy Center Crop (Non-Match)** | $50\%$ center crop | pHash | $\ge 14$ (Known non-match) | Evaluates center region only |
| **Large Rotation (Non-Match)** | $90^\circ$ rotation | pHash | $\ge 18$ (Known non-match) | Evaluates rotated geometry |

*Rule: Thresholds will NOT be relaxed or tuned to force arbitrary passes. Known non-matches (heavy crop, $90^\circ$ rotation) are documented as inherent mathematical properties of 2D DCT-based perceptual hashes.*

---

## Gate 1 Checklist

- [ ] Import-boundary test passes (`safeflow.core` imports zero plugins/adapters; plugins do not import each other).
- [ ] Procedural avatar generator produces valid geometric avatars with non-depictive pre-strip metadata and pixel markers.
- [ ] Zero blocked image persistence verified by canary byte scan across DB, temp files, and logs.
- [ ] Perceptual hashes calculated for BLOCK before discarding image bytes.
- [ ] Generic role redaction strips internal scores/tags for creator role.
- [ ] ReviewBlobStore encrypted in-memory storage, auto-purge TTL, server-side blur, and session reveal caps verified.
- [ ] Host-provided `MediaFetcher` protocol and `RescanRequest` events verified with fixture fetcher.
- [ ] Policy pack loader enforces non-overridable invariants and rejects adversarial packs.
- [ ] Dual-crop evaluation selects higher risk crop between full image and circular avatar crop.
- [ ] Tamper-evident audit log verifies hash-chain integrity.
- [ ] All pytest suites pass cleanly (`pytest -v`).
- [ ] `safeflow gate` CLI demonstrates pre-registered outputs.
- [ ] Commit milestone and stop for user review.
