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
});
