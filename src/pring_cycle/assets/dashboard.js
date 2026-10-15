(function () {
  "use strict";
  const storageKey = "pring-cycle-theme";
  const commands = new Map();

  function preferredTheme() {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
  }

  function reportProjection(button) {
    return button?.dataset.projectionId || document.querySelector("#report-projection")?.dataset.projectionId ||
      new URLSearchParams(window.location.search).get("projection");
  }

  function commandButton(fields) {
    if (fields.command === "manual_full") return document.querySelector("#manual-run-command");
    if (fields.command === "report_generation") {
      const button = document.querySelector("#generate-report-command");
      return reportProjection(button) === fields.projection_set_id ? button : null;
    }
    return document.querySelector('[data-run-action="' + CSS.escape(fields.command) +
      '"][data-run-id="' + CSS.escape(fields.run_id) + '"]');
  }

  function markActiveReportSection() {
    const toc = document.querySelector(".report-toc");
    if (!toc) return;
    const sections = [...document.querySelectorAll(".report-section[id]")];
    const boundary = Math.max(0, toc.getBoundingClientRect().bottom) + 24;
    let active = sections[0]?.id;
    sections.forEach(function (section) {
      if (section.getBoundingClientRect().top <= boundary) active = section.id;
    });
    toc.querySelectorAll("a").forEach(function (link) {
      if (link.hash === "#" + active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }

  function markActiveNavigation() {
    commands.forEach(function (_message, identity) {
      const button = commandButton(JSON.parse(identity));
      if (button) button.disabled = true;
    });
    const pathname = window.location.pathname || "/";
    document.querySelectorAll(".nav-link").forEach(function (link) {
      const destination = new URL(link.href, window.location.href).pathname;
      const active = destination === pathname || (destination === "/" &&
        ["/core-assets", "/macro", "/inventory", "/stage-history", "/reports", "/release-calendar"].includes(pathname));
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    const anchors = {"/core-assets": "assets", "/macro": "confirmation",
      "/inventory": "inventory", "/stage-history": "history"};
    const anchor = window.location.hash.slice(1) || anchors[pathname];
    const anchorIdentity = pathname + window.location.search + "#" + anchor;
    if (anchor && document.documentElement.dataset.locatedAnchor !== anchorIdentity) {
      const section = document.getElementById(anchor);
      if (section) { section.scrollIntoView(); document.documentElement.dataset.locatedAnchor = anchorIdentity; }
    }
    markActiveReportSection();
    document.querySelectorAll(".price-chart .js-plotly-plot").forEach(function (graph) {
      if (graph.dataset.evidenceBound || typeof graph.on !== "function") return;
      graph.dataset.evidenceBound = "true";
      graph.on("plotly_click", function (data) {
        const href = data.points && data.points[0] && data.points[0].customdata;
        if (typeof href === "string" && href.startsWith("/data-chain?")) window.location.assign(href);
      });
    });
  }

  applyTheme(preferredTheme());
  markActiveNavigation();
  new MutationObserver(markActiveNavigation).observe(document.body, {
    childList: true,
    subtree: true,
  });
  window.addEventListener("popstate", markActiveNavigation);
  window.addEventListener("hashchange", markActiveNavigation);
  window.addEventListener("resize", markActiveReportSection);

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
      submitCommand({
        command: command,
        run_id: runId,
        confirm_external_calls: command === "resume",
      }, runAction);
      return;
    }
    const command = target.closest("#manual-run-command")
      ? "manual_full"
      : target.closest("#generate-report-command")
        ? "report_generation"
        : null;
    if (!command) return;
    const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" });
    // Dash 4.2 把 DatePickerSingle 渲染成 id 所在的 input 本身；旧版是一个包住 input
    // 的容器。两种结构都要读到，否则用户选的目标交易日会被静默替换成今天。
    const targetInput =
      document.querySelector("input#manual-run-target") ||
      document.querySelector("#manual-run-target input");
    const targetDate =
      command === "manual_full" &&
      targetInput instanceof HTMLInputElement &&
      targetInput.value
        ? targetInput.value
        : today;
    submitCommand({
      command: command,
      target_business_date: targetDate,
      ...(command === "report_generation" ? {projection_set_id:
        reportProjection(target.closest("#generate-report-command"))} : {}),
    }, target.closest("button"));
  });

  function submitCommand(fields, button) {
    const feedback = document.querySelector("#command-feedback");
    const identity = JSON.stringify(fields);
    if (commands.has(identity)) {
      if (feedback) feedback.textContent = commands.get(identity);
      return;
    }
    const retryKey = "pring-command:" + identity;
    const requestId = sessionStorage.getItem(retryKey) || crypto.randomUUID();
    sessionStorage.setItem(retryKey, requestId);
    commands.set(identity, "正在持久化命令 · 幂等键 " + requestId);
    if (button) button.disabled = true;
    if (feedback) feedback.textContent = commands.get(identity);
    fetch("/api/v1/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...fields,
        client_request_id: requestId,
      }),
    })
      .then(async function (response) {
        const document = await response.json();
        if (!response.ok) throw new Error(document.error || "command_rejected");
        const message = `命令已受理：${document.run_id} · ${document.status} · 幂等键 ${requestId}`;
        commands.set(identity, message);
        sessionStorage.removeItem(retryKey);
        if (button) button.textContent = "已受理，查看运行记录";
        if (feedback) feedback.textContent = message;
        // Move an idle page to live polling as soon as a command is accepted.
        window.dash_clientside.set_props("command-refresh", {data: requestId});
        // Explicitly allow the next operation only after this run has reached a terminal state.
        function refreshAcceptedCommand() {
          fetch("/api/v1/runs/" + encodeURIComponent(document.run_id) + "/audit")
            .then(response => response.ok ? response.json() : null)
            .then(audit => {
              if (audit && ["completed", "cancelled", "failed", "action_required", "interrupted"]
                  .includes(audit.run.status)) {
                commands.delete(identity);
                const currentButton = commandButton(fields);
                if (currentButton) {
                  currentButton.disabled = fields.command === "cancel";
                  currentButton.textContent = fields.command === "cancel" ? "已取消后续步骤" :
                    fields.command === "resume" ? "允许外部调用并继续" :
                    fields.command === "report_generation" ? "为本投影生成新报告" : "再次发起运行";
                }
              } else window.setTimeout(refreshAcceptedCommand, 30000);
            }).catch(() => window.setTimeout(refreshAcceptedCommand, 30000));
        }
        window.setTimeout(refreshAcceptedCommand, 30000);
      })
      .catch(function (error) {
        const message = String(error.message).startsWith("source_certification_contract_unresolved:")
          ? "来源认证尚未完成，请先完成来源复核及新模型验收。历史结果仍可查看。"
          : error.message;
        if (feedback) feedback.textContent = `命令结果未确认：${message}。重试沿用幂等键 ${requestId}`;
        commands.delete(identity);
        const currentButton = commandButton(fields);
        if (currentButton) currentButton.disabled = false;
      });
  }

  // Preserve open explanations and focus when a changed ledger replaces the page.
  const reading = new Map();
  let renderedPage = null;
  function pageKey() { return window.location.pathname + window.location.search; }
  window.addEventListener("scroll", function () {
    markActiveReportSection();
    const state = reading.get(pageKey()) || {};
    state.scroll = window.scrollY;
    reading.set(pageKey(), state);
  }, {passive: true});
  document.addEventListener("toggle", function (event) {
    if (!(event.target instanceof HTMLDetailsElement)) return;
    const list = [...document.querySelectorAll("#page-content details")];
    const state = reading.get(pageKey()) || {};
    state.open = list.map((item, index) => item.open ? index : -1).filter(index => index >= 0);
    reading.set(pageKey(), state);
  }, true);
  document.addEventListener("focusin", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.closest("#page-content")) return;
    const state = reading.get(pageKey()) || {};
    state.focus = target.id ? "#" + CSS.escape(target.id) : target.getAttribute("name") ?
      '[name="' + CSS.escape(target.getAttribute("name")) + '"]' : null;
    reading.set(pageKey(), state);
  });
  new MutationObserver(function () {
    const page = document.querySelector("#page-content > *");
    if (!page || page === renderedPage) return;
    renderedPage = page;
    const state = reading.get(pageKey());
    if (!state) return;
    document.querySelectorAll("#page-content details").forEach((item, index) => {
      item.open = (state.open || []).includes(index);
    });
    const target = state.focus && page.querySelector(state.focus);
    if (target) target.focus({preventScroll: true});
    if (typeof state.scroll === "number") window.scrollTo({top: state.scroll, behavior: "instant"});
  }).observe(document.body, {childList: true, subtree: true});
})();
