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
