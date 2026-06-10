document.addEventListener("click", (event) => {
  const tab = event.target.closest(".tabs button");
  if (tab) {
    const tabs = tab.parentElement.querySelectorAll("button");
    const section = tab.closest(".tabbed-section");
    if (!section) return;
    tabs.forEach((item) => {
      item.classList.toggle("active", item === tab);
      item.setAttribute("aria-selected", item === tab ? "true" : "false");
    });
    section.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === tab.getAttribute("aria-controls"));
    });
    return;
  }

  const galleryButton = event.target.closest(".gallery-item");
  if (galleryButton) {
    const items = [...document.querySelectorAll(".gallery-item img")];
    const image = galleryButton.querySelector("img");
    const index = items.indexOf(image);
    openLightbox(items, index);
  }
});

const hero = document.querySelector(".project-hero img");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (hero && !reduceMotion) {
  const updateHeroMotion = () => {
    const progress = Math.min(Math.max(window.scrollY / 520, 0), 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    document.documentElement.style.setProperty("--hero-scale", (1 - eased * 0.045).toFixed(4));
    document.documentElement.style.setProperty("--hero-shift", `${Math.round(eased * -14)}px`);
    document.documentElement.style.setProperty("--hero-radius", `${Math.round(eased * 2)}px`);
  };
  updateHeroMotion();
  window.addEventListener("scroll", updateHeroMotion, { passive: true });
}

if (!reduceMotion && "IntersectionObserver" in window) {
  const revealItems = document.querySelectorAll([
    ".portrait-frame",
    ".intro-content",
    ".featured-section",
    ".project-card",
    ".page-title",
    ".filters",
    ".project-hero",
    ".project-info",
    ".project-section",
    ".cv-identity",
    ".cv-block",
    ".contact-card",
  ].join(","));

  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px 6% 0px", threshold: 0.04 });

  revealItems.forEach((item) => {
    item.classList.add("reveal");
    if (item.getBoundingClientRect().top < window.innerHeight * 0.98) {
      item.classList.add("is-visible");
      return;
    }
    revealObserver.observe(item);
  });
}

document.querySelectorAll(".gallery-grid").forEach((gallery) => {
  gallery.addEventListener("wheel", (event) => {
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    if (gallery.scrollWidth <= gallery.clientWidth) return;
    event.preventDefault();
    gallery.scrollBy({ left: event.deltaY * 0.9, behavior: "smooth" });
  }, { passive: false });
});

document.querySelectorAll(".before-after").forEach((slider) => {
  const range = slider.querySelector(".before-after-range");
  const update = () => {
    slider.style.setProperty("--before-after-position", `${range.value}%`);
  };
  range.addEventListener("input", update);
  update();
});

function openLightbox(items, index) {
  const lightbox = document.querySelector(".lightbox");
  const image = lightbox.querySelector("img");
  const useThumbs = document.body.classList.contains("lightbox-thumbs-prototype");
  let current = index;

  function updateControls() {
    window.requestAnimationFrame(() => {
      const rect = image.getBoundingClientRect();
      const styles = window.getComputedStyle(lightbox);
      const controlSize = Number.parseFloat(styles.getPropertyValue("--lightbox-control-size")) || 44;
      const controlGap = Number.parseFloat(styles.getPropertyValue("--lightbox-control-gap")) || 24;
      const closeGap = Number.parseFloat(styles.getPropertyValue("--lightbox-close-gap")) || 16;
      const viewportPadding = Number.parseFloat(styles.getPropertyValue("--lightbox-viewport-padding")) || 12;
      const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
      const maxLeft = window.innerWidth - controlSize - viewportPadding;
      const prevLeft = clamp(rect.left - controlSize - controlGap, viewportPadding, maxLeft);
      const nextLeft = clamp(rect.right + controlGap, viewportPadding, maxLeft);
      const closeLeft = clamp(rect.right - controlSize, viewportPadding, maxLeft);
      const closeTop = clamp(rect.top - controlSize - closeGap, viewportPadding, window.innerHeight - controlSize - viewportPadding);
      lightbox.style.setProperty("--lightbox-image-left", `${Math.round(rect.left)}px`);
      lightbox.style.setProperty("--lightbox-image-right", `${Math.round(window.innerWidth - rect.right)}px`);
      lightbox.style.setProperty("--lightbox-image-top", `${Math.round(rect.top)}px`);
      lightbox.style.setProperty("--lightbox-image-mid", `${Math.round(rect.top + rect.height / 2)}px`);
      lightbox.style.setProperty("--lightbox-prev-left", `${Math.round(prevLeft)}px`);
      lightbox.style.setProperty("--lightbox-next-left", `${Math.round(nextLeft)}px`);
      lightbox.style.setProperty("--lightbox-close-left", `${Math.round(closeLeft)}px`);
      lightbox.style.setProperty("--lightbox-close-top", `${Math.round(closeTop)}px`);
    });
  }

  function render() {
    const nextSrc = items[current].dataset.fullSrc || items[current].src;
    if (useThumbs) {
      image.classList.add("lightbox-image-fade", "is-changing");
      window.setTimeout(() => {
        image.src = nextSrc;
        image.alt = items[current].alt;
        image.onload = updateControls;
        updateControls();
        window.setTimeout(updateControls, 220);
        updateThumbs();
        image.classList.remove("is-changing");
      }, 150);
      return;
    }
    image.src = nextSrc;
    image.alt = items[current].alt;
    image.onload = updateControls;
    updateControls();
    window.setTimeout(updateControls, 220);
  }

  function close() {
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    image.removeAttribute("src");
    image.onload = null;
    lightbox.querySelector(".lightbox-thumbs")?.remove();
    document.removeEventListener("keydown", onKeydown);
    window.removeEventListener("resize", updateControls);
  }

  function move(delta) {
    current = (current + delta + items.length) % items.length;
    render();
  }

  function onKeydown(event) {
    if (event.key === "Escape") close();
    if (event.key === "ArrowLeft") move(-1);
    if (event.key === "ArrowRight") move(1);
  }

  function buildThumbs() {
    if (!useThumbs) return;
    lightbox.querySelector(".lightbox-thumbs")?.remove();
    const thumbs = document.createElement("div");
    thumbs.className = "lightbox-thumbs";
    items.forEach((item, index) => {
      const button = document.createElement("button");
      button.className = "lightbox-thumb";
      button.type = "button";
      button.setAttribute("aria-label", `View image ${index + 1}`);
      button.innerHTML = `<img src="${item.src}" alt="">`;
      button.addEventListener("click", () => {
        current = index;
        render();
      });
      thumbs.appendChild(button);
    });
    lightbox.appendChild(thumbs);
    updateThumbs();
  }

  function updateThumbs() {
    if (!useThumbs) return;
    const thumbs = [...lightbox.querySelectorAll(".lightbox-thumb")];
    thumbs.forEach((thumb, index) => {
      thumb.classList.toggle("active", index === current);
      if (index === current) {
        thumb.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      }
    });
  }

  lightbox.querySelector(".lightbox-close").onclick = close;
  lightbox.querySelector(".lightbox-prev").onclick = () => move(-1);
  lightbox.querySelector(".lightbox-next").onclick = () => move(1);
  lightbox.classList.add("open");
  lightbox.setAttribute("aria-hidden", "false");
  document.addEventListener("keydown", onKeydown);
  window.addEventListener("resize", updateControls, { passive: true });
  buildThumbs();
  render();
}
