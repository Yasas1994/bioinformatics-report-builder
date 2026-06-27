# Repository Guidelines

## Project Overview

A Quarto-based HTML report template and Python builder for UMG bioinformatics workflows (metagenomics, single-cell RNA-seq, spatial transcriptomics, multi-omics). The Python package writes a Quarto `.qmd` source plus CSS/sidebar/footer includes and an `assets/` folder; the user then runs `quarto render` to produce a standalone HTML report.

## Architecture & Data Flow

```mermaid
flowchart LR
    User["User code (Report + Section chain)"] -->|save()| QMD["output_dir/report.qmd"]
    QMD -->|include-in-header| Styles["output_dir/styles.html"]
    QMD -->|include-before-body| Sidebar["output_dir/sidebar.html"]
    QMD -->|include-after-body| Footer["output_dir/footer.html"]
    save -->|copies| Assets["output_dir/assets/ (figures, logos)"]
    User -->|shell| Quarto["quarto render output_dir/report.qmd --to html"]
    Quarto --> HTML["output_dir/report.html"]
```

- `Report` collects metadata, sections, and global settings.
- `Section` collects content items (metrics, tables, figures, code, references, etc.) using a fluent API.
- `Report.save(output_dir, filename="report.qmd")` writes:
  - `output_dir/report.qmd` — Quarto source whose body is a single ` ``````{=html}` raw block.
  - `output_dir/styles.html` — copied from `bioinformatics_report/templates/styles.html`.
  - `output_dir/sidebar.html` — generated dynamically with navigation, logo, and run metadata.
  - `output_dir/footer.html` — generated footer markup + static script from `templates/footer.html`.
  - `output_dir/assets/` — copies figures referenced via `add_figure()`.
- The rendered `report.html` links externally to `assets/` and Google Fonts (`embed-resources: false`), so the directory must stay together.

## Key Directories

| Directory | Purpose |
|---|---|
| `bioinformatics_report/` | Python package. `__init__.py` exports `Report`/`Section`; `report.py` contains the builder implementation; `templates/` holds Quarto extension and include files. |
| `bioinformatics_report/templates/` | Source assets for generated reports and the Quarto extension. `styles.html` is copied verbatim by `save()`; `sidebar.html`/`footer.html` are templates/fragments; `template.qmd` and `_extension.yml` are for manual/extension use only. |
| `examples/` | Workflow example scripts that generate placeholder figures and reports for four bioinformatics domains. |
| `examples/out/` | Generated report directories (`.qmd`, `.html`, `assets/`). Listed in `.gitignore`; currently checked in. |

## Development Commands

```bash
# Editable install
pip install -e .

# Optional: figure generation for examples
pip install matplotlib numpy

# Run example scripts (from examples/)
cd examples
python metagenomics_report.py
python single_cell_report.py
python spatial_transcriptomics_report.py
python multi_omics_report.py

# Render one report
quarto render examples/out/metagenomics/metagenomics_report.qmd --to html

# Render all generated reports
for f in examples/out/*/*.qmd; do quarto render "$f" --to html; done

# Build a wheel
python -m build
```

## Code Conventions & Common Patterns

- **Fluent API**: most `Report`/`Section` methods return `self`. Example:
  ```python
  report.set_metadata([("Date", "2026-06-26"), ("Samples", "n = 48")])
  section = report.add_section("01", "Summary")
  section.set_overview("...").add_metrics([...]).add_table(...)
  ```
- **Return exceptions**: `Report.add_section()` returns the new `Section`, not `self`, so chains switch to the section object.
- **Dataclasses for content items**: `_SubSection`, `_Metric`, `_Figure`, `_Table`, `_Notice`, `_Code` are stored in `Section.items` and rendered by `_render_item`.
- **Typing**: `from __future__ import annotations`, `pathlib.Path`, `typing.Any/Iterable/Sequence`.
- **HTML escaping**: user-facing strings are passed through `html.escape()`; `Section.add_raw()` and `Section.add_latex()` are the exceptions that insert raw content (HTML or MathJax-delimited TeX).
- **Slug generation**: `Section._slug()` lowercases, collapses non-alphanumerics to `-`, and falls back to `"section"`.
- **Path handling**: output paths use `expanduser().resolve()`; asset references use `Path(src).name`.
- **Sync only**: no async code.
- **LaTeX math**: `Section.add_latex(tex, display=False)` emits `\( ... \)` inline or `\[ ... \]` display math. `Report.save()` detects LaTeX items, writes a `mathjax.html` include, and adds it to the Quarto header so MathJax renders the expressions.
- **Error handling**: minimal and silent — missing figure/logo files are skipped rather than raising.
- **No runtime validation**: incorrect inputs are generally accepted and may only fail later during Quarto rendering.

## Important Files

| File | Purpose |
|---|---|
| `bioinformatics_report/__init__.py` | Package entry point; exports `Report`, `Section`, defines `__version__`. |
| `bioinformatics_report/report.py` | Core builder: `Report`, `Section`, private dataclasses, rendering, asset copying, `save()`. |
| `bioinformatics_report/templates/styles.html` | Embedded CSS include; copied into every generated report. |
| `bioinformatics_report/templates/sidebar.html` | Static sidebar markup/JS fragment used as a base for generated sidebars. |
| `bioinformatics_report/templates/footer.html` | Closing `</main>` and scroll-spy/toggle script appended to generated footers. |
| `bioinformatics_report/templates/template.qmd` | Manual `.qmd` example showing frontmatter and CSS-class-based layout. Not used by the Python builder. |
| `bioinformatics_report/templates/_extension.yml` | Quarto extension manifest; not read by the Python builder. |
| `bioinformatics_report/templates/bioinformatics-report.css` | Stylesheet referenced by the Quarto extension only. |
| `pyproject.toml` | PEP 621 project metadata and setuptools build configuration. |
| `Unimed_logo.svg` | Logo embedded inline in generated sidebars. |

## Runtime/Tooling Preferences

- **Python**: `>=3.10` (declared in `pyproject.toml` and README).
- **Quarto**: `>=1.4` required; checked-in HTML outputs were generated with Quarto `1.8.26`.
- **Package manager**: `pip` (standard Python packaging).
- **Build system**: `setuptools>=61.0` + `wheel`; no `setup.py`/`setup.cfg`/`MANIFEST.in`.
- **Runtime dependencies**: none.
- **Optional dev dependencies**: `matplotlib`, `numpy` (used by examples for placeholder figures).
- **No configured linters/formatters/type-checkers**: only a stale `.ruff_cache/` exists; no `ruff.toml`, `[tool.ruff]`, `pytest`, `mypy`, or pre-commit config is present.

## Testing & QA

- **No automated test suite exists.** There is no `tests/` directory, no `test_*.py`, no `pytest.ini`, no CI/CD configuration, and no coverage tooling.
- **Validation workflow**: run the four example scripts and render their `.qmd` outputs with Quarto to confirm the builder still emits valid reports.
  ```bash
  cd examples
  python metagenomics_report.py
  python single_cell_report.py
  python spatial_transcriptomics_report.py
  python multi_omics_report.py
  for f in out/*/*.qmd; do quarto render "$f" --to html; done
  ```
- **Gaps to watch when editing**: `Report.save()` output structure, `_slug()` edge cases, HTML escaping behavior, figure asset copying, and Quarto frontmatter correctness.
