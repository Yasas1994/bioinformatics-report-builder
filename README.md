# Bioinformatics Report Template

A general-purpose, Quarto-based HTML report template and a Python builder for
bioinformatics workflows (metagenomics, single-cell RNA-seq, spatial
transcriptomics, multi-omics, etc.).

The template provides a clean, branded report layout (sticky sidebar navigation,
masthead metadata ledger, metric strips, tables, minimal bar charts, figure
boxes, code blocks and references) and produces a standalone HTML file. Figures
are kept as linked files in an `assets/` directory. The company or institution
logo is fully configurable.

## Repository layout

```
.
├── bioinformatics_report/       # Python package
│   ├── __init__.py
│   ├── report.py                # Report and Section builder classes
│   └── templates/               # Quarto extension files
│       ├── _extension.yml
│       ├── bioinformatics-report.css
│       ├── styles.html          # embedded CSS include
│       ├── sidebar.html         # default sidebar with generic logo placeholder
│       ├── footer.html          # closing </main> + navigation script
│       └── template.qmd         # manual Quarto template
├── examples/                    # workflow examples
│   ├── assets/                  # example logos and other static assets
│   │   └── Unimed_logo.svg
│   ├── metagenomics_report.py
│   ├── single_cell_report.py
│   ├── spatial_transcriptomics_report.py
│   ├── multi_omics_report.py
│   └── generic_company_report.py
└── pyproject.toml
```

## Installation

### Prerequisites

