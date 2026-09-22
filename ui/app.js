// SafeFlow Trust & Safety Analyst Investigation App

const MOCK_ALERTS = [
  {
    actor_id: "actor_7a8f9c2d1b",
    level: "CRITICAL",
    score: 91.5,
    families: ["IMAGE_LINK", "BEHAVIOR", "DESTINATION", "PROFILE_CHANGE"],
    recommendation: "Suspend actor account, invalidate active sessions, and block associated destination URLs",
    phash: "0xf4e2c1a89b03df12",
    whash: "0x88f00a1b77c2e944",
    tag: "suggestive_presentation (TTL: 28d)",
    crop: "Dual Crop (Circular avatar higher)",
    evidence: [
      "Shared perceptual hash with 14 other accounts across 3 spaces",
      "Text template repetition rate 95% with burst velocity 6.2 msgs/min",
      "Cloaked redirect chain to high-risk destination (*.local)",
      "Bio callout pattern encouraging off-platform redirection"
    ],
    counter_evidence: [
      "No mitigating counter-evidence identified across evaluated signals"
    ],
    cluster_nodes: [
      { id: "actor_7a8f9c2d1b", type: "actor", label: "Target" },
      { id: "media_avatar_01", type: "media", label: "pHash: 0xf4e2" },
      { id: "actor_ring_peer1", type: "actor", label: "Peer 1" },
      { id: "actor_ring_peer2", type: "actor", label: "Peer 2" },
      { id: "dom_dating_local", type: "domain", label: "target.local" }
    ]
  },
  {
    actor_id: "actor_3b11e04a99",
    level: "HIGH",
    score: 72.8,
    families: ["IMAGE_LINK", "TARGETING", "DESTINATION"],
    recommendation: "Route actor to high-priority moderation queue for manual review",
    phash: "0x3344a1b2c5d6e7f8",
    whash: "0x9988776655443322",
    tag: "suggestive_presentation (TTL: 14d)",
    crop: "Standard Crop",
    evidence: [
      "Curiosity funnel pattern: Benign comments targeting 95th percentile popularity spaces",
      "Elevated suggestive presentation score on profile avatar",
      "External bio link to unverified *.local domain"
    ],
    counter_evidence: [
      "High lexical diversity in comment text (normal TTR 0.82)"
    ],
    cluster_nodes: [
      { id: "actor_3b11e04a99", type: "actor", label: "Target" },
      { id: "media_avatar_02", type: "media", label: "Suggestive" },
      { id: "dom_promo_local", type: "domain", label: "funnel.local" }
    ]
  },
  {
    actor_id: "actor_5521a990ee",
    level: "LOW",
    score: 18.2,
    families: [],
    recommendation: "Allow standard activity; no policy action required",
    phash: "0x1122334455667788",
    whash: "0xaabbccddeeff0011",
    tag: "viral_meme_discounted",
    crop: "Center Crop",
    evidence: [
      "All observed signals within normal baseline thresholds"
    ],
    counter_evidence: [
      "Avatar reuse discounted: High community prevalence indicates viral meme or default avatar",
      "Organic account age > 400 days with steady low-frequency posting",
      "Zero abusive destination links"
    ],
    cluster_nodes: [
      { id: "actor_5521a990ee", type: "actor", label: "Organic User" }
    ]
  }
];

let state = {
  currentAlert: MOCK_ALERTS[0],
  revealsUsed: 0,
  maxReveals: 10,
  isRevealed: false
};

function renderQueue() {
  const listEl = document.getElementById("queue-list");
  listEl.innerHTML = "";

  MOCK_ALERTS.forEach((alert) => {
    const itemEl = document.createElement("div");
    itemEl.className = `queue-item ${alert.actor_id === state.currentAlert.actor_id ? "active" : ""}`;
    itemEl.onclick = () => selectAlert(alert);

    const levelClass = `risk-${alert.level.toLowerCase()}`;
    itemEl.innerHTML = `
      <div class="item-top">
        <span class="actor-hmac">${alert.actor_id}</span>
        <span class="badge ${levelClass}">${alert.level}</span>
      </div>
      <div class="item-meta">
        <span>Score: ${alert.score}</span> • <span>${alert.families.length} Families</span>
      </div>
    `;
    listEl.appendChild(itemEl);
  });
}

