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
CV_FILE = ROOT / "2 CV" / "Lemi_Hadarau_CV.docx"
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
class BeforeAfterPair:
    title: str
    existing: ImageAsset
    proposed: ImageAsset
    orientation: str


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
    before_after: list[BeforeAfterPair]
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


def before_after_marker(path: Path) -> str:
    if re.search(r"\bexisting\b", path.stem, re.IGNORECASE):
        return "existing"
    if re.search(r"\bproposed\b", path.stem, re.IGNORECASE):
        return "proposed"
    return ""


def before_after_key(path: Path) -> str:
    key = re.sub(r"\b(existing|proposed)\b", "", path.stem, flags=re.IGNORECASE)
    key = re.sub(r"\b\d+\b", "", key)
    key = re.sub(r"[-_]+", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key or path.parent.name


def photomontage_before_after(section_path: Path) -> tuple[list[BeforeAfterPair], list[Path]]:
    pairs: list[BeforeAfterPair] = []
    used: set[Path] = set()

    def pair_orientation(existing: Path, proposed: Path) -> str:
        with Image.open(existing) as existing_image, Image.open(proposed) as proposed_image:
            width = min(existing_image.width, proposed_image.width)
            height = min(existing_image.height, proposed_image.height)
        return "portrait" if height > width else "landscape"

    for folder in sorted([p for p in section_path.iterdir() if p.is_dir()], key=lambda p: natural_key(p.name)):
        files = image_files(folder)
        existing = next((p for p in files if before_after_marker(p) == "existing"), None)
        proposed = next((p for p in files if before_after_marker(p) == "proposed"), None)
        if existing and proposed:
            pairs.append(
                BeforeAfterPair(
                    title=strip_leading_number(folder.name),
                    existing=optimize_image(existing),
                    proposed=optimize_image(proposed),
                    orientation=pair_orientation(existing, proposed),
                )
            )
            used.update({existing, proposed})

    flat_groups: dict[str, dict[str, Path]] = {}
    for file in direct_image_files(section_path):
        marker = before_after_marker(file)
        if not marker:
            continue
        flat_groups.setdefault(before_after_key(file), {})[marker] = file

    for key, group in sorted(flat_groups.items(), key=lambda item: natural_key(item[0])):
        existing = group.get("existing")
        proposed = group.get("proposed")
        if existing and proposed and existing not in used and proposed not in used:
            pairs.append(
                BeforeAfterPair(
                    title=key,
                    existing=optimize_image(existing),
                    proposed=optimize_image(proposed),
                    orientation=pair_orientation(existing, proposed),
                )
            )
            used.update({existing, proposed})

    loose_images = [p for p in image_files(section_path) if p not in used]
    return pairs, loose_images


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
            before_after: list[BeforeAfterPair] = []
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

                if section_path.name.lower().startswith("photomontage"):
                    before_after, loose_images = photomontage_before_after(section_path)
                    if loose_images:
                        sections["Photomontages"] = [optimize_image(img) for img in loose_images]
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
                    before_after=before_after,
                    design_iterations=design_iterations,
                )
            )
    return projects


def page(title: str, body: str, active: str = "", body_class: str = "") -> str:
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
  <link rel="stylesheet" href="/assets/css/styles.css?v=quiet-motion-2">
  <script src="/assets/js/site.js?v=quiet-motion-2" defer></script>
</head>
<body{f' class="{html.escape(body_class)}"' if body_class else ''}>
  <header class="site-header">
    <a class="brand" href="/">Lemi Hadarau</a>
    <nav aria-label="Main navigation">{nav_html}</nav>
  </header>
  <main>{body}</main>
  <footer class="site-footer">
    <span>Lemi Hadarau</span>
    <span>Registered Architect MRIAI</span>
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
  <h1 class="about-heading">About</h1>
  <figure class="portrait-frame">
    {portrait_html}
    <figcaption>
      <strong>Lemi Hadarau</strong>
      <span>Registered Architect MRIAI</span>
    </figcaption>
  </figure>
  <div class="intro-content">
    <div class="intro-copy">{paragraph_html(about)}</div>
    <div class="intro-links">
      <a href="/projects/">View projects</a>
      <a href="/cv/">View CV</a>
      <a href="/contact/">Contact</a>
    </div>
  </div>
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


