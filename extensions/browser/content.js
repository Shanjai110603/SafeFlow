/**
 * SafeFlow Defensive Shield - Content Script
 * Scans page links for multi-hop redirection funnels and cloaked domains.
 */

(function () {
  const SUSPICIOUS_PATTERNS = [
    /funnel\.local/i,
    /redirect\.local/i,
    /tiny\.local/i,
    /bitly\.local/i,
    /t\.co\.local/i,
  ];

  function scanLinks() {
    const links = document.querySelectorAll("a[href]");
    let flaggedCount = 0;

    links.forEach((a) => {
      const href = a.href || "";
      const isSuspicious = SUSPICIOUS_PATTERNS.some((pattern) => pattern.test(href));

      if (isSuspicious && !a.dataset.safeflowScanned) {
        a.dataset.safeflowScanned = "true";
        flaggedCount++;

        // Add visual indicator
        a.style.outline = "2px solid #ef4444";
        a.style.position = "relative";
        a.title = "SafeFlow Alert: Suspicious redirection pathway detected.";

        a.addEventListener("click", (e) => {
          const confirmNav = confirm(
            "⚠️ SafeFlow Defensive Shield Warning:\n\n" +
            "This link matches a high-risk multi-hop redirection funnel pattern.\n" +
            "Destination: " + href + "\n\n" +
            "Are you sure you want to proceed?"
          );
          if (!confirmNav) {
            e.preventDefault();
            e.stopPropagation();
          }
        });
      }
    });

    if (flaggedCount > 0) {
      console.warn(`[SafeFlow] Intercepted ${flaggedCount} high-risk redirection links.`);
    }
  }

  // Initial scan & MutationObserver for dynamic infinite scroll feeds
  scanLinks();
  const observer = new MutationObserver(() => scanLinks());
  observer.observe(document.body, { childList: true, subtree: true });
})();
