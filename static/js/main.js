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
  function wireOverlay(overlay, closeButtonIds) {
    if (!overlay) return null;

    const close = function () {
      overlay.classList.add("is-closing");
      window.setTimeout(function () {
        overlay.classList.remove("is-open", "is-closing");
        overlay.style.display = "none";
      }, 150);
    };

    const open = function () {
      overlay.classList.remove("is-closing");
      overlay.style.display = "flex";
      overlay.classList.add("is-open");
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

    return { open, close };
  }

  // Success/error popup (rendered server-side from Django messages).
  wireOverlay(document.getElementById("site-modal"), ["modal-close", "modal-ok"]);

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
});
