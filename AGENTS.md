# Repository Guidelines

## Project Overview

A general-purpose Quarto-based HTML report template and Python builder for bioinformatics workflows (metagenomics, single-cell RNA-seq, spatial transcriptomics, multi-omics). The Python package writes a Quarto `.qmd` source plus CSS/sidebar/footer includes and an `assets/` folder; the user then runs `quarto render` to produce a standalone HTML report. The logo, footer text, and color scheme are fully configurable.

## Architecture & Data Flow

```mermaid
flowchart LR
    User["User code (Report + Section chain)"] -->|save()| QMD["output_dir/report.qmd"]
    QMD -->|include-in-header| Styles["output_dir/styles.html"]
    QMD -->|include-before-body| Sidebar["output_dir/sidebar.html"]
    QMD -->|include-after-body| Footer["output_dir/footer.html"]
    save -->|copies| Assets["output_dir/assets/ (figures, logos, downloads)"]
    User -->|shell or CLI| Quarto["quarto render output_dir/report.qmd --to html"]
    Quarto --> HTML["output_dir/report.html"]
```

- `Report` collects metadata, sections, and global settings.
- `Section` collects content items (metrics, tables, figures, code, references, etc.) using a fluent API.
- Each content item implements a `_Renderable` protocol; `Section._render()` dispatches by calling `item.render(...)`.
- `Report.save()` writes:
  - `output_dir/report.qmd`
  - `output_dir/styles.html`
  - `output_dir/sidebar.html` (generated with logo, navigation, run metadata)
  - `output_dir/footer.html`
  - `output_dir/assets/` (copied figures and download files)
  - `output_dir/mathjax.html` (only when LaTeX is present)
  - `output_dir/custom.css` (only when `extra_css` is set)
- `bioinformatics-report render <qmd> --to html|pdf` wraps `quarto render`.

## Key Directories

| Directory | Purpose |
|---|---|
| `bioinformatics_report/` | Python package. `__init__.py` exports `Report`/`Section`; `report.py` contains the builder; `cli.py` contains the CLI; `templates/` holds Quarto extension/include files. |
| `bioinformatics_report/templates/` | Source assets for generated reports and the Quarto extension. `styles.html` is copied verbatim by `save()`; `sidebar.html` contains a generic logo placeholder for manual use; `template.qmd`/`_extension.yml` are for manual/extension use only. |
| `examples/` | Workflow example scripts that generate placeholder figures and reports for four bioinformatics domains. |
| `examples/assets/` | Example static assets, including the UMG/Unimed logo. |
| `examples/out/` | Generated report directories (`.qmd`, `.html`, `assets/`). Listed in `.gitignore`; not tracked. |
| `tests/` | pytest test suite. |
| `.github/workflows/` | GitHub Actions CI. |

## Development Commands

```bash
# Editable install with all optional deps
pip install -e ".[dev,test]"

# Run tests
pytest

# Lint and typecheck
ruff check bioinformatics_report tests
ruff format --check bioinformatics_report tests
mypy bioinformatics_report

# Run example scripts (from examples/)
cd examples
python metagenomics_report.py
python single_cell_report.py
python spatial_transcriptomics_report.py
python multi_omics_report.py

# Render via Quarto directly
quarto render examples/out/metagenomics/metagenomics_report.qmd --to html

# Render via CLI
bioinformatics-report render examples/out/metagenomics/metagenomics_report.qmd --to html

# Build a wheel
python -m build
```

## Code Conventions & Common Patterns

