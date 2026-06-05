from __future__ import annotations

import hashlib
import html
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = ROOT / "3 Projects"
ABOUT_ROOT = ROOT / "1 About"
CONTACT_FILE = ROOT / "4 Contact" / "Contact.txt"
CV_PDF = ROOT / "2 CV" / "Lemi_Hadarau_CV.pdf"
GENERATED_ASSETS = ROOT / "assets" / "generated"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ENABLED_CATEGORIES = {"Commercial"}


@dataclass
class ProjectInfo:
    title: str = ""
    location: str = ""
    year: str = ""
    role: str = ""
    stage: str = ""
    contribution: str = ""
    description: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)


@dataclass
class ImageAsset:
    source: Path
    url: str
    alt: str


@dataclass
class Project:
    category: str
    category_slug: str
    source: Path
    order: int
    display_name: str
    slug: str
    info: ProjectInfo
    cover: ImageAsset
    sections: dict[str, list[ImageAsset]]
    design_iterations: dict[str, list[ImageAsset]]


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def leading_number(path: Path) -> int:
    match = re.match(r"\s*(\d+)", path.name)
    return int(match.group(1)) if match else 9999


def strip_leading_number(name: str) -> str:
    return re.sub(r"^\s*\d+\s*", "", name).strip()


def bracket_name(name: str) -> str:
    match = re.search(r"\(([^)]+)\)", name)
    if match:
        return match.group(1).strip()
    return strip_leading_number(name)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "item"


def paragraph_html(paragraphs: Iterable[str]) -> str:
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip())


def output_path_to_url(path: Path) -> str:
    return "/" + path.relative_to(ROOT).as_posix()


def optimize_image(source: Path, width: int = 2200) -> ImageAsset:
    rel = source.relative_to(ROOT)
    digest = hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:10]
    filename = f"{slugify(source.stem)}-{digest}.jpg"
    dest = GENERATED_ASSETS / filename
    if not dest.exists() or dest.stat().st_mtime < source.stat().st_mtime:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            if image.width > width:
                height = round(image.height * (width / image.width))
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            image.save(dest, "JPEG", quality=86, optimize=True, progressive=True)
    return ImageAsset(source=source, url=output_path_to_url(dest), alt=source.stem)


