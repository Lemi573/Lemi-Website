document.addEventListener("click", (event) => {
  const tab = event.target.closest(".tabs button");
  if (tab) {
    const tabs = tab.parentElement.querySelectorAll("button");
    const section = tab.closest(".design-process");
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

function openLightbox(items, index) {
  const lightbox = document.querySelector(".lightbox");
  const image = lightbox.querySelector("img");
  let current = index;

  function render() {
    image.src = items[current].src;
    image.alt = items[current].alt;
  }

  function close() {
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    image.removeAttribute("src");
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

  lightbox.querySelector(".lightbox-close").onclick = close;
  lightbox.querySelector(".lightbox-prev").onclick = () => move(-1);
  lightbox.querySelector(".lightbox-next").onclick = () => move(1);
  lightbox.classList.add("open");
  lightbox.setAttribute("aria-hidden", "false");
  document.addEventListener("keydown", onKeydown);
  render();
}