def before_after_html(pairs: list[BeforeAfterPair]) -> str:
    if not pairs:
        return ""
    tabs = []
    panels = []
    for index, pair in enumerate(pairs):
        tab_id = f"before-after-tab-{index}"
        panel_id = f"before-after-panel-{index}"
        tabs.append(
            f'<button class="{"active" if index == 0 else ""}" id="{tab_id}" type="button" role="tab" aria-controls="{panel_id}" aria-selected="{str(index == 0).lower()}">{html.escape(pair.title)}</button>'
        )
        panels.append(
            f"""
  <div class="tab-panel {"active" if index == 0 else ""}" id="{panel_id}" role="tabpanel" aria-labelledby="{tab_id}">
    <figure class="before-after before-after-{html.escape(pair.orientation)}" style="--before-after-position: 50%">
      <div class="before-after-media">
        <img src="{pair.existing.url}" alt="{html.escape(pair.existing.alt)}">
        <div class="before-after-overlay">
          <img src="{pair.proposed.url}" alt="{html.escape(pair.proposed.alt)}">
        </div>
        <span class="before-after-label before-after-label-existing">Existing</span>
        <span class="before-after-label before-after-label-proposed">Proposed</span>
        <div class="before-after-divider" aria-hidden="true"><span></span></div>
        <input class="before-after-range" type="range" min="0" max="100" value="50" aria-label="{html.escape(pair.title)} before and after comparison">
      </div>
    </figure>
  </div>"""
        )
    return f"""
<section class="project-section before-after-section tabbed-section">
  <h2>Photomontages</h2>
  <div class="tabs" role="tablist">{"".join(tabs)}</div>
  {"".join(panels)}
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
<section class="project-section design-process tabbed-section">
  <h2>Design Process</h2>
  <div class="tabs" role="tablist">{"".join(tabs)}</div>
  {"".join(panels)}
</section>"""


def build_project(project: Project, previous_project: Project | None, next_project: Project | None) -> None:
    section_order = ["Visualisations", "Photomontages", "Photos", "Drawings"]
    galleries = []
    if project.before_after:
        galleries.append(before_after_html(project.before_after))
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
    body_class = "lightbox-thumbs-prototype" if project.category_slug == "commercial" else ""
    write(ROOT / "projects" / project.category_slug / project.slug / "index.html", page(project.display_name, body, active="projects", body_class=body_class))


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
        if CV_FILE.suffix.lower() == ".docx":
            from docx import Document

            document = Document(str(CV_FILE))
            lines: list[str] = []
            for paragraph in document.paragraphs:
                lines.extend(line.strip() for line in paragraph.text.splitlines() if line.strip())
            return "\n".join(lines)

        from pypdf import PdfReader

        reader = PdfReader(str(CV_FILE))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def merge_wrapped_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    current = ""
    for line in lines:
        if line.startswith("•"):
            if current:
                bullets.append(current)
            current = line.lstrip("• ").strip()
        elif current:
            current += " " + line
        else:
            bullets.append(line)
    if current:
        bullets.append(current)
    return bullets


