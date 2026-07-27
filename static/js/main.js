// Closes the mobile nav automatically when a link is clicked.
document.addEventListener("DOMContentLoaded", function () {
  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.querySelectorAll(".main-nav a");

  navLinks.forEach(function (link) {
    link.addEventListener("click", function () {
      if (navToggle) {
        navToggle.checked = false;
      }
    });
  });

  // Light/dark theme toggle. The saved preference is applied synchronously
  // in <head> (see base.html) to avoid a flash; this just handles clicks
  // and keeps localStorage in sync from then on.
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      const root = document.documentElement;
      const current = root.getAttribute("data-theme") === "light" ? "light" : "dark";
      const next = current === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("gfc-theme", next);
      } catch (e) {
        // Ignore storage errors (e.g. private browsing) — theme still
        // applies for the current page view.
      }
    });
  }

  // Shared close/open behaviour for floating overlays: the success/error
  // message popup, and the "Register Your Team" floating form. Both use
  // the same overlay pattern (click backdrop, close button, or Escape to
  // dismiss); the form overlay additionally has a button that opens it.
  function syncBodyModalLock() {
    const anyOpen = document.querySelector(
      ".form-modal-overlay.is-open, .modal-overlay.is-open, #site-modal.is-open"
    );
    // site-modal may be visible without is-open class on first paint
    const siteModal = document.getElementById("site-modal");
    const siteVisible =
      siteModal &&
      !siteModal.classList.contains("is-closing") &&
      siteModal.offsetParent !== null;
    if (anyOpen || siteVisible) {
      document.body.classList.add("modal-open");
    } else {
      document.body.classList.remove("modal-open");
    }
  }

  function wireOverlay(overlay, closeButtonIds) {
    if (!overlay) return null;

    const close = function () {
      overlay.classList.add("is-closing");
      window.setTimeout(function () {
        overlay.classList.remove("is-open", "is-closing");
        overlay.style.display = "none";
        syncBodyModalLock();
      }, 150);
    };

    const open = function () {
      overlay.classList.remove("is-closing");
      overlay.style.display = "flex";
      overlay.classList.add("is-open");
      document.body.classList.add("modal-open");
    };

    closeButtonIds.forEach(function (id) {
      const btn = document.getElementById(id);
      if (btn) btn.addEventListener("click", close);
    });

    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        close();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && overlay.classList.contains("is-open")) {
        close();
      }
    });

    // If server rendered the overlay already open (validation errors),
    // lock page scroll without jumping the viewport.
    if (overlay.classList.contains("is-open")) {
      overlay.style.display = "flex";
      document.body.classList.add("modal-open");
    }

    return { open, close };
  }

  // Success/error popup (rendered server-side from Django messages).
  const siteModal = document.getElementById("site-modal");
  const siteModalApi = wireOverlay(siteModal, ["modal-close", "modal-ok"]);
  if (siteModal && siteModalApi) {
    // Messages modal is shown on load — keep scroll locked until dismissed.
    siteModal.classList.add("is-open");
    siteModal.style.display = "flex";
    document.body.classList.add("modal-open");
    // Stay at current/top position; do not honor leftover #hash scrolls.
    if (window.location.hash) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    window.scrollTo(0, 0);
  }

  // Floating "Register Your Team" form. It may already be open on load
  // (server adds the "is-open" class if the last submission had errors to
  // fix), otherwise it's opened by the CTA button.
  const registerModal = wireOverlay(
    document.getElementById("register-form-modal"),
    ["register-form-close"]
  );
  const openRegisterBtn = document.getElementById("open-register-form");
  if (openRegisterBtn && registerModal) {
    openRegisterBtn.addEventListener("click", registerModal.open);
  }

  // Prevent double-submit (extra emails / duplicate rows) from rapid clicks.
  function guardSubmitOnce(form, button) {
    if (!form || !button) return;
    form.addEventListener("submit", function () {
      if (button.disabled) return;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      const original = button.textContent;
      button.dataset.originalLabel = original;
      button.textContent = "Submitting…";
    });
  }
  guardSubmitOnce(
    document.querySelector(".register-form"),
    document.getElementById("register-submit-btn")
  );
  guardSubmitOnce(
    document.getElementById("contact-form"),
    document.getElementById("contact-submit-btn")
  );

  // Shared fade-open / fade-close helper for schedule overlays.
  function wireFadeOverlay(overlay, options) {
    if (!overlay) return null;
    const bodyClass = options.bodyClass || "";
    const closeBtn = options.closeBtn || null;
    const onOpen = options.onOpen || null;
    let closeTimer = null;

    function close() {
      if (!overlay.classList.contains("is-open")) return;
      overlay.classList.add("is-closing");
      if (bodyClass) document.body.classList.remove(bodyClass);
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(function () {
        overlay.classList.remove("is-open", "is-closing");
        overlay.style.display = "none";
        overlay.hidden = true;
      }, 320);
    }

    function open() {
      window.clearTimeout(closeTimer);
      if (typeof onOpen === "function") onOpen();
      overlay.hidden = false;
      overlay.style.display = "flex";
      overlay.classList.remove("is-closing", "is-open");
      void overlay.offsetWidth;
      overlay.classList.add("is-open");
      if (bodyClass) document.body.classList.add(bodyClass);
    }

    if (closeBtn) closeBtn.addEventListener("click", close);
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) close();
    });

    return { open: open, close: close, el: overlay };
  }

  // Group standings drawer: side "Tables" button opens tabbed overlay.
  const groupOverlay = document.getElementById("group-table-overlay");
  const openGroupTablesBtn = document.getElementById("open-group-tables");
  const groupTabs = document.querySelectorAll("[data-group-tab]");

  function setActiveGroupTab(panelId) {
    document.querySelectorAll("[data-group-panel]").forEach(function (panel) {
      panel.hidden = panel.id !== panelId;
    });
    groupTabs.forEach(function (tab) {
      const active = tab.getAttribute("data-group-tab") === panelId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  let pendingGroupPanel = null;
  const groupModal = wireFadeOverlay(groupOverlay, {
    bodyClass: "group-overlay-open",
    closeBtn: document.getElementById("group-overlay-close"),
    onOpen: function () {
      const firstPanel = document.querySelector("[data-group-panel]");
      const target = pendingGroupPanel || (firstPanel && firstPanel.id);
      if (target) setActiveGroupTab(target);
      pendingGroupPanel = null;
    },
  });

  if (openGroupTablesBtn && groupModal) {
    openGroupTablesBtn.addEventListener("click", function () {
      pendingGroupPanel = null;
      if (knockoutModal) knockoutModal.close();
      groupModal.open();
    });
  }

  // Group-stage cards (shown while knockout is locked).
  document
    .querySelectorAll(".group-card[data-group-target]")
    .forEach(function (card) {
      card.addEventListener("click", function () {
        pendingGroupPanel = card.getAttribute("data-group-target");
        if (knockoutModal) knockoutModal.close();
        if (groupModal) groupModal.open();
      });
    });

  groupTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      setActiveGroupTab(tab.getAttribute("data-group-tab"));
    });
  });

  // Knockout rounds: clickable cards open an expand overlay (group-table pattern).
  const knockoutOverlay = document.getElementById("knockout-round-overlay");
  const knockoutCards = document.querySelectorAll(
    ".knockout-round-card[data-knockout-target]"
  );
  const knockoutTabs = document.querySelectorAll("[data-knockout-tab]");

  function setActiveKnockoutPanel(panelId) {
    document.querySelectorAll("[data-knockout-panel]").forEach(function (panel) {
      panel.hidden = panel.id !== panelId;
    });
    knockoutTabs.forEach(function (tab) {
      const active = tab.getAttribute("data-knockout-tab") === panelId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  let pendingKnockoutPanel = null;
  const knockoutModal = wireFadeOverlay(knockoutOverlay, {
    bodyClass: "knockout-overlay-open",
    closeBtn: document.getElementById("knockout-overlay-close"),
    onOpen: function () {
      const firstPanel = document.querySelector("[data-knockout-panel]");
      const target =
        pendingKnockoutPanel || (firstPanel && firstPanel.id);
      if (target) setActiveKnockoutPanel(target);
      pendingKnockoutPanel = null;
    },
  });

  knockoutCards.forEach(function (card) {
    card.addEventListener("click", function () {
      pendingKnockoutPanel = card.getAttribute("data-knockout-target");
      if (groupModal) groupModal.close();
      if (knockoutModal) knockoutModal.open();
    });
  });

  knockoutTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      setActiveKnockoutPanel(tab.getAttribute("data-knockout-tab"));
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    if (
      knockoutOverlay &&
      knockoutOverlay.classList.contains("is-open") &&
      knockoutModal
    ) {
      knockoutModal.close();
      return;
    }
    if (groupOverlay && groupOverlay.classList.contains("is-open") && groupModal) {
      groupModal.close();
    }
  });

  // Finished results stay visible briefly, then fade out (default 5 minutes).
  document.querySelectorAll(".match-row[data-finished-at]").forEach(function (row) {
    const finishedAt = Date.parse(row.getAttribute("data-finished-at"));
    if (Number.isNaN(finishedAt)) return;

    const minutes = parseInt(
      row.getAttribute("data-finished-visible-minutes") || "5",
      10
    );
    const visibleMs = (Number.isFinite(minutes) ? minutes : 5) * 60 * 1000;
    const remaining = finishedAt + visibleMs - Date.now();

    const removeRow = function () {
      row.classList.add("is-fading-out");
      window.setTimeout(function () {
        const list = row.closest(".match-list");
        row.remove();
        if (list && !list.querySelector(".match-row")) {
          const heading = list.previousElementSibling;
          if (heading && heading.classList.contains("results-title")) {
            heading.remove();
          }
          list.remove();
        }
      }, 450);
    };

    if (remaining <= 0) {
      removeRow();
    } else {
      window.setTimeout(removeRow, remaining);
    }
  });
});
