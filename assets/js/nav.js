(() => {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  const hasHero = !!document.querySelector(".hero");
  const threshold = 60;
  function update() {
    if (hasHero && window.scrollY < threshold) nav.classList.add("nav--transparent");
    else nav.classList.remove("nav--transparent");
  }
  update();
  window.addEventListener("scroll", update, { passive: true });
})();
