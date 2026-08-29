(function () {
  "use strict";
  const storageKey = "pring-cycle-theme";

  function preferredTheme() {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") return saved;
    return "light";
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
  }

  applyTheme(preferredTheme());

  document.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("#theme-toggle")) {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(storageKey, next);
      applyTheme(next);
      return;
    }
    const command = target.closest("#manual-run-command")
      ? "manual_full"
      : target.closest("#generate-report-command")
        ? "report_generation"
        : null;
    if (!command) return;
    const feedback = document.querySelector("#command-feedback");
    if (feedback) feedback.textContent = "正在持久化命令…";
    const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" });
    fetch("/api/v1/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: command,
        target_business_date: today,
        client_request_id: crypto.randomUUID(),
      }),
    })
      .then(async function (response) {
        const document = await response.json();
        if (!response.ok) throw new Error(document.error || "command_rejected");
        if (feedback) feedback.textContent = `命令已持久化：${document.run_id}`;
      })
      .catch(function (error) {
        if (feedback) feedback.textContent = `命令未提交：${error.message}`;
      });
  });
})();
