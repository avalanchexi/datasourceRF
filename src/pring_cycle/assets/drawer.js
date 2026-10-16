// The site-wide right drawer (pring_cycle.drawer). The server renders every panel hidden in
// the page; this script shows one at a time while the URL fragment is #drawer-<key>, so an
// open drawer is a shareable link, Back closes it and a new trigger replaces the content.
(function () {
  "use strict";
  const prefix = "drawer-";
  let backdrop = null;
  let openPanel = null;
  let returnFocus = null;

  function fragment() {
    const key = decodeURIComponent(window.location.hash.slice(1));
    return key.startsWith(prefix) ? key : "";
  }

  function ensureBackdrop() {
    if (backdrop) return backdrop;
    backdrop = document.createElement("div");
    backdrop.className = "drawer-backdrop";
    backdrop.hidden = true;
    backdrop.addEventListener("click", close);
    document.body.appendChild(backdrop);
    return backdrop;
  }

  function show(panel, fromLink) {
    if (openPanel && openPanel !== panel && openPanel.isConnected) openPanel.hidden = true;
    const first = !openPanel;
    openPanel = panel;
    panel.hidden = false;
    ensureBackdrop().hidden = false;
    document.documentElement.classList.add("drawer-open");
    if (!fromLink && first) {
      // A shared link: bring the trigger into view behind the drawer.
      const trigger = document.querySelector('a.drawer-trigger[href="#' + CSS.escape(panel.id) + '"]');
      if (trigger) { trigger.scrollIntoView({block: "center"}); returnFocus = trigger; }
    }
    // Charts drawn while the panel was hidden take the drawer's width on the next resize.
    window.dispatchEvent(new Event("resize"));
    const closeLink = panel.querySelector(".drawer-close");
    if (closeLink) closeLink.focus({preventScroll: true});
  }

  function hide() {
    if (openPanel && openPanel.isConnected) openPanel.hidden = true;
    openPanel = null;
    if (backdrop) backdrop.hidden = true;
    document.documentElement.classList.remove("drawer-open");
    if (returnFocus && returnFocus.isConnected) returnFocus.focus({preventScroll: true});
    returnFocus = null;
  }

  function sync(fromLink) {
    const key = fragment();
    const panel = key ? document.getElementById(key) : null;
    if (panel && panel.classList.contains("drawer-panel")) {
      if (panel !== openPanel || panel.hidden) show(panel, fromLink === true);
    } else if (openPanel) {
      hide();
    }
  }

  function open(trigger) {
    returnFocus = returnFocus || trigger;
    const url = window.location.pathname + window.location.search + trigger.getAttribute("href");
    // One drawer at a time: switching replaces the entry, so one Back always closes.
    if (fragment()) window.history.replaceState(window.history.state, "", url);
    else window.history.pushState({drawer: true}, "", url);
    sync(true);
  }

  function close() {
    if (!fragment()) { hide(); return; }
    if (window.history.state && window.history.state.drawer) window.history.back();
    else { window.history.replaceState(null, "", window.location.pathname + window.location.search); hide(); }
  }

  document.addEventListener("click", function (event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const trigger = target.closest("a.drawer-trigger");
    if (trigger && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
      event.preventDefault();
      open(trigger);
      return;
    }
    if (target.closest(".drawer-close")) { event.preventDefault(); close(); }
  });

  document.addEventListener("keydown", function (event) {
    if (!openPanel) return;
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key !== "Tab") return;
    // Keep keyboard focus inside the open drawer.
    const focusable = [...openPanel.querySelectorAll("a[href], button, [tabindex]")]
      .filter(item => !item.disabled && item.tabIndex >= 0 && item.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!openPanel.contains(document.activeElement)) { event.preventDefault(); first.focus(); }
    else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  window.addEventListener("popstate", sync);
  window.addEventListener("hashchange", sync);
  // Dash renders the page after load and re-renders it on refresh: reopen from the fragment.
  new MutationObserver(function () {
    if (fragment() ? !openPanel || !openPanel.isConnected : openPanel) sync();
  }).observe(document.body, {childList: true, subtree: true});
})();
