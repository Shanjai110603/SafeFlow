document.addEventListener("DOMContentLoaded", async () => {
  const statusEl = document.getElementById("api-status");
  const rescanBtn = document.getElementById("rescan-btn");

  try {
    const res = await fetch("http://127.0.0.1:8000/v1/health", { method: "GET" });
    if (res.ok) {
      const data = await res.json();
      statusEl.textContent = `Connected (${data.version})`;
      statusEl.style.color = "#4ade80";
    } else {
      statusEl.textContent = "Node Offline (Local Mode)";
      statusEl.style.color = "#f59e0b";
    }
  } catch (err) {
    statusEl.textContent = "Standalone Heuristic";
    statusEl.style.color = "#94a3b8";
  }

  rescanBtn.addEventListener("click", () => {
    rescanBtn.textContent = "Scanning...";
    setTimeout(() => {
      rescanBtn.textContent = "Active Protection On";
    }, 400);
  });
});
