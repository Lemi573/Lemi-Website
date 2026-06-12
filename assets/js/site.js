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

const aboutIntro = document.querySelector(".home-intro");

if (aboutIntro) {
  const portraitImage = aboutIntro.querySelector(".portrait-crop img");
  const introCopy = aboutIntro.querySelector(".intro-copy");
  const compactAbout = window.matchMedia("(max-width: 920px)");
  const syncAboutGrid = () => {
    if (!portraitImage || !introCopy) return;
    if (compactAbout.matches || !portraitImage.naturalHeight) {
      aboutIntro.style.removeProperty("--about-hair-offset");
      aboutIntro.style.removeProperty("--about-portrait-width");
      return;
    }
    const hairTop = 148;
    const visibleRatio = (portraitImage.naturalHeight - hairTop) / portraitImage.naturalHeight;
    const copyHeight = introCopy.getBoundingClientRect().height;
    const imageHeight = copyHeight / visibleRatio;
    const imageWidth = imageHeight * (portraitImage.naturalWidth / portraitImage.naturalHeight);
    const hairOffset = imageHeight * (hairTop / portraitImage.naturalHeight);
    aboutIntro.style.setProperty("--about-hair-offset", `${hairOffset}px`);
    aboutIntro.style.setProperty("--about-portrait-width", `${imageWidth}px`);
  };

  syncAboutGrid();
  portraitImage.addEventListener("load", syncAboutGrid);
  window.addEventListener("resize", syncAboutGrid);
  window.addEventListener("load", syncAboutGrid);
  document.fonts?.ready.then(syncAboutGrid);
}

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
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.12 });

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

  function render() {
    if (useThumbs) {
      image.classList.add("lightbox-image-fade", "is-changing");
      window.setTimeout(() => {
        image.src = items[current].src;
        image.alt = items[current].alt;
        updateThumbs();
        image.classList.remove("is-changing");
      }, 150);
      return;
    }
    image.src = items[current].src;
    image.alt = items[current].alt;
  }

  function close() {
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    image.removeAttribute("src");
    lightbox.querySelector(".lightbox-thumbs")?.remove();
    document.removeEventListener("keydown", onKeydown);
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
  buildThumbs();
  render();
}
