"""Tests for the bioinformatics_report builder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bioinformatics_report import Report, Section


@pytest.fixture
def tmp_report(tmp_path: Path) -> Report:
    """Return a minimal Report instance with one section."""
    report = Report(title_line1="Test", title_line2="Report")
    section = report.add_section("01", "Summary")
    section.set_overview("Overview text")
    return report


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "report"


# --------------------------------------------------------------------------- #
# Basic construction
# --------------------------------------------------------------------------- #


def test_report_save_creates_qmd_and_assets(out_dir: Path, tmp_report: Report) -> None:
    qmd = tmp_report.save(out_dir)
    assert qmd.exists()
    assert (out_dir / "styles.html").exists()
    assert (out_dir / "sidebar.html").exists()
    assert (out_dir / "footer.html").exists()
    assert (out_dir / "assets").is_dir()


def test_qmd_contains_raw_html_block(out_dir: Path, tmp_report: Report) -> None:
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "``````{=html}" in text
    assert '<section class="report-section"' in text


def test_report_metadata_escaped(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.set_metadata([("Key", "<script>alert(1)</script>")])
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


# --------------------------------------------------------------------------- #
# Section content
# --------------------------------------------------------------------------- #


def test_add_text_is_escaped(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Details")
    section.add_text("<b>bold</b>")
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "<b>bold</b>" not in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text


def test_add_raw_is_not_escaped(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Details")
    section.add_raw("<span class='custom'>x</span>")
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "<span class='custom'>x</span>" in text


def test_add_table_validates_dimensions(tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Table")
    with pytest.raises(ValueError, match="row length"):
        section.add_table(
            headers=["A", "B"],
            rows=[["only-one"]],
        )


def test_add_table_accepts_cells(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Table")
    section.add_table(
        headers=["A", "B"],
        rows=[["1", "2"], ["3", "4"]],
        caption="Test table",
        cell_classes=[["mono", None], [None, "status pass"]],
    )
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "Test table" in text
    assert '<td class="mono">1</td>' in text


def test_add_table_paginated_renders_pager(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Table")
    section.add_table(
        headers=["A"],
        rows=[[str(i)] for i in range(5)],
        paginate=True,
        page_size=2,
    )
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert 'class="table-pager"' in text
    assert "Page 1 of 3" in text
    assert "table-pager-prev" in text
    assert "table-pager-next" in text


def test_add_table_not_paginated_has_no_pager(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Table")
    section.add_table(headers=["A"], rows=[["1"], ["2"], ["3"], ["4"]])
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "table-pager" not in text


def test_add_table_from_dataframe(out_dir: Path, tmp_report: Report) -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    section = tmp_report.add_section("02", "Table")
    section.add_table(df=pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}), caption="DF table")
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert "DF table" in text
    assert "<th>A</th>" in text
    assert "<th>B</th>" in text
    assert "<td>1</td>" in text
    assert "<td>x</td>" in text


def test_add_table_dataframe_requires_pandas(tmp_report: Report) -> None:
    pandas = sys.modules.get("pandas")
    sys.modules["pandas"] = None  # type: ignore[assignment]
    try:
        section = tmp_report.add_section("02", "Table")
        with pytest.raises(ImportError, match="pandas"):
            section.add_table(df="not-a-dataframe")  # type: ignore[arg-type]
    finally:
        if pandas is not None:
            sys.modules["pandas"] = pandas
        else:
            sys.modules.pop("pandas", None)


def test_add_table_rejects_df_and_rows_together(tmp_report: Report) -> None:
    pytest.importorskip("pandas")
    import pandas as pd

    section = tmp_report.add_section("02", "Table")
    with pytest.raises(ValueError, match="either a DataFrame"):
        section.add_table(headers=["A"], rows=[["1"]], df=pd.DataFrame({"A": ["2"]}))


def test_add_list(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "List")
    section.add_list(["first", "second"], ordered=True)
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert '<ol class="report-list">' in text
    assert "<li>first</li>" in text


def test_add_citation_link(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Refs")
    section.add_citation_link("Paper", "https://example.com/paper")
    qmd = tmp_report.save(out_dir)
    text = qmd.read_text(encoding="utf-8")
    assert 'href="https://example.com/paper"' in text
    assert "Paper" in text


# --------------------------------------------------------------------------- #
# Figures and downloads
# --------------------------------------------------------------------------- #


def test_add_figure_copies_to_assets(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    img = tmp_path / "plot.png"
    img.write_text("fake png", encoding="utf-8")
    section = tmp_report.add_section("02", "Figure")
    section.add_figure(img, caption="A plot")
    tmp_report.save(out_dir)
    assert (out_dir / "assets" / "plot.png").exists()


def test_add_figure_warns_when_missing(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Figure")
    section.add_figure("/nonexistent/plot.png", caption="Missing")
    with pytest.warns(UserWarning, match="Figure not found"):
        tmp_report.save(out_dir)


def test_add_figure_width(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    img = tmp_path / "plot.png"
    img.write_text("fake png", encoding="utf-8")
    section = tmp_report.add_section("02", "Figure")
    section.add_figure(img, caption="A plot", width="80%")
    tmp_report.save(out_dir)
    qmd = out_dir / "report.qmd"
    text = qmd.read_text(encoding="utf-8")
    assert 'style="width:80%; height:auto; display:block;"' in text


def test_add_figure_height(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    img = tmp_path / "plot.png"
    img.write_text("fake png", encoding="utf-8")
    section = tmp_report.add_section("02", "Figure")
    section.add_figure(img, caption="A plot", height="400px")
    tmp_report.save(out_dir)
    qmd = out_dir / "report.qmd"
    text = qmd.read_text(encoding="utf-8")
    assert 'style="height:400px; width:auto; display:block;"' in text


def test_add_code_collapsible_hidden_by_default(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Code")
    section.add_code("python", "x = 1")
    tmp_report.save(out_dir)
    qmd = out_dir / "report.qmd"
    text = qmd.read_text(encoding="utf-8")
    assert '<details class="code-collapsible">' in text
    assert '<span class="code-lang">python</span>' in text
    assert "x = 1" in text
    assert "open" not in text.split("<details")[1].split(">")[0]


def test_add_code_collapsible_open(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Code")
    section.add_code("bash", "echo hello", open=True)
    tmp_report.save(out_dir)
    qmd = out_dir / "report.qmd"
    text = qmd.read_text(encoding="utf-8")
    assert '<details class="code-collapsible" open>' in text


def test_add_code_invalid_open_type(tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Code")
    with pytest.raises(TypeError, match="open must be a bool"):
        section.add_code("python", "x = 1", open="yes")


def test_add_figure_width_and_height(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    img = tmp_path / "plot.png"
    img.write_text("fake png", encoding="utf-8")
    section = tmp_report.add_section("02", "Figure")
    section.add_figure(img, caption="A plot", width="600px", height="400px")
    tmp_report.save(out_dir)
    qmd = out_dir / "report.qmd"
    text = qmd.read_text(encoding="utf-8")
    assert 'style="width:600px; height:400px; object-fit:contain; display:block;"' in text


def test_add_download_copies_to_assets(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n", encoding="utf-8")
    section = tmp_report.add_section("02", "Download")
    section.add_download(data, label="Download data")
    tmp_report.save(out_dir)
    assert (out_dir / "assets" / "data.tsv").exists()


# --------------------------------------------------------------------------- #
# LaTeX
# --------------------------------------------------------------------------- #


def test_add_latex_triggers_mathjax_include(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Math")
    section.add_latex(r"x^2 + y^2 = z^2")
    section.add_latex(r"\int_0^1 x dx", display=True)
    tmp_report.save(out_dir)
    assert (out_dir / "mathjax.html").exists()
    qmd = (out_dir / "report.qmd").read_text(encoding="utf-8")
    assert "mathjax.html" in qmd
    assert r"\(x^2 + y^2 = z^2\)" in qmd
    assert r"\[\int_0^1 x dx\]" in qmd


def test_add_latex_rejects_existing_delimiters() -> None:
    section = Section(number="01", title="Math")
    with pytest.raises(ValueError, match="math delimiters"):
        section.add_latex(r"\(x\)")


# --------------------------------------------------------------------------- #
# Logo
# --------------------------------------------------------------------------- #


def test_default_logo_placeholder(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "Your Logo" in sidebar


def test_svg_logo_embedded(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    svg = tmp_path / "logo.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Custom</text></svg>',
        encoding="utf-8",
    )
    tmp_report.logo_path = svg
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "Custom" in sidebar


def test_non_svg_logo_copied(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    png = tmp_path / "logo.png"
    png.write_text("fake png", encoding="utf-8")
    tmp_report.logo_path = png
    tmp_report.save(out_dir)
    assert (out_dir / "assets" / "logo.png").exists()
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert 'src="assets/logo.png"' in sidebar


def test_svg_logo_width_height_stripped(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    svg = tmp_path / "logo.svg"
    svg.write_text(
        '<?xml version="1.0"?><!DOCTYPE svg>\n'
        '<svg width="500px" height="200px" xmlns="http://www.w3.org/2000/svg">'
        "<text>Company</text></svg>",
        encoding="utf-8",
    )
    tmp_report.logo_path = svg
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    # Fixed dimensions should be removed from the root SVG tag.
    assert 'width="500px"' not in sidebar
    assert 'height="200px"' not in sidebar
    # The configured logo size should be applied via style.
    assert "width:160px" in sidebar
    assert "height:auto" in sidebar
    assert "Company" in sidebar


def test_svg_logo_merges_with_existing_style(
    out_dir: Path, tmp_path: Path, tmp_report: Report
) -> None:
    svg = tmp_path / "logo.svg"
    svg.write_text(
        '<svg style="color:#123456" width="100" height="50" '
        'xmlns="http://www.w3.org/2000/svg"><text>Co</text></svg>',
        encoding="utf-8",
    )
    tmp_report.logo_path = svg
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "color:#123456" in sidebar
    assert "width:160px" in sidebar
    assert 'width="100"' not in sidebar


def test_logo_size_and_alt_parameters(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    png = tmp_path / "logo.png"
    png.write_text("fake png", encoding="utf-8")
    tmp_report.logo_path = png
    tmp_report.logo_alt = "Acme Corp"
    tmp_report.logo_width = "200px"
    tmp_report.logo_height = "80px"
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert 'alt="Acme Corp"' in sidebar
    assert "width:200px" in sidebar
    assert "height:80px" in sidebar


def test_default_logo_placeholder_uses_configured_size(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.logo_width = "120px"
    tmp_report.logo_height = "50px"
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "width:120px" in sidebar
    assert "height:50px" in sidebar
    assert "Your Logo" in sidebar


def test_set_logo_fluent_api(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    svg = tmp_path / "logo.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Fluent</text></svg>',
        encoding="utf-8",
    )
    returned = tmp_report.set_logo(svg, width="180px", height="60px")
    assert returned is tmp_report
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "Fluent" in sidebar
    assert "width:180px" in sidebar
    assert "height:60px" in sidebar


def test_set_logo_fluent_api_sets_alt_for_non_svg(
    out_dir: Path, tmp_path: Path, tmp_report: Report
) -> None:
    png = tmp_path / "logo.png"
    png.write_text("fake png", encoding="utf-8")
    tmp_report.set_logo(png, alt="Fluent Logo", width="180px")
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert 'alt="Fluent Logo"' in sidebar
    assert "width:180px" in sidebar


def test_set_logo_to_none_uses_placeholder(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.set_logo(None)
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "Your Logo" in sidebar


def test_sidebar_footer_configurable(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.set_sidebar_footer("Ready for review")
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "Ready for review" in sidebar
    assert "Pipeline complete" not in sidebar


def test_empty_sidebar_footer_omits_nav_foot(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert "nav-foot" not in sidebar


def test_run_label_prefix_configurable(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.run_label = "FY2026 Q2"
    tmp_report.run_label_prefix = "report"
    tmp_report.save(out_dir)
    sidebar = (out_dir / "sidebar.html").read_text(encoding="utf-8")
    assert '<div class="nav-run-label">report</div>' in sidebar
    assert "pipeline" not in sidebar


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_report_rejects_invalid_types() -> None:
    with pytest.raises(TypeError):
        Report(title_line1=123)  # type: ignore[arg-type]


def test_section_rejects_invalid_table_rows(tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Bad")
    with pytest.raises(ValueError, match="headers must not be empty"):
        section.add_table(headers=[], rows=[])


def test_add_latex_rejects_non_string() -> None:
    section = Section(number="01", title="Math")
    with pytest.raises(TypeError):
        section.add_latex(123)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Markdown (optional dependency)
# --------------------------------------------------------------------------- #


def test_add_markdown_requires_markdown_package(out_dir: Path, tmp_report: Report) -> None:
    section = tmp_report.add_section("02", "Markdown")
    section.add_markdown("# Heading\n\nSome **bold** text.")

    # Hide the optional dependency if installed.
    real_module = sys.modules.get("markdown")
    try:
        sys.modules["markdown"] = None  # type: ignore[assignment]
        with pytest.raises(ImportError, match="markdown"):
            tmp_report.save(out_dir)
    finally:
        if real_module is not None:
            sys.modules["markdown"] = real_module
        else:
            sys.modules.pop("markdown", None)


def test_add_markdown_renders_when_available(out_dir: Path, tmp_report: Report) -> None:
    pytest.importorskip("markdown")
    section = tmp_report.add_section("02", "Markdown")
    section.add_markdown("**bold**")
    tmp_report.save(out_dir)
    qmd = (out_dir / "report.qmd").read_text(encoding="utf-8")
    assert "<strong>bold</strong>" in qmd


# --------------------------------------------------------------------------- #
# Extra CSS
# --------------------------------------------------------------------------- #


def test_extra_css_path_copied(out_dir: Path, tmp_path: Path, tmp_report: Report) -> None:
    css = tmp_path / "custom.css"
    css.write_text(".masthead { background: red; }", encoding="utf-8")
    tmp_report.extra_css = css
    tmp_report.save(out_dir)
    assert (out_dir / "custom.css").exists()
    qmd = (out_dir / "report.qmd").read_text(encoding="utf-8")
    assert "custom.css" in qmd


def test_extra_css_raw_string(out_dir: Path, tmp_report: Report) -> None:
    tmp_report.extra_css = Path(".masthead { background: blue; }")
    # This is a string passed as a Path; code treats it as raw text because
    # the file does not exist.
    tmp_report.save(out_dir)
    custom = (out_dir / "custom.css").read_text(encoding="utf-8")
    assert "background: blue" in custom
