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
});