def parse_project_info(path: Path) -> ProjectInfo:
    text = read_text(path).replace("\r\n", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    non_empty = [line.strip() for line in lines if line.strip()]
    title = ""
    if "Project Information" in non_empty:
        index = non_empty.index("Project Information")
        title = non_empty[index + 1] if len(non_empty) > index + 1 else ""
    else:
        title = non_empty[0] if non_empty else ""

    fields = {}
    for key in ("Location", "Year", "Role", "Stage", "Contribution"):
        match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", text)
        fields[key.lower()] = match.group(1).strip() if match else ""

    description: list[str] = []
    responsibilities: list[str] = []
    mode = None
    for line in lines:
        stripped = line.strip()
        if re.match(r"(?i)^(short\s+)?description:?\s*$", stripped):
            mode = "description"
            continue
        if re.match(r"(?i)^key responsibilities:?\s*$", stripped):
            mode = "responsibilities"
            continue
        if not stripped:
            continue
        if mode == "description":
            description.append(stripped)
        elif mode == "responsibilities":
            responsibilities.append(stripped)

    return ProjectInfo(
        title=title,
        location=fields["location"],
        year=fields["year"],
        role=fields["role"],
        stage=fields["stage"],
        contribution=fields["contribution"],
        description=description,
        responsibilities=responsibilities,
    )


def image_files(path: Path) -> list[Path]:
    return sorted(
        [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda p: natural_key(str(p.relative_to(path))),
    )


def direct_image_files(path: Path) -> list[Path]:
    return sorted(
        [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda p: natural_key(p.name),
    )


def load_projects() -> list[Project]:
    projects: list[Project] = []
    categories = sorted([p for p in PROJECTS_ROOT.iterdir() if p.is_dir()], key=leading_number)
    for category_path in categories:
        category_name = strip_leading_number(category_path.name)
        category_slug = slugify(category_name)
        if category_name not in ENABLED_CATEGORIES:
            continue
        for project_path in sorted([p for p in category_path.iterdir() if p.is_dir()], key=leading_number):
            info_files = sorted(project_path.glob("*Project Information.txt"), key=lambda p: natural_key(p.name))
            cover_files = [
                p
                for p in direct_image_files(project_path)
                if re.search(r"cover\.(jpe?g|png|webp)$", p.name, re.IGNORECASE)
            ]
            if not info_files or not cover_files:
                continue

            display_name = bracket_name(project_path.name)
            project_slug = slugify(display_name)
            sections: dict[str, list[ImageAsset]] = {}
            design_iterations: dict[str, list[ImageAsset]] = {}
            for section_path in sorted([p for p in project_path.iterdir() if p.is_dir()], key=lambda p: natural_key(p.name)):
                if section_path.name.lower() == "visualisations":
                    iteration_dirs = [
                        p for p in section_path.iterdir() if p.is_dir() and re.search(r"design iteration", p.name, re.IGNORECASE)
                    ]
                    for iteration in sorted(iteration_dirs, key=lambda p: natural_key(p.name)):
                        design_iterations[iteration.name] = [optimize_image(img) for img in image_files(iteration)]
                    normal_visuals = [
                        p for p in direct_image_files(section_path) if p.suffix.lower() in IMAGE_EXTENSIONS
                    ]
                    if normal_visuals:
                        sections["Visualisations"] = [optimize_image(img) for img in normal_visuals]
                    continue

                images = image_files(section_path)
                if images:
                    section_name = "Photomontages" if section_path.name.lower().startswith("photomontage") else section_path.name
                    sections[section_name] = [optimize_image(img) for img in images]

            projects.append(
                Project(
                    category=category_name,
                    category_slug=category_slug,
                    source=project_path,
                    order=leading_number(project_path),
                    display_name=display_name,
                    slug=project_slug,
                    info=parse_project_info(info_files[0]),
                    cover=optimize_image(cover_files[0]),
                    sections=sections,
                    design_iterations=design_iterations,
                )
            )
    return projects


def page(title: str, body: str, active: str = "") -> str:
    nav = [
        ("About", "/", "about"),
        ("Projects", "/projects/", "projects"),
        ("CV", "/cv/", "cv"),
        ("Contact", "/contact/", "contact"),
    ]
    nav_html = "".join(
        f'<a class="{"active" if key == active else ""}" href="{href}">{label}</a>' for label, href, key in nav
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} | Lemi Hadarau</title>
  <meta name="description" content="Architectural portfolio of Lemi Hadarau, Architect based in Ireland.">
  <link rel="stylesheet" href="/assets/css/styles.css">
  <script src="/assets/js/site.js" defer></script>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">Lemi Hadarau</a>
    <nav aria-label="Main navigation">{nav_html}</nav>
  </header>
  <main>{body}</main>
  <footer class="site-footer">
    <span>Lemi Hadarau</span>
    <span>Architect MRIAI</span>
    <a href="mailto:lemuel_marius@yahoo.com?subject=Portfolio%20Enquiry">lemuel_marius@yahoo.com</a>
  </footer>
  <div class="lightbox" aria-hidden="true">
    <button class="lightbox-close" type="button" aria-label="Close image">Close</button>
    <button class="lightbox-prev" type="button" aria-label="Previous image">Prev</button>
    <img alt="">
    <button class="lightbox-next" type="button" aria-label="Next image">Next</button>
  </div>
</body>
</html>
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def read_about() -> list[str]:
    about_file = ABOUT_ROOT / "About.txt"
    text = read_text(about_file) if about_file.exists() else ""
    paragraphs = [line.strip() for line in text.splitlines() if line.strip() and line.strip().lower() != "about"]
    return paragraphs


def about_portrait() -> ImageAsset | None:
    candidates = [
        p
        for p in ABOUT_ROOT.glob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and re.search(r"portrait|profile|about|lemi", p.name, re.I)
    ]
    if not candidates:
        return None
    return optimize_image(candidates[0], width=1400)


def project_card(project: Project) -> str:
    return f"""
<a class="project-card" href="/projects/{project.category_slug}/{project.slug}/">
  <img src="{project.cover.url}" alt="{html.escape(project.display_name)}">
  <span class="project-card-title">{html.escape(project.display_name)}</span>
</a>"""


def build_home(projects: list[Project]) -> None:
    about = read_about()
    portrait = about_portrait()
    if portrait:
        portrait_html = f'<img src="{portrait.url}" alt="Black and white portrait of Lemi Hadarau">'
    else:
        portrait_html = '<div class="portrait-placeholder">Portrait image<br>to be added</div>'
    featured = "\n".join(project_card(project) for project in projects[:5])
    body = f"""
<section class="home-intro section">
  <div>
    <p class="eyebrow">Architect MRIAI</p>
    <h1>Lemi Hadarau</h1>
    <div class="intro-copy">{paragraph_html(about[:3])}</div>
    <div class="intro-links">
      <a href="/projects/">View projects</a>
      <a href="/cv/">View CV</a>
      <a href="/contact/">Contact</a>
    </div>
  </div>
  <figure class="portrait-frame">{portrait_html}</figure>
</section>
<section class="section featured-section">
  <div class="section-heading">
    <p class="eyebrow">Selected work</p>
    <h2>Commercial Projects</h2>
  </div>
  <div class="featured-row">{featured}</div>
</section>
"""
    write(ROOT / "index.html", page("About", body, active="about"))


def meta_grid(project: Project) -> str:
    rows = [
        ("Location", project.info.location),
        ("Year", project.info.year),
        ("Role", project.info.role),
        ("Stage", project.info.stage),
    ]
    if project.info.contribution:
        rows.append(("Contribution", project.info.contribution))
    return "\n".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>" for label, value in rows if value
    )


def gallery_html(name: str, images: list[ImageAsset]) -> str:
    if not images:
        return ""
    items = "\n".join(
        f'<button class="gallery-item" type="button"><img src="{img.url}" alt="{html.escape(img.alt)}"></button>'
        for img in images
    )
    return f"""
<section class="project-section">
  <h2>{html.escape(name)}</h2>
  <div class="gallery-grid">{items}</div>
</section>"""


def design_process_html(project: Project) -> str:
    if not project.design_iterations:
        return ""
    tabs = []
    panels = []
    for index, (name, images) in enumerate(project.design_iterations.items()):
        tab_id = f"{project.slug}-tab-{index}"
        panel_id = f"{project.slug}-panel-{index}"
        tabs.append(
            f'<button class="{"active" if index == 0 else ""}" id="{tab_id}" type="button" role="tab" aria-controls="{panel_id}" aria-selected="{str(index == 0).lower()}">{html.escape(name)}</button>'
        )
        items = "\n".join(
            f'<button class="gallery-item" type="button"><img src="{img.url}" alt="{html.escape(img.alt)}"></button>'
            for img in images
        )
        panels.append(
            f'<div class="tab-panel {"active" if index == 0 else ""}" id="{panel_id}" role="tabpanel" aria-labelledby="{tab_id}"><div class="gallery-grid">{items}</div></div>'
        )
    return f"""
<section class="project-section design-process">
  <h2>Design Process</h2>
  <div class="tabs" role="tablist">{"".join(tabs)}</div>
  {"".join(panels)}
</section>"""


def build_project(project: Project, previous_project: Project | None, next_project: Project | None) -> None:
    section_order = ["Visualisations", "Photomontages", "Photos", "Drawings"]
    galleries = []
    for section in section_order:
        if section in project.sections:
            galleries.append(gallery_html(section, project.sections[section]))
    for section, images in project.sections.items():
        if section not in section_order:
            galleries.append(gallery_html(section, images))

    responsibilities = ""
    if project.info.responsibilities:
        responsibilities = "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in project.info.responsibilities) + "</ul>"

    prev_next = '<nav class="project-nav">'
    if previous_project:
        prev_next += f'<a href="/projects/{previous_project.category_slug}/{previous_project.slug}/">Previous: {html.escape(previous_project.display_name)}</a>'
    else:
        prev_next += "<span></span>"
    if next_project:
        prev_next += f'<a href="/projects/{next_project.category_slug}/{next_project.slug}/">Next: {html.escape(next_project.display_name)}</a>'
    else:
        prev_next += "<span></span>"
    prev_next += "</nav>"

    body = f"""
<article class="project-page">
  <section class="project-hero">
    <img src="{project.cover.url}" alt="{html.escape(project.display_name)}">
    <div>
      <p class="eyebrow">{html.escape(project.category)}</p>
      <h1>{html.escape(project.display_name)}</h1>
    </div>
  </section>
  <section class="project-info section">
    <dl>{meta_grid(project)}</dl>
    <div class="project-description">{paragraph_html(project.info.description)}</div>
  </section>
  {design_process_html(project)}
  {"".join(galleries)}
  <section class="project-section responsibilities">
    <h2>Key Responsibilities</h2>
    {responsibilities}
  </section>
  {prev_next}
</article>
"""
    write(ROOT / "projects" / project.category_slug / project.slug / "index.html", page(project.display_name, body, active="projects"))


def build_projects_index(projects: list[Project]) -> None:
    cards = "\n".join(project_card(project) for project in projects)
    body = f"""
<section class="section page-title">
  <p class="eyebrow">Projects</p>
  <h1>Selected architectural work</h1>
  <p>This first build focuses on the Commercial section. The same file-based structure will extend to Retail, Office Fit Out, Public and Residential once the design direction is approved.</p>
</section>
<section class="section filters" aria-label="Project categories">
  <a class="active" href="/projects/">All</a>
  <a class="active" href="/projects/">Commercial</a>
  <span>Retail</span>
  <span>Office Fit Out</span>
  <span>Public</span>
  <span>Residential</span>
</section>
<section class="section project-grid">{cards}</section>
"""
    write(ROOT / "projects" / "index.html", page("Projects", body, active="projects"))


def extract_cv_text() -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(CV_PDF))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def build_cv() -> None:
    text = extract_cv_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = []
    experience_index = 0
    for idx, line in enumerate(lines):
        if line == "Professional Experience":
            experience_index = idx
            break
        header.append(line)
    content_lines = lines[experience_index:] if experience_index else lines
    content = "\n".join(f"<p>{html.escape(line)}</p>" for line in content_lines)
    intro = "\n".join(f"<p>{html.escape(line)}</p>" for line in header[:8])
    body = f"""
<section class="section cv-page">
  <div class="cv-intro">
    <p class="eyebrow">CV</p>
    <h1>Lemi Hadarau</h1>
    {intro}
  </div>
  <div class="cv-content">{content}</div>
</section>
"""
    write(ROOT / "cv" / "index.html", page("CV", body, active="cv"))


def build_contact() -> None:
    text = read_text(CONTACT_FILE)
    email = re.search(r"Email:\s*\[?([^\]\s]+@[^\]\s]+)", text)
    phone = re.search(r"Phone:\s*([^\n]+)", text)
    location = re.search(r"Location:\s*([^\n]+)", text)
    linkedin = re.search(r"LinkedIn:\s*(https?://\S+)", text)
    body = f"""
<section class="section contact-page">
  <p class="eyebrow">Contact</p>
  <h1>Contact</h1>
  <p>For professional enquiries or opportunities, please contact me by email or phone.</p>
  <div class="contact-card">
    <p><strong>Email</strong><a href="mailto:{email.group(1) if email else 'lemuel_marius@yahoo.com'}?subject=Portfolio%20Enquiry">{email.group(1) if email else 'lemuel_marius@yahoo.com'}</a></p>
    <p><strong>Phone</strong><a href="tel:+353852218018">{phone.group(1).strip() if phone else '085 221 8018'}</a></p>
    <p><strong>Location</strong><span>{location.group(1).strip() if location else 'Ratoath, Co. Meath'}</span></p>
    <p><strong>LinkedIn</strong><a href="{linkedin.group(1) if linkedin else 'https://www.linkedin.com/in/lemi-hadarau-b8780a15a/'}" target="_blank" rel="noreferrer">LinkedIn</a></p>
  </div>
</section>
"""
    write(ROOT / "contact" / "index.html", page("Contact", body, active="contact"))


def clean_generated_pages() -> None:
    for path in [ROOT / "index.html", ROOT / "projects", ROOT / "cv", ROOT / "contact"]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    if GENERATED_ASSETS.exists():
        shutil.rmtree(GENERATED_ASSETS)


def main() -> None:
    clean_generated_pages()
    projects = load_projects()
    build_home(projects)
    build_projects_index(projects)
    for index, project in enumerate(projects):
        previous_project = projects[index - 1] if index > 0 else None
        next_project = projects[index + 1] if index + 1 < len(projects) else None
        build_project(project, previous_project, next_project)
    build_cv()
    build_contact()
    print(f"Built site with {len(projects)} Commercial projects.")


if __name__ == "__main__":
    main()