def list_html(items: Iterable[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items if item.strip()) + "</ul>"


def cv_timeline_item(year: str, period: str, title: str, meta: str, bullets: list[str]) -> str:
    return f"""
<article class="cv-timeline-item">
  <div class="cv-year">{html.escape(year)}</div>
  <div class="cv-marker" aria-hidden="true"></div>
  <div class="cv-entry">
    <p class="cv-period">{html.escape(period)}</p>
    <h3>{html.escape(title)}</h3>
    <p class="cv-meta">{html.escape(meta)}</p>
    {list_html(bullets)}
  </div>
</article>
"""


def cv_block(number: str, title: str, content: str, extra_class: str = "") -> str:
    classes = "cv-block" + (f" {extra_class}" if extra_class else "")
    return f"""
<section class="{classes}">
  <div class="cv-block-heading">
    <span>{html.escape(number)}</span>
    <h2>{html.escape(title)}</h2>
  </div>
  {content}
</section>
"""


def build_cv() -> None:
    name = "Lemi Hadarau"
    qualification = "Registered Architect MRIAI"
    location = "Dublin, Ireland"
    licence = "Full driving licence"
    email = "lemuel_marius@yahoo.com"
    phone = "085 221 8018"

    experience = "".join([
        cv_timeline_item("2024", "Jun 2024 - Present", "Project Architect", "NODE Architecture, Dublin 2 · Full-time", [
            "Act as Project Architect on multiple retail, commercial, and office fit-out projects, managing contract administration, day-to-day coordination, programme, and communication with clients, consultants, and contractors",
            "Lead coordination on the Toyota National Retail Concept rollout, involving 43 dealerships upgrade projects across Ireland, including signage, joinery, A/V, internal upgrades and external facade works",
            "Prepare and manage planning applications, H&S documentation, tender and construction packages",
            "Prepare and coordinate Fire Safety Certificate and Disability Access Certificate applications, including preparation of drawings and documentation",
            "Produce 3D models, CGI renderings, and presentations to support design development, planning submissions, and client approvals",
            "Coordinate multidisciplinary teams including QS, M&E, structural engineers, and specialist subcontractors",
            "Oversee site progress, attend site meetings and carry out site inspections, coordinate works during construction and resolve technical queries",
            "Review contractor progress claims and assist with reviewing/signing off payment certificates in coordination with the QS/Director",
            "Carry out snagging inspections, prepare snag lists, and coordinate completion items through to handover",
            "Review, coordinate, and sign off contractor and specialist subcontractor shop drawings/submittals",
            "Assist with BCAR/BCMS documentation and inspections, including coordination of required certificates, compliance documentation, and completion-stage information",
            "Support project close-out, handover documentation, and completion-stage coordination",
            "Support internal IT, workstation setup, software troubleshooting, and workflow improvements to improve office efficiency",
            "Support and mentor architectural graduates in the office",
        ]),
        cv_timeline_item("2021", "Jul 2021 - May 2024", "Architectural Graduate (Part II)", "NODE Architecture, Dublin 2", [
            "Worked closely with one of the Directors on high end residential and commercial projects across planning, tender, and construction stages",
            "Produced 3D models, CGI renderings, photomontages and visual presentation material to support design development, planning applications, and client presentations",
            "Assisted with planning applications for one-off houses, domestic extensions, and residential refurbishment projects",
            "Produced planning drawings, tender packages, construction drawings, and supporting documentation, coordinating with structural and M&E input",
            "Assisted with site inspections, meeting notes, and contract administration during construction stages",
            "Gained strong experience in Irish planning processes, residential design, and technical detailing",
            "Contributed to the practice's marketing and digital presence, including social media content management, updating the website with new projects, and photographing completed projects for marketing use",
        ]),
        cv_timeline_item("2018", "Oct 2018 - Aug 2019", "Architectural Assistant (Part I)", "NODE Architecture, Dublin 2", [
            "Worked closely with Directors and senior architects on a range of residential, commercial, and student accommodation projects",
            "Assisted with design development, planning applications, and project documentation",
            "Prepared architectural drawings, 3D models, CGI visualisations, and presentation material for design development and client presentations",
            "Assisted on the redevelopment of a former B&B into student accommodation on Stillorgan Road, including revised planning, FSC, DAC and construction drawings",
            "Gained early experience in local authority processes, planning and building regulations, and communication with contractors and wider design teams",
        ]),
    ])

    digital_workflow_bullets = [
        "Strong working knowledge of PC hardware, software setup, troubleshooting, and workstation configuration",
        "Researched, specified, purchased, and set up 4 new architectural workstations over the past three years, balancing performance requirements, office work needs, and budget",
        "Prepared and configured workstations for new employees, including software installation, peripherals, and general setup",
        "Liaising with external IT providers and advising on hardware specifications for CAD and visualisation work",
        "Carried out regular maintenance, hardware/software upgrades, and performance troubleshooting to improve office efficiency",
        "Supported the practice's digital presence through website content updates, social media content coordination, project photography and marketing material preparation",
    ]

    education_entries = [
        ("2026", "Commencing Sept 2026", "Certificate in Building Information Modelling - Architecture", "Atlantic Technological University", "NFQ Level 8 · In progress · Expected 2027"),
        ("2022", "Sept 2022 - May 2024", "Postgraduate Diploma in Architectural Practice (PDAP)", "Technological University Dublin", ""),
        ("2019", "Sept 2019 - Sept 2021", "Master of Architecture (M.Arch)", "University College Dublin", ""),
        ("2015", "Sept 2015 - Sept 2018", "Bachelor of Science (BSc) in Architectural Science", "University College Dublin", "UCD Entrance Scholar - University College Dublin, 2015<br>Awarded to high-achieving students based on 2014/2015 academic results (580 CAO points)"),
    ]
    education = "".join(
        f"""
<article class="cv-mini-entry">
  <span>{html.escape(year)}</span>
  <div>
    <p>{html.escape(period)}</p>
    <h3>{html.escape(title)}</h3>
    <p class="cv-institution">{html.escape(place)}</p>
    {f'<p class="cv-entry-note">{note}</p>' if note else ''}
  </div>
</article>
"""
        for year, period, title, place, note in education_entries
    )

    skills = f"""
<div class="cv-skills-matrix">
  <div class="cv-skill-group">
    <h3>Software</h3>
    <div class="cv-skill-cards cv-skill-cards-two">
      <article>
        <h4>Design &amp; Visualisation</h4>
        {list_html(["AutoCAD", "SketchUp", "Lumion", "Adobe Creative Cloud (Photoshop, InDesign, Illustrator)", "Revit (basic)", "Vectorworks (basic)"])}
      </article>
      <article>
        <h4>Project Delivery &amp; Collaboration</h4>
        {list_html(["Microsoft Office 365", "Teams", "SharePoint", "Procore", "Fieldwire"])}
      </article>
    </div>
  </div>
  <div class="cv-skill-group">
    <h3>Professional Skills</h3>
    <div class="cv-skill-cards">
      <article>
        <h4>Project Delivery</h4>
        {list_html(["Design Development", "Planning applications", "Tender & construction documentation", "FSC / DAC applications", "BCAR / BCMS", "Contract administration", "Site inspections", "Snagging & project handover"])}
      </article>
      <article>
        <h4>Coordination &amp; Communication</h4>
        {list_html(["Project coordination", "Consultant coordination", "Clear client & stakeholder communication", "Main contractor liaison", "Team collaboration", "Follow-up and action tracking"])}
      </article>
      <article>
        <h4>Technical &amp; Quality</h4>
        {list_html(["Adaptability & continuous learning", "Practical problem-solving", "Technical detailing", "Accuracy & attention to details", "CGI & 3D visualisation", "Programme and cost awareness"])}
      </article>
    </div>
  </div>
</div>
"""
    body = f"""
<section class="section cv-page cv-redesign">
  <header class="cv-identity">
    <p class="eyebrow">CV</p>
    <h1>{html.escape(name)}</h1>
    <p class="cv-role">{html.escape(qualification)}</p>
    <div class="cv-contact-lines">
      <p>{html.escape(location)}<br>{html.escape(licence)}</p>
      <p class="cv-contact-list">
        <span><span class="cv-contact-icon" aria-hidden="true">✉</span><a href="mailto:{html.escape(email)}">{html.escape(email)}</a></span>
        <span><span class="cv-contact-icon cv-contact-icon-phone" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M6.5 3.2 4.3 5.4c-.7.7-.9 1.7-.5 2.6 2.4 4.9 6.3 8.8 11.2 11.2.9.4 1.9.2 2.6-.5l2.2-2.2c.5-.5.5-1.2 0-1.7l-3.1-3.1c-.4-.4-1.1-.5-1.6-.2l-1.8 1c-1.8-1.1-3.4-2.7-4.5-4.5l1-1.8c.3-.5.2-1.2-.2-1.6L8.2 3.2c-.5-.5-1.2-.5-1.7 0z"/></svg></span>{html.escape(phone)}</span>
      </p>
    </div>
    <a class="cv-download" href="/2%20CV/{html.escape(CV_FILE.name)}" target="_blank" rel="noopener">Download CV</a>
  </header>
  <div class="cv-layout">
    <aside class="cv-left-column">
      {cv_block("01", "Professional Experience", f'<div class="cv-timeline">{experience}</div>')}
    </aside>
    <div class="cv-right-column">
      {cv_block("02", "Education", education)}
      {cv_block("03", "Additional Digital Workflows", list_html(digital_workflow_bullets), "cv-compact")}
      {cv_block("04", "Skills", skills, "cv-skills-full")}
    </div>
  </div>
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
  <h1>Contact</h1>
  <p>For professional enquiries or opportunities, please contact me by email or phone.</p>
  <div class="contact-card">
    <p><strong>Email</strong><a href="mailto:{email.group(1) if email else 'lemuel_marius@yahoo.com'}?subject=Portfolio%20Enquiry">{email.group(1) if email else 'lemuel_marius@yahoo.com'}</a></p>
    <p><strong>Phone</strong><a href="tel:+353852218018">{phone.group(1).strip() if phone else '085 221 8018'}</a></p>
    <p><strong>Location</strong><span>{location.group(1).strip() if location else 'Ratoath, Co. Meath'}</span></p>
    <p><strong>LinkedIn</strong><a href="{linkedin.group(1) if linkedin else 'https://www.linkedin.com/in/lemi-hadarau-b8780a15a/'}" target="_blank" rel="noreferrer">Lemi Hadarau</a></p>
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
