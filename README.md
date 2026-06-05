# Lemi Website

Static, file-based architectural portfolio website for Lemi Hadarau.

## Current Build Scope

This first build includes:

- About / homepage
- Commercial projects
- CV page
- Contact page

Other project categories remain in the content folders and can be enabled after the Commercial design is approved.

## Run Locally

Use the bundled Python runtime in Codex or any Python environment with Pillow and pypdf installed:

```powershell
& 'C:\Users\mariu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_site.py
& 'C:\Users\mariu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m http.server 8080
```

Then open:

```text
http://localhost:8080
```

## Content Rules

- Folder numbers control order but are not displayed.
- Project display names come from bracketed folder names where available.
- Project pages are generated from each `Project Information.txt` file.
- Original images are not overwritten.
- Website image copies are generated into `assets/generated`.
- MPO-backed `.jpg` files are converted into standard JPEG only in generated site assets.

## Add A Commercial Project

1. Copy an existing Commercial project folder.
2. Rename it with a leading order number and display name in brackets.
3. Replace the project information text file.
4. Add a cover image in the project root.
5. Add optional `Drawings`, `Photos`, `Visualisations`, `Photomontage(s)` or `Design Iteration` folders.
6. Run `scripts\build_site.py`.