- Python **≥3.10**
- [Quarto](https://quarto.org) **≥1.4**

Install Quarto from <https://quarto.org/docs/get-started/>. Verify the
installation from a terminal:

```bash
quarto --version   # should be 1.4 or newer
python --version   # should be 3.10 or newer
```

### Install the package

From the repository root:

```bash
pip install -e .
```

For development (linting, formatting, type-checking):

```bash
pip install -e ".[dev,test]"
```

Optional runtime packages used by the bundled examples:

```bash
pip install matplotlib numpy
```

Optional package for `Section.add_markdown()`:

```bash
pip install markdown
```

### Verify the installation

```bash
python -c "from bioinformatics_report import Report, Section; print('OK')"
bioinformatics-report --help
```

## Quick start

1. **Create a Python script** (e.g. `my_report.py`):

```python
from bioinformatics_report import Report

report = Report(
    title_line1="Phage Genomics",
    title_line2="Classification Report",
    date="2026-06-27",
    footer_left="Generated on 2026-06-27",
    footer_right="My Lab",
)

report.set_metadata([
    ("Date", "2026-06-27"),
    ("Samples", "48"),
    ("Contigs", "14,382"),
])

summary = report.add_section("01", "Executive Summary")
summary.set_overview("All 48 samples processed successfully.")
summary.add_metrics([
    {"label": "Contigs", "value": "14,382", "sub": "across 48 samples", "highlight": True},
    {"label": "Mean Length", "value": "28.4 kb", "sub": "N50 = 41.2 kb"},
])

report.save("my_report", filename="report.qmd")
```

2. **Run the script**:

```bash
python my_report.py
```

This writes `my_report/report.qmd`, `my_report/styles.html`,
`my_report/sidebar.html`, `my_report/footer.html` and the `my_report/assets/`
directory.

3. **Render to HTML**:

```bash
quarto render my_report/report.qmd --to html
```

Open `my_report/report.html` in a browser.

### Switch the company logo

SVG logos are embedded inline; PNG/JPG logos are copied to `assets/`.

```python
from pathlib import Path
from bioinformatics_report import Report

report = Report(title_line1="Quarterly", title_line2="Business Report")
report.set_logo(
    Path("path/to/my-logo.svg"),
    alt="My Company",
    width="180px",
    height="auto",
)
```

Omit `set_logo()` (or pass `None`) to show a generic "Your Logo" placeholder.

## Builder API

### `Report`

```python
Report(
    title_line1: str = "",
    title_line2: str = "",
    pipeline: str = "",
    operator: str = "",
    reference: str = "",
    cluster: str = "",
    date: str | None = None,
    run_label: str = "",
    run_status: str = "",
    run_label_prefix: str = "pipeline",
    sidebar_footer: str = "",
    logo_path: str | Path | None = None,
    logo_alt: str = "",
    logo_width: str = "160px",
    logo_height: str = "auto",
    footer_left: str = "",
    footer_right: str = "",
    extra_css: str | Path | None = None,
    mathjax_url: str | None = None,
    offline_mathjax: bool = False,
)
```

| Parameter | Description |
|-----------|-------------|
| `title_line1`, `title_line2` | Two-line masthead title. |
| `pipeline`, `operator`, `reference`, `cluster` | Optional masthead metadata labels. |
| `date` | Date string; defaults to today. |
| `run_label` | Label shown in the sidebar under `run_label_prefix`. |
| `run_status` | Smaller status text shown under `run_label`. |
| `run_label_prefix` | Small header above `run_label`; default `"pipeline"`. |
| `sidebar_footer` | Status text at the bottom of the sidebar. |
| `logo_path` | Path to an SVG, PNG or JPG logo. |
| `logo_alt` | Accessible `alt` text for non-SVG logos. |
| `logo_width`, `logo_height` | Logo size in the sidebar. |
| `footer_left`, `footer_right` | Text in the page footer. |
| `extra_css` | Path to a CSS file or raw CSS text included in the report. |
| `mathjax_url` | Override the MathJax URL used for LaTeX rendering. |
| `offline_mathjax` | Copy a local MathJax `tex-chtml.js` to `assets/` if found. |

#### `Report` methods

| Method | Returns | Description |
|--------|---------|-------------|
| `set_metadata(items)` | `Report` | Set the masthead metadata ledger from a sequence of `(key, value)` pairs. |
| `add_section(number, title, count="")` | `Section` | Add a new section and return it for chaining. |
| `set_logo(path, alt=None, width=None, height=None)` | `Report` | Configure or swap the sidebar logo. Pass `None` for the placeholder. |
| `set_sidebar_footer(text)` | `Report` | Set the bottom-of-sidebar status text. |
| `set_run_label_prefix(text)` | `Report` | Set the small label shown above `run_label`. |
| `save(output_dir, filename="report.qmd", assets_dir="assets")` | `Path` | Write the `.qmd`, include files and assets; returns the path to the `.qmd`. |

### `Section`

Returned by `Report.add_section()`. All content methods return `self` for
chaining.

| Method | Description |
|--------|-------------|
| `set_overview(text)` | Set the section overview paragraph. |
| `add_metrics(metrics)` | Add a strip of metric cards. Each dict may contain `label`, `value`, `sub`, `highlight`. |
| `add_subsection(title, anchor=None)` | Add a subsection heading with an anchor for the sidebar. |
| `add_text(text)` | Add a plain paragraph (HTML-escaped). |
| `add_notice(tag, text, kind="info" \| "warn")` | Add an info/warn notice strip. |
| `add_table(headers, rows, caption="", col_classes=..., cell_classes=...)` | Add a data table. `cell_classes` should have the same shape as `rows`. |
| `add_freq_bars(data, low_threshold=15.0)` | Add a minimal horizontal bar chart from `(label, percent)` tuples. |
| `add_figure(path, caption, label=None)` | Reference a figure; the file is copied to `assets/`. |
| `add_code(language, code)` | Add a styled code block. |
| `add_latex(tex, display=False)` | Add inline or display LaTeX. MathJax is loaded automatically. |
| `add_references(citations)` | Add a numbered reference list. |
| `add_list(items, ordered=False)` | Add a bulleted or numbered list. |
| `add_markdown(text)` | Add Markdown content rendered to HTML (requires the `markdown` package). |
| `add_download(path, label=None)` | Add a download link; the file is copied to `assets/`. |
| `add_citation_link(text, url)` | Add a citation paragraph linking to an external URL. |
| `add_raw(html_fragment)` | Insert arbitrary raw HTML (not escaped). |

## Customizing the logo

Pass any SVG, PNG or JPG to `Report(logo_path=...)`:

```python
from pathlib import Path
from bioinformatics_report import Report

report = Report(
    title_line1="My Study",
    title_line2="Analysis Report",
    logo_path=Path("path/to/my-logo.svg"),
    logo_alt="My Company",
    logo_width="160px",
    logo_height="auto",
)
```

You can also change the logo (and its size/alt text) fluently after construction
with `Report.set_logo()`:

```python
report = Report(title_line1="Quarterly", title_line2="Business Report")
report.set_logo(Path("path/to/my-logo.svg"), alt="My Company", width="180px")
```

- **SVG** logos are embedded inline in the sidebar (best quality and small file size).
  Fixed `width`/`height` attributes on the root `<svg>` tag are removed automatically
  so the logo scales to the configured `logo_width`/`logo_height`.
- **PNG/JPG** logos are copied into the report `assets/` folder and referenced with an `<img>` tag.
- `logo_alt` sets the image `alt` text for accessibility.
- If `logo_path` is omitted, a generic placeholder box is shown in the sidebar.

When using the manual `.qmd` workflow, replace the placeholder `<svg>` in `sidebar.html` with your own logo markup.

## General-purpose sidebar options

For reports outside of bioinformatics workflows, the sidebar labels and footer
are configurable:

```python
report = Report(
    title_line1="Quarterly",
    title_line2="Business Report",
    run_label="FY2026 · Q2",
    run_label_prefix="report",      # label shown above run_label; default is "pipeline"
    sidebar_footer="Report ready",  # status text at the bottom of the sidebar
)
```

## Common tasks

### Hide the sidebar status footer

Leave `sidebar_footer` empty (the default) and the footer block is omitted:

```python
report = Report(title_line1="Minimal", title_line2="Report")
```

### Add a custom stylesheet

Pass a CSS file path or raw CSS text:

```python
report = Report(
    title_line1="My Report",
    title_line2="With custom colors",
    extra_css=".masthead { background: #f0f4fa; }",
)
```

### Include LaTeX math

```python
section = report.add_section("02", "Math")
section.add_latex(r"x^2 + y^2 = z^2")          # inline
section.add_latex(r"\int_0^1 x dx", display=True)  # display
```

MathJax is included automatically when any LaTeX item is present.

## Workflow examples

Generate all example reports:

```bash
cd examples
python metagenomics_report.py
python single_cell_report.py
python spatial_transcriptomics_report.py
python multi_omics_report.py
python generic_company_report.py
```

Then render each one:

```bash
for f in out/*/*.qmd; do quarto render "$f" --to html; done
```

The `generic_company_report.py` example demonstrates a non-bioinformatics use
case and shows how to switch the company logo at runtime with
`Report.set_logo()`.

## Manual use with a `.qmd` template

You can also write a `.qmd` directly. Copy the template files from
`bioinformatics_report/templates/` (`styles.html`, `sidebar.html`, `footer.html`)
into your project and use the frontmatter shown in
`bioinformatics_report/templates/template.qmd`:

```yaml
---
title: "My Analysis"
format:
  html:
    toc: false
    theme: none
    page-layout: custom
    include-in-header: styles.html
    include-before-body: sidebar.html
    include-after-body: footer.html
    embed-resources: false
    link-color: '#264882'
---
```

The body of `template.qmd` shows the CSS classes and raw-HTML layout used by the builder.

## Development commands

```bash
# Run tests
pytest

# Lint and typecheck
ruff check bioinformatics_report tests
ruff format --check bioinformatics_report tests
mypy bioinformatics_report
```

## License

MIT – Kaderali Lab, Universitätsmedizin Greifswald.