- **Fluent API**: most `Report`/`Section` methods return `self`. `Report.add_section()` returns the new `Section`, switching the chain target.
- **Renderable protocol**: content dataclasses (`_SubSection`, `_Metric`, `_Figure`, `_Table`, `_Notice`, `_Code`, `_Latex`, `_List`, `_Markdown`, `_Download`, `_CitationLink`) implement `render(section, asset_rel_prefix)`.
- **Validation**: public methods validate types and dimensions early (`_validate_str`, `_validate_path`, `_validate_choice`).
- **HTML escaping**: user-facing strings are passed through `html.escape()`; `Section.add_raw()` and `Section.add_latex()` are the exceptions that insert raw content.
- **LaTeX math**: `Section.add_latex(tex, display=False)` emits `\( ... \)` inline or `\[ ... \]` display math. User-supplied TeX must not already contain delimiters.
- **Slug generation**: `Section._slug()` lowercases, collapses non-alphanumerics to `-`, and falls back to `"section"`.
- **Sync only**: no async code.
- **Logo handling**: SVG logos are embedded inline; PNG/JPG logos are copied to `assets/` and referenced via `<img>`. No logo renders a generic "Your Logo" placeholder.
- **Error handling**: missing figure/download/logo files emit a `warnings.warn` and are skipped; invalid inputs raise `TypeError` or `ValueError`.

## Important Files

| File | Purpose |
|---|---|
| `bioinformatics_report/__init__.py` | Package entry point; exports `Report`, `Section`; dynamic `__version__` from `setuptools_scm`. |
| `bioinformatics_report/report.py` | Core builder: `Report`, `Section`, private dataclasses, rendering, asset copying, `save()`. |
| `bioinformatics_report/cli.py` | `bioinformatics-report render` CLI. |
| `bioinformatics_report/templates/styles.html` | Embedded CSS include; copied into every generated report. |
| `bioinformatics_report/templates/sidebar.html` | Default sidebar for manual `.qmd` use; generic logo placeholder. |
| `bioinformatics_report/templates/footer.html` | Closing `</main>` and scroll-spy/toggle script. |
| `bioinformatics_report/templates/template.qmd` | Manual `.qmd` example showing frontmatter and CSS-class-based layout. |
| `bioinformatics_report/templates/_extension.yml` | Quarto extension manifest. |
| `bioinformatics_report/templates/bioinformatics-report.css` | Stylesheet referenced by the Quarto extension only. |
| `pyproject.toml` | PEP 621 metadata, `setuptools_scm`, optional deps, CLI entry point, ruff/black/mypy config. |
| `examples/assets/Unimed_logo.svg` | Example logo used by the bundled workflow reports. |
| `.github/workflows/ci.yml` | CI: lint, typecheck, test, render examples. |
| `.pre-commit-config.yaml` | pre-commit hooks for ruff and mypy. |

## Runtime/Tooling Preferences

- **Python**: `>=3.10` (tested on 3.10, 3.11, 3.12).
- **Quarto**: `>=1.4` required.
- **Package manager**: `pip`.
- **Build system**: `setuptools>=61.0` + `wheel` + `setuptools_scm>=8`; dynamic versioning from git tags.
- **Runtime dependencies**: none.
- **Optional dev dependencies**: `matplotlib`, `numpy`, `markdown`.
- **Optional test dependencies**: `pytest`, `pytest-cov`.
- **Lint/format/typecheck**: ruff, black (via ruff format), mypy — configured in `pyproject.toml`.
- **Pre-commit**: configured in `.pre-commit-config.yaml`.

## Testing & QA

- **Test framework**: pytest. Tests live in `tests/test_report.py`.
- **Coverage**: run `pytest --cov=bioinformatics_report --cov-report=xml`.
- **CI**: `.github/workflows/ci.yml` runs on push/PR, testing Python 3.10–3.12 with ruff, mypy, pytest, and example renders.
- **Validation workflow**: run the four example scripts and render their `.qmd` outputs with Quarto:
  ```bash
  cd examples
  python metagenomics_report.py
  python single_cell_report.py
  python spatial_transcriptomics_report.py
  python multi_omics_report.py
  for f in out/*/*.qmd; do quarto render "$f" --to html; done
  ```
- **Gaps to watch when editing**: `Report.save()` output structure, `_slug()` edge cases, HTML escaping, figure/download asset copying, MathJax include correctness, and Quarto frontmatter.
