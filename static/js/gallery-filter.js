// Client-side gallery filtering so switching categories never leaves the
// single scrollable page or triggers a full reload.
document.addEventListener("DOMContentLoaded", function () {
  const filterBar = document.querySelector("[data-gallery-filters]");
  const gallery = document.querySelector("[data-gallery]");

  if (!filterBar || !gallery) {
    return;
  }

  const chips = filterBar.querySelectorAll(".filter-chip");
  const items = gallery.querySelectorAll(".gallery-item");

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      const filter = chip.getAttribute("data-filter");

      chips.forEach(function (c) {
        c.classList.remove("active");
      });
      chip.classList.add("active");

      items.forEach(function (item) {
        const matches = filter === "all" || item.getAttribute("data-category") === filter;
        item.style.display = matches ? "" : "none";
      });
    });
  });
});