function selectAlert(alert) {
  state.currentAlert = alert;
  state.isRevealed = false;
  renderQueue();
  renderInspector();
}

function renderInspector() {
  const alert = state.currentAlert;
  document.getElementById("current-actor-id").innerText = alert.actor_id;
  document.getElementById("current-score").innerText = alert.score;
  
  const badgeEl = document.getElementById("risk-badge-large");
  badgeEl.className = `risk-badge risk-${alert.level.toLowerCase()}`;
  badgeEl.innerText = `${alert.level} RISK`;

  // Families
  const familyContainer = document.getElementById("family-pills");
  familyContainer.innerHTML = alert.families.length
    ? alert.families.map(f => `<span class="family-pill">${f}</span>`).join("")
    : `<span class="val-text">None</span>`;

  document.getElementById("policy-recommendation").innerText = alert.recommendation;
  document.getElementById("phash-val").innerText = alert.phash;
  document.getElementById("whash-val").innerText = alert.whash;
  document.getElementById("tag-badge").innerText = alert.tag;

  // Evidence
  const evList = document.getElementById("evidence-list");
  evList.innerHTML = alert.evidence.map(e => `<li>${e}</li>`).join("");

  const counterList = document.getElementById("counter-evidence-list");
  counterList.innerHTML = alert.counter_evidence.map(c => `<li>${c}</li>`).join("");

  // Media preview reset
  const canvas = document.getElementById("avatar-canvas");
  const overlay = document.getElementById("blur-overlay");
  if (state.isRevealed) {
    canvas.classList.add("revealed");
    overlay.classList.add("hidden");
  } else {
    canvas.classList.remove("revealed");
    overlay.classList.remove("hidden");
  }

  renderNetworkGraph(alert);
}

function handleReveal() {
  if (state.revealsUsed >= state.maxReveals) {
    alert("Session reveal quota exceeded (10/10). Please contact your administrator.");
    return;
  }
  state.revealsUsed++;
  state.isRevealed = true;
  document.getElementById("reveal-quota").innerText = `${state.revealsUsed} / ${state.maxReveals}`;
  
  const canvas = document.getElementById("avatar-canvas");
  const overlay = document.getElementById("blur-overlay");
  canvas.classList.add("revealed");
  overlay.classList.add("hidden");
}

function renderNetworkGraph(alert) {
  const svg = document.getElementById("network-svg");
  svg.innerHTML = "";

  const nodes = alert.cluster_nodes || [];
  if (nodes.length <= 1) {
    svg.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748b" font-size="12">Isolated Single Actor (No Coordinated Ring)</text>`;
    return;
  }

  // Draw coordinated network nodes
  const cx = 200;
  const cy = 130;
  const radius = 80;

  nodes.forEach((node, idx) => {
    const angle = (idx / nodes.length) * 2 * Math.PI;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);

    // Line to center target
    if (idx > 0) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", cx);
      line.setAttribute("y1", cy);
      line.setAttribute("x2", x);
      line.setAttribute("y2", y);
      line.setAttribute("stroke", "#334155");
      line.setAttribute("stroke-width", "2");
      svg.appendChild(line);
    }
  });

  nodes.forEach((node, idx) => {
    const angle = (idx / nodes.length) * 2 * Math.PI;
    const x = idx === 0 ? cx : cx + radius * Math.cos(angle);
    const y = idx === 0 ? cy : cy + radius * Math.sin(angle);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", idx === 0 ? "16" : "12");
    circle.setAttribute("fill", idx === 0 ? "#ef4444" : (node.type === "domain" ? "#f97316" : "#38bdf8"));
    circle.setAttribute("stroke", "#0f172a");
    circle.setAttribute("stroke-width", "2");
    svg.appendChild(circle);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", x);
    text.setAttribute("y", y + (idx === 0 ? 28 : 22));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#94a3b8");
    text.setAttribute("font-size", "10");
    text.textContent = node.label;
    svg.appendChild(text);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("reveal-btn").onclick = handleReveal;
  renderQueue();
  renderInspector();
});
