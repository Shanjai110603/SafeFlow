# SafeFlow Threat Model

## 1. Scope & Adversary Characterization

SafeFlow models adversaries who attempt to funnel users from public platforms (video-sharing platforms, discussion forums, chat servers) toward external, age-inappropriate, exploitative, or scam destinations.

### Adversary Profiles:
1. **Automated Traffic Arbitrage / Spam Rings**:
   - High-volume bot networks utilizing scripted account creation, templated text, and mass commenting.
   - Low operational cost per account; relies on brute-force volume.
2. **Curiosity Funnel Operators**:
   - Advanced adversaries who deploy **completely benign, conversational comments** (e.g., "Great video!", "I totally agree with this point") on high-traffic spaces.
   - The comment itself contains zero spam keywords, URLs, or policy violations.
   - The attack vector resides on the **identity surface** (avatar presentation) and **secondary surfaces** (bio links).
3. **Decentralized Coordinated Networks**:
   - Operations that rotate across accounts, mutate avatars slightly (cropping, subtle noise, re-encoding), and share common external redirect infrastructure.
4. **Adaptive / Evasive Operators**:
   - Adversaries who monitor moderation rules and adapt: utilizing homoglyphs, zero-width characters, intermediate landing hubs, cloaked destinations, and dormant activation delays.

---

## 2. Multi-Hop Attack Vectors

Adversaries deliberately decouple the promotion vector into multiple hops across platform surfaces:

```
[ATTENTION SURFACE] ──────► [IDENTITY SURFACE] ──────► [SECONDARY SURFACE] ──────► [EXTERNAL DESTINATION]
 - Benign comments           - Suggestive avatar        - Intermediate bio links   - Cloaked .local host
 - Contextual chatter        - "Check my profile"       - Hub/linktree landing     - Activation delay
 - High-traffic spaces       - Obfuscated bio text      - Secondary channels       - Multi-hop redirects
```

### Hop Breakdown:
- **Hop 1: Attention to Identity**: An actor posts on a popular video/thread. The comment avoids lexical triggers, but the user clicks the profile due to an enticing avatar or name.
- **Hop 2: Identity to Secondary**: The profile bio contains an invitation ("Exclusive content at link below") obfuscated with homoglyphs or emojis.
- **Hop 3: Secondary to External**: The link routes through a URL shortener or multi-step redirect chain.
- **Hop 4: External Delivery**: The destination uses IP/user-agent cloaking to show an innocent page to automated scanners while serving age-inappropriate content to genuine users, or delays turning on explicit redirects until hours after posting.

---

## 3. Adversarial Adaptations & Evasion Techniques

| Evasion Strategy | Attacker Mechanism | SafeFlow Defensive Countermeasure |
|---|---|---|
| **Benign Comment Camouflage** | Posting normal or AI-generated positive chatter with zero spam keywords. | **Multi-signal correlation**: Text behavior alone does not decide risk; link, destination, and network graph signals expose the funnel. |
| **Perceptual Hash Perturbation** | Resizing, cropping, subtle rotation, JPEG re-compression, mirroring. | **Robust multi-algorithm perceptual hashing** (pHash, dHash, wHash) evaluated against Hamming distance thresholds; indexing of image mirrors. |
| **Popular Avatar Hijacking** | Using viral memes, anime defaults, or platform icons to hide in large clusters. | **Popularity Discounting (IDF)**: Highly frequent hashes receive discounted weight so legitimate avatar reuse does not inflate risk. |
| **Bio Obfuscation** | Homoglyph substitution (e.g., Cyrillic 'а', 'о'), zero-width spaces, emoji separation. | **Text normalization**: Canonical Unicode normalization (NFKC) and confusable mapping in profile analyzers. |
| **Cloaking & Delayed Activation** | Benign response to platform crawler IPs; explicit destination activated after $N$ hours. | **Risk-Adaptive Link Verification Queue**: Holding link publication for higher-risk accounts across configurable windows (5–120 min); re-scanning destinations. |
| **Dormant / Aged Accounts** | Sleeper accounts created months in advance or compromised legacy accounts. | **Temporal Trajectory Analysis**: Flagging sudden behavioral transitions from dormancy to high-frequency targeting. |
| **Domain Rotation & Shorteners** | Generating disposable short-links (`bit.ly`, `tinyurl`) to hide destination hosts. | **Redirect Chain Unraveling**: Following redirect chains to base canonical domains; tracking domain registration age and synthetic reputation. |

---

## 4. SafeFlow System Defenses & Invariants

To avoid becoming vulnerable to exploitation or weaponization, SafeFlow enforces core architectural invariants:

1. **Strict Signal-Family Gating**:
   - Elevated actor risk levels (**HIGH** and **CRITICAL**) require corroborating evidence from multiple independent signal families (e.g., `DESTINATION`, `NETWORK`, `BEHAVIOR`, `IMAGE_LINK`).
   - A single weak signal (e.g., `suggestive_presentation` tag or AI-likelihood score) **can never raise an actor above LOW risk**.
2. **Zero-Byte Blocked Image Persistence**:
   - Adversaries cannot use SafeFlow storage as an involuntary cache or hosting ground for prohibited material. Blocked uploads are purged immediately from memory after calculating perceptual hashes.
3. **Analyst-Only Explanations & Generic Role Redaction**:
   - Creators receive only generic statuses (`ACCEPTED`, `UNDER_REVIEW`, `REJECTED`). Exact scores, matched hashes, and model weights are strictly concealed to prevent black-box threshold probing.
4. **Non-Overridable Policy Invariants**:
   - Policy packs cannot disable hash checks, disable fail-closed error handling, or enable blocked image storage.

---

## 5. Deliberately Unpublished Elements & Operational Security

In production defensive research:
- **Uncalibrated Research Placeholders**: All thresholds shipped in open configurations (e.g., nudity threshold $0.85$, review band $0.50$, family gating counts) are documented research placeholders. Platforms deploying SafeFlow must tune these against their specific platform distributions.
- **Ensemble Combination Weights**: Shipped ensemble weights are representative baselines. In production, weights should remain confidential to the deploying platform to prevent adversarial gradient estimation.
