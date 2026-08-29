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

  function markActiveNavigation() {
    const pathname = window.location.pathname || "/";
    document.querySelectorAll(".nav-link").forEach(function (link) {
      const active = new URL(link.href, window.location.href).pathname === pathname;
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  applyTheme(preferredTheme());
  markActiveNavigation();
  new MutationObserver(markActiveNavigation).observe(document.body, {
    childList: true,
    subtree: true,
  });
  window.addEventListener("popstate", markActiveNavigation);

  document.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest(".nav-link")) queueMicrotask(markActiveNavigation);
    if (target.closest("#theme-toggle")) {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(storageKey, next);
      applyTheme(next);
      return;
    }
    const runAction = target.closest("[data-run-action]");
    if (runAction) {
      const command = runAction.getAttribute("data-run-action");
      const runId = runAction.getAttribute("data-run-id");
      if (!command || !runId) return;
      if (
        command === "resume" &&
        !window.confirm("继续会恢复该运行，并允许尚未完成的外部调用。是否继续？")
      ) {
        return;
      }
      submitCommand({
        command: command,
        run_id: runId,
        confirm_external_calls: command === "resume",
      });
      return;
    }
    const command = target.closest("#manual-run-command")
      ? "manual_full"
      : target.closest("#generate-report-command")
        ? "report_generation"
        : null;
    if (!command) return;
    const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" });
    const targetInput = document.querySelector("#manual-run-target input");
    const targetDate =
      command === "manual_full" && targetInput instanceof HTMLInputElement
        ? targetInput.value
        : today;
    submitCommand({
      command: command,
      target_business_date: targetDate,
    });
  });

  function submitCommand(fields) {
    const feedback = document.querySelector("#command-feedback");
    if (feedback) feedback.textContent = "正在持久化命令…";
    fetch("/api/v1/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...fields,
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
  }
})();
