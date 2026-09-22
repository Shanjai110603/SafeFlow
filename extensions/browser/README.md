# SafeFlow Defensive Shield (Browser Extension)

A lightweight client-side defense prototype that warns users before navigating multi-hop redirection funnels and cloaked domains leading to age-inappropriate destinations.

---

## Installation (Developer Mode)

### Chrome / Brave / Edge
1. Navigate to `chrome://extensions/` (or `edge://extensions/`).
2. Toggle **Developer mode** on in the top-right corner.
3. Click **Load unpacked** and select this directory (`extensions/browser`).
4. The **SafeFlow Shield** icon will appear in your browser toolbar.

### Firefox
1. Navigate to `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...** and select `manifest.json`.

---

## Capabilities
- Intercepts live DOM links matching known cloaked redirection funnel patterns.
- Applies visual warning indicators to high-risk links.
- Emits confirmation dialogs before opening unverified external destinations.
- Connects automatically to local SafeFlow API (`http://127.0.0.1:8000/v1/health`) if running.
