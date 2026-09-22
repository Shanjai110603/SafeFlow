# SafeFlow Architectural & Ethical Limitations

**Document Version:** 1.0.0  
**Status:** Authoritative Guidance  

---

## 1. Mathematical & Algorithmic Bounds

### 1.1 Perceptual Hashing Sensitivity
Perceptual hash algorithms (pHash, dHash, wHash) compute low-frequency DCT and wavelet representations of image matrices. While highly effective against standard re-encoding perturbations, their mathematical bounds include:
- **Preserved Matches (Hamming $\le 12$)**: Clean re-encodes, scaling ($512\to 128$), JPEG compression (quality 60), brightness shift ($\pm 15\%$), screenshot noise, subtle rotation ($\le 3^\circ$).
- **Known Degradation Boundaries**:
  - **Heavy Center Crops ($>50\%$)**: Alters the spatial DCT block layout, producing Hamming distances $\ge 14$.
  - **Large Planar Rotations ($90^\circ, 180^\circ$)**: Inverts frequency gradients, producing Hamming distances $\ge 16$.
  - **Reflections / Flips**: Solved in SafeFlow via dual-indexing with `mirror_phash` (0-distance match against mirror index).

### 1.2 Multi-Signal Gating Tradeoffs
- **Single-Signal Protection**: SafeFlow strictly enforces that isolated suggestive presentation tags (`ALLOW_TAGGED`) or AI-likelihood scores cannot elevate actor risk above `LOW` without corroborating signals (e.g. bio callout, high repetition, or destination hops). While this eliminates false positive harm on compliant creators, an attacker who uses a suggestive avatar with zero bio links and unique comments will remain in the `LOW` risk tier.

---

## 2. Adversarial Adaptation & Evasion Vectors

### 2.1 Delayed-Activation Redirect Evasions
Attacker domains may point to an innocuous destination during registration and switch DNS/HTTP redirects to malicious landing pages $N$ hours later.
- **SafeFlow Mitigation**: The **Risk-Adaptive Link Verification Queue** (Milestone 7) holds high/critical-risk links for a configurable window ($T_{\text{window}} = 30\text{m} - 60\text{m}$) and executes dynamic re-scans before links appear on user feeds.

### 2.2 Text Polymorphism & Token Permutations
Attackers utilizing dynamic LLM paraphrasing can evade exact substring matching and reduce repetition rates.
- **SafeFlow Mitigation**: Multi-modal correlation across profile bio callouts, homoglyph density, targeting percentiles, and media perceptual hashes ensures resilience against pure text evasions.

---

## 3. Ethical Boundaries & Intended Posture

1. **Zero Real Likenesses**: SafeFlow benchmark generators strictly synthesize procedural, geometric avatars. No real human faces or scraped likenesses are ever used.
2. **No Biometric Age Estimation**: SafeFlow explicitly refuses facial age estimation due to inherent bias and ethical concerns. Audience context is evaluated via platform space metadata (e.g. channel category).
3. **No Commercial Platform Scraping**: SafeFlow is an independent research framework with zero live platform scraping or posting capabilities. All targets are simulated mock `.local` hostnames.
4. **Analyst Safety (Amendment 3/4)**: Investigation consoles serve server-side blurred previews by default and enforce a hard 10-reveal session quota to prevent vicarious trauma.
