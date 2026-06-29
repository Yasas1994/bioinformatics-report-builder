"""Core report builder implementation."""

from __future__ import annotations

import dataclasses as dc
import datetime
import html
import re
import shutil
import warnings
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


def _validate_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {type(value).__name__}")
    return value


def _validate_optional_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _validate_str(value, name)


def _validate_path(value: str | Path | None, name: str, *, must_exist: bool) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str | Path):
        raise TypeError(f"{name} must be a string or Path, got {type(value).__name__}")
    path = Path(value)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"{name} does not exist: {path}")
    return path


def _validate_choice(value: Any, choices: set[str], name: str) -> str:
    text = _validate_str(value, name)
    if text not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {text!r}")
    return text


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _contains_math_delimiter(text: str) -> bool:
    """Return True if the user has already wrapped the expression in delimiters."""
    return any(d in text for d in ("\\(", "\\)", "\\[", "\\]", "$$"))


# --------------------------------------------------------------------------- #
# Renderable protocol and content items
# --------------------------------------------------------------------------- #


@runtime_checkable
class _Renderable(Protocol):
    """Protocol for section items that know how to render themselves."""

    def render(self, section: Section, asset_rel_prefix: str) -> str: ...


@dc.dataclass
class _SubSection:
    title: str
    anchor: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        return f'  <div class="sub-head" id="{self.anchor}">{html.escape(self.title)}</div>'


@dc.dataclass
class _Metric:
    label: str
    value: str
    sub: str = ""
    highlight: bool = False


@dc.dataclass
class _MetricsGroup:
    items: list[_Metric]

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        style = f' style="grid-template-columns: repeat({len(self.items)}, 1fr)"'
        out = [f'  <div class="metric-strip"{style}>']
        for m in self.items:
            cls = "metric-cell hi" if m.highlight else "metric-cell"
            sub = f'<div class="metric-sub">{html.escape(m.sub)}</div>' if m.sub else ""
            out.append(
                f'    <div class="{cls}">'
                f'<div class="metric-k">{html.escape(m.label)}</div>'
                f'<div class="metric-v">{html.escape(m.value)}</div>{sub}</div>'
            )
        out.append("  </div>")
        return "\n".join(out)


@dc.dataclass
class _Paragraph:
    text: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        return (
            f'  <p style="font-size:0.8rem; color:var(--steel); margin-bottom:1rem">'
            f"{html.escape(self.text)}</p>"
        )


@dc.dataclass
class _Notice:
    tag: str
    text: str
    kind: str = "info"

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        cls = f"notice {self.kind}" if self.kind != "info" else "notice"
        return (
            f'  <div class="{cls}">'
            f'<span class="notice-tag">{html.escape(self.tag)}</span>'
            f"{html.escape(self.text)}</div>"
        )


@dc.dataclass
class _Table:
    headers: list[str]
    rows: list[list[str]]
    caption: str
    col_classes: list[str | None] | None = None
    cell_classes: list[list[str | None]] | None = None
    paginate: bool = False
    page_size: int = 25

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        table_id = f"table-{id(self)}"
        out = ['  <table class="data-table" id="' + table_id + '">', "    <thead>", "      <tr>"]
        for h in self.headers:
            out.append(f"        <th>{html.escape(h)}</th>")
        out.append("      </tr>")
        out.append("    </thead>")
        out.append("    <tbody>")
        for r_idx, row in enumerate(self.rows):
            out.append("      <tr>")
            for i, cell in enumerate(row):
                cls = ""
                if (
                    self.cell_classes
                    and r_idx < len(self.cell_classes)
                    and i < len(self.cell_classes[r_idx])
                ):
                    c = self.cell_classes[r_idx][i]
                elif self.col_classes and i < len(self.col_classes):
                    c = self.col_classes[i]
                else:
                    c = None
                if c:
                    cls = f' class="{html.escape(c)}"'
                out.append(f"        <td{cls}>{html.escape(cell)}</td>")
            out.append("      </tr>")
        out.append("    </tbody>")
        out.append("  </table>")
        if self.caption:
            out.append(
                f'  <p style="font-family:var(--mono); font-size:0.58rem; '
                f'color:var(--mist); margin-top:0.4rem">{html.escape(self.caption)}</p>'
            )
        if self.paginate and self.rows:
            out.append(self._pagination_html(table_id))
        return "\n".join(out)

    def _pagination_html(self, table_id: str) -> str:
        total_pages = max(1, (len(self.rows) + self.page_size - 1) // self.page_size)
        return (
            f'<div class="table-pager" id="{table_id}-pager" data-table="{table_id}" '
            f'data-page-size="{self.page_size}">'
            f'<button class="table-pager-prev" disabled>‹ Prev</button>'
            f'<span class="table-pager-info">Page 1 of {total_pages}</span>'
            f'<button class="table-pager-next">Next ›</button>'
            f"</div>"
        )


@dc.dataclass
class _FreqBars:
    data: list[tuple[str, float]]
    low_threshold: float

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        out = ['  <table class="freq-table">']
        for label, pct in self.data:
            low = " low" if pct < self.low_threshold else ""
            out.append("    <tr>")
            out.append(f'      <td class="freq-taxon">{html.escape(label)}</td>')
            out.append(
                '      <td class="freq-bar-cell">'
                f'<div class="freq-bar-bg"><div class="freq-bar-fg{low}" '
                f'style="width:{pct:.1f}%"></div></div></td>'
            )
            out.append(f'      <td class="freq-pct">{pct:.1f}%</td>')
            out.append("    </tr>")
        out.append("  </table>")
        return "\n".join(out)


@dc.dataclass
class _Figure:
    src: Path
    caption: str
    label: str
    width: str | None = None

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        src = f"{asset_rel_prefix}{self.src.name}"
        if self.width:
            style = f"width:{html.escape(self.width)}; height:auto; display:block;"
        else:
            style = "max-width:100%; height:auto; display:block;"
        return (
            f'  <div class="figure-area">'
            f'<div class="figure-canvas">'
            f'<img src="{src}" alt="{html.escape(self.caption)}" '
            f'style="{style}">'
            f"</div>"
            f'<div class="figure-label"><b>{html.escape(self.label)}</b> · '
            f"{html.escape(self.caption)}</div></div>"
        )


@dc.dataclass
class _Code:
    language: str
    code: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        body = html.escape(self.code)
        return f'  <div class="code-block">{body}</div>'


@dc.dataclass
class _Latex:
    text: str
    display: bool = False

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        # Deliberately NOT html.escape()-ed: MathJax must see the raw TeX.
        if self.display:
            return f'  <div class="math display">\\[{self.text}\\]</div>'
        return f'  <span class="math inline">\\({self.text}\\)</span>'


@dc.dataclass
class _References:
    citations: list[str]

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        out = ['  <ol class="ref-list">']
        for c in self.citations:
            out.append(f"    <li>{html.escape(c)}</li>")
        out.append("  </ol>")
        return "\n".join(out)


@dc.dataclass
class _RawHtml:
    html: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        return self.html


@dc.dataclass
class _List:
    items: list[str]
    ordered: bool

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        tag = "ol" if self.ordered else "ul"
        out = [f'  <{tag} class="report-list">']
        for item in self.items:
            out.append(f"    <li>{html.escape(item)}</li>")
        out.append(f"  </{tag}>")
        return "\n".join(out)


@dc.dataclass
class _Markdown:
    text: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        try:
            import markdown  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "add_markdown requires the 'markdown' package. "
                "Install it with: pip install markdown"
            ) from exc
        md = markdown.Markdown(extensions=["extra", "codehilite"])
        body = md.convert(self.text)
        return f'  <div class="markdown-body">{body}</div>'


@dc.dataclass
class _Download:
    path: Path
    label: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        filename = self.path.name
        return (
            f'  <p class="download-link">'
            f'<a href="{asset_rel_prefix}{html.escape(filename)}" download>'
            f"{html.escape(self.label)}</a></p>"
        )


@dc.dataclass
class _CitationLink:
    text: str
    url: str

    def render(self, section: Section, asset_rel_prefix: str) -> str:
        return (
            f'  <p class="citation-link">'
            f'<a href="{html.escape(self.url)}" target="_blank" rel="noopener">'
            f"{html.escape(self.text)}</a></p>"
        )


# --------------------------------------------------------------------------- #
# Section
# --------------------------------------------------------------------------- #


class Section:
    """One numbered report section."""

    def __init__(self, number: str, title: str, count: str = ""):
        self.number = _validate_str(number, "number")
        self.title = _validate_str(title, "title")
        self.count = _validate_str(count, "count")
        self.overview: str | None = None
        self.items: list[_Renderable] = []
        self._subsection_counter = 0
        self._figure_counter = 0

    # ------------------------------------------------------------------ public
    def set_overview(self, text: str) -> Section:
        """Set the overview paragraph for this section."""
        self.overview = _validate_str(text, "overview")
        return self

    add_overview = set_overview

    def add_metrics(self, metrics: Iterable[dict[str, Any]]) -> Section:
        """Add a strip of metric cards.

        Each metric dict accepts keys: label, value, sub, highlight.
        """
        parsed: list[_Metric] = []
        for m in metrics:
            parsed.append(
                _Metric(
                    label=_validate_str(m.get("label", ""), "metric label"),
                    value=_validate_str(m.get("value", ""), "metric value"),
                    sub=_validate_str(m.get("sub", ""), "metric sub"),
                    highlight=bool(m.get("highlight", False)),
                )
            )
        self.items.append(_MetricsGroup(items=parsed))
        return self

    def add_subsection(self, title: str, anchor: str | None = None) -> Section:
        """Add a subsection heading with an anchor for the sidebar."""
        title = _validate_str(title, "subsection title")
        if anchor is None:
            self._subsection_counter += 1
            anchor = f"s{self.number}-{self._subsection_counter:02d}-{self._slug(title)}"
        else:
            anchor = _validate_str(anchor, "subsection anchor")
        self.items.append(_SubSection(title=title, anchor=anchor))
        return self

    def add_text(self, text: str) -> Section:
        """Add a plain paragraph."""
        self.items.append(_Paragraph(_validate_str(text, "text")))
        return self

    def add_notice(self, tag: str, text: str, kind: str = "info") -> Section:
        """Add an info/warn notice strip."""
        kind = _validate_choice(kind, {"info", "warn"}, "notice kind")
        self.items.append(
            _Notice(
                tag=_validate_str(tag, "notice tag"),
                text=_validate_str(text, "notice text"),
                kind=kind,
            )
        )
        return self

    def add_table(
        self,
        headers: Sequence[str] | None = None,
        rows: Sequence[Sequence[Any]] | None = None,
        df: Any = None,
        caption: str = "",
        col_classes: Sequence[str | None] | None = None,
        cell_classes: Sequence[Sequence[str | None]] | None = None,
        paginate: bool = False,
        page_size: int = 25,
    ) -> Section:
        """Add a data table.

        Provide either ``headers`` + ``rows`` or a pandas ``df``.

        ``col_classes`` applies a CSS class to every cell in a column.
        ``cell_classes`` overrides it on a per-cell basis and should have the
        same shape as ``rows``.

        Set ``paginate=True`` to render the table with client-side page
        navigation showing ``page_size`` rows per page.
        """
        if df is not None:
            if headers is not None or rows is not None:
                raise ValueError(
                    "pass either a DataFrame ('df') or explicit 'headers' and 'rows', not both"
                )
            try:
                import pandas as pd  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "pandas is required for add_table(df=...); install it with: pip install pandas"
                ) from exc
            if not isinstance(df, pd.DataFrame):
                raise TypeError("df must be a pandas DataFrame")
            headers = list(df.columns.astype(str))
            rows = [[_cell_text(c) for c in row] for row in df.values.tolist()]
        else:
            if headers is None or rows is None:
                raise ValueError("add_table requires either 'df' or both 'headers' and 'rows'")

        headers = list(headers)
        if not headers:
            raise ValueError("table headers must not be empty")
        str_rows: list[list[str]] = []
        for row in rows:
            if len(row) != len(headers):
                raise ValueError(
                    f"row length ({len(row)}) does not match header length ({len(headers)})"
                )
            str_rows.append([_cell_text(c) for c in row])
        self.items.append(
            _Table(
                headers=headers,
                rows=str_rows,
                caption=_validate_str(caption, "caption"),
                col_classes=list(col_classes) if col_classes else None,
                cell_classes=[list(r) for r in cell_classes] if cell_classes else None,
                paginate=bool(paginate),
                page_size=int(page_size),
            )
        )
        return self

    def add_freq_bars(
        self, data: Iterable[tuple[str, float]], low_threshold: float = 15.0
    ) -> Section:
        """Add a minimal horizontal bar chart from (label, percent) tuples."""
        parsed: list[tuple[str, float]] = []
        for label, pct in data:
            parsed.append((_validate_str(label, "freq label"), float(pct)))
        self.items.append(_FreqBars(data=parsed, low_threshold=float(low_threshold)))
        return self

    def add_figure(
        self,
        path: str | Path,
        caption: str,
        label: str | None = None,
        width: str | None = None,
    ) -> Section:
        """Reference a figure.  It will be copied to the report assets dir.

        By default the image is shown at its native size, scaled down only if
        it is wider than the content column. Pass ``width`` (e.g. ``"600px"``
        or ``"80%"``) to force a specific display width.
        """
        valid_path = _validate_path(path, "figure path", must_exist=False)
        if valid_path is None:
            raise ValueError("figure path cannot be empty")
        if label is None:
            self._figure_counter += 1
            label = f"Fig. {self._figure_counter}"
        else:
            label = _validate_str(label, "figure label")
        if width is not None:
            width = _validate_str(width, "figure width")
        self.items.append(
            _Figure(
                src=valid_path,
                caption=_validate_str(caption, "figure caption"),
                label=label,
                width=width,
            )
        )
        return self

    def add_code(self, language: str, code: str) -> Section:
        """Add a styled code block."""
        self.items.append(
            _Code(
                language=_validate_str(language, "language"),
                code=_validate_str(code, "code"),
            )
        )
        return self

    def add_references(self, citations: Iterable[str]) -> Section:
        """Add a numbered reference list."""
        self.items.append(_References([_validate_str(c, "citation") for c in citations]))
        return self

    def add_raw(self, html_fragment: str) -> Section:
        """Insert arbitrary raw HTML."""
        self.items.append(_RawHtml(_validate_str(html_fragment, "html fragment")))
        return self

    def add_latex(self, text: str, display: bool = False) -> Section:
        """Add a LaTeX math expression.

        Inline math is wrapped in \\( ... \\); display math in \\[ ... \\].
        The report output loads MathJax when at least one LaTeX item is
        present so the expressions are rendered in the browser.
        """
        text = _validate_str(text, "latex")
        if _contains_math_delimiter(text):
            raise ValueError(
                "LaTeX text must not contain math delimiters such as \\(, \\), "
                "\\[, \\] or $$; use the display flag for display math"
            )
        self.items.append(_Latex(text=text, display=bool(display)))
        return self

    def add_list(self, items: Iterable[str], ordered: bool = False) -> Section:
        """Add a bulleted or numbered list."""
        self.items.append(
            _List(
                items=[_validate_str(item, "list item") for item in items],
                ordered=bool(ordered),
            )
        )
        return self

    def add_markdown(self, text: str) -> Section:
        """Add Markdown content rendered to HTML.

        Requires the optional ``markdown`` package.
        """
        self.items.append(_Markdown(_validate_str(text, "markdown")))
        return self

    def add_download(
        self,
        path: str | Path,
        label: str | None = None,
    ) -> Section:
        """Add a download link to a file that will be copied to assets."""
        valid_path = _validate_path(path, "download path", must_exist=False)
        if valid_path is None:
            raise ValueError("download path cannot be empty")
        label = _validate_str(label or valid_path.name, "download label")
        self.items.append(_Download(path=valid_path, label=label))
        return self

    def add_citation_link(self, text: str, url: str) -> Section:
        """Add a citation paragraph linking to an external URL."""
        self.items.append(
            _CitationLink(
                text=_validate_str(text, "citation text"),
                url=_validate_str(url, "citation url"),
            )
        )
        return self

    # ------------------------------------------------------------------ render
    def _render(self, asset_rel_prefix: str = "assets/") -> str:
        lines: list[str] = []
        anchor = self._slug(self.title)
        lines.append(f'<section class="report-section" id="{anchor}">')
        lines.append('  <div class="section-head">')
        lines.append(f'    <span class="section-num">{html.escape(self.number)}</span>')
        lines.append(f"    <h2>{html.escape(self.title)}</h2>")
        if self.count:
            lines.append(f'    <span class="section-count">{html.escape(self.count)}</span>')
        lines.append("  </div>")

        if self.overview:
            lines.append(
                f'  <p style="font-size:0.82rem; color:var(--steel); '
                f'max-width:600px; margin-bottom:1.5rem; line-height:1.7">'
                f"{html.escape(self.overview)}</p>"
            )

        for item in self.items:
            lines.append(item.render(self, asset_rel_prefix))

        lines.append("</section>")
        return "\n".join(lines)

    @staticmethod
    def _slug(text: str) -> str:
        s = text.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = s.strip("-")
        return s or "section"


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


class Report:
    """Top-level report builder."""

    def __init__(
        self,
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
    ):
        self.title_line1 = _validate_str(title_line1, "title_line1")
        self.title_line2 = _validate_str(title_line2, "title_line2")
        self.pipeline = _validate_str(pipeline, "pipeline")
        self.operator = _validate_str(operator, "operator")
        self.reference = _validate_str(reference, "reference")
        self.cluster = _validate_str(cluster, "cluster")
        self.date = _validate_optional_str(date, "date") or str(datetime.date.today())
        self.run_label = _validate_str(run_label, "run_label")
        self.run_status = _validate_str(run_status, "run_status")
        self.run_label_prefix = _validate_str(run_label_prefix, "run_label_prefix")
        self.sidebar_footer = _validate_str(sidebar_footer, "sidebar_footer")
        self.logo_path = _validate_path(logo_path, "logo_path", must_exist=False)
        self.logo_alt = _validate_str(logo_alt, "logo_alt")
        self.logo_width = _validate_str(logo_width, "logo_width")
        self.logo_height = _validate_str(logo_height, "logo_height")
        self.footer_left = _validate_str(footer_left, "footer_left")
        self.footer_right = _validate_str(footer_right, "footer_right")
        self.extra_css = _validate_path(extra_css, "extra_css", must_exist=False)
        self.mathjax_url = _validate_optional_str(mathjax_url, "mathjax_url")
        self.offline_mathjax = bool(offline_mathjax)
        self._metadata: list[tuple[str, str]] = []
        self._sections: list[Section] = []

    # ------------------------------------------------------------------ public
    def set_metadata(self, items: Sequence[tuple[str, str]]) -> Report:
        """Set the masthead metadata ledger.

        Expects a sequence of (key, value) pairs; up to five fit the layout.
        """
        validated: list[tuple[str, str]] = []
        for key, value in items:
            validated.append(
                (_validate_str(key, "metadata key"), _validate_str(value, "metadata value"))
            )
        self._metadata = validated
        return self

    def add_section(self, number: str, title: str, count: str = "") -> Section:
        """Add and return a new report section."""
        section = Section(number=number, title=title, count=count)
        self._sections.append(section)
        return section

    def set_logo(
        self,
        path: str | Path | None,
        alt: str | None = None,
        width: str | None = None,
        height: str | None = None,
    ) -> Report:
        """Configure the sidebar logo.

        SVG logos are embedded inline; PNG/JPG logos are copied to the assets
        directory. Pass ``None`` to fall back to the generic placeholder.
        """
        self.logo_path = _validate_path(path, "logo path", must_exist=False)
        if alt is not None:
            self.logo_alt = _validate_str(alt, "logo alt")
        if width is not None:
            self.logo_width = _validate_str(width, "logo width")
        if height is not None:
            self.logo_height = _validate_str(height, "logo height")
        return self

    def set_sidebar_footer(self, text: str) -> Report:
        """Set the small status text shown at the bottom of the sidebar."""
        self.sidebar_footer = _validate_str(text, "sidebar footer")
        return self

    def set_run_label_prefix(self, text: str) -> Report:
        """Set the small label shown above ``run_label`` in the sidebar."""
        self.run_label_prefix = _validate_str(text, "run label prefix")
        return self

    def _has_latex(self) -> bool:
        return any(isinstance(item, _Latex) for s in self._sections for item in s.items)

    def save(
        self,
        output_dir: str | Path,
        filename: str = "report.qmd",
        assets_dir: str = "assets",
    ) -> Path:
        """Write the report directory with `.qmd`, includes, and assets."""
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        assets = out / assets_dir
        assets.mkdir(parents=True, exist_ok=True)

        self._copy_template_files(out)
        self._copy_assets(assets)
        if self._has_latex():
            self._write_mathjax_include(out)
        if self.extra_css:
            self._write_extra_css(out)

        qmd_path = out / filename
        qmd_path.write_text(self._build_qmd(assets_dir), encoding="utf-8")
        sidebar_path = out / "sidebar.html"
        sidebar_path.write_text(self._build_sidebar(), encoding="utf-8")
        return qmd_path

    # ------------------------------------------------------------------ internals
    def _copy_template_files(self, out: Path) -> None:
        here = Path(__file__).with_suffix("").parent / "templates"
        for name in ("styles.html",):
            src = here / name
            if src.exists():
                shutil.copy2(src, out / name)
        (out / "footer.html").write_text(self._build_footer_script(), encoding="utf-8")

    def _copy_assets(self, assets: Path) -> None:
        assets = assets.resolve()
        for section in self._sections:
            for item in section.items:
                if isinstance(item, _Figure):
                    src = item.src.resolve()
                    if not src.exists():
                        warnings.warn(f"Figure not found, skipping: {src}", stacklevel=2)
                        continue
                    if src.parent == assets:
                        continue
                    shutil.copy2(src, assets / src.name)
                elif isinstance(item, _Download):
                    src = item.path.resolve()
                    if not src.exists():
                        warnings.warn(
                            f"Download file not found, skipping: {src}",
                            stacklevel=2,
                        )
                        continue
                    if src.parent == assets:
                        continue
                    shutil.copy2(src, assets / src.name)
        if self.logo_path and self.logo_path.exists():
            logo = self.logo_path.resolve()
            if logo.suffix.lower() != ".svg" and logo.parent != assets:
                shutil.copy2(logo, assets / logo.name)

    @staticmethod
    def _write_mathjax_include(out: Path) -> None:
        mathjax_html = """<script>
MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']]
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
"""
        (out / "mathjax.html").write_text(mathjax_html, encoding="utf-8")

    def _write_extra_css(self, out: Path) -> None:
        if self.extra_css is None:
            return
        if self.extra_css.exists():
            content = self.extra_css.read_text(encoding="utf-8")
        else:
            # Treat the value as raw CSS text.
            content = str(self.extra_css)
        if not content.strip().startswith("<style>"):
            content = f"<style>\n{content}\n</style>"
        (out / "custom.css").write_text(content, encoding="utf-8")

    def _resolve_mathjax_url(self, out: Path) -> str:
        if self.mathjax_url:
            return self.mathjax_url
        if self.offline_mathjax:
            local = self._find_local_mathjax()
            if local:
                target = out / "assets" / "mathjax" / "tex-chtml.js"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local, target)
                return "assets/mathjax/tex-chtml.js"
            warnings.warn(
                "offline_mathjax=True but no local MathJax installation found; falling back to CDN",
                stacklevel=2,
            )
        return "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"

    @staticmethod
    def _find_local_mathjax() -> Path | None:
        """Look for a local MathJax tex-chtml.js at a few common locations."""
        candidates = [
            Path("/usr/share/javascript/mathjax/tex-chtml.js"),
            Path("/usr/local/share/javascript/mathjax/tex-chtml.js"),
        ]
        # Try to locate via npm if available.
        import shutil as _shutil

        npm = _shutil.which("npm")
        if npm:
            try:
                import subprocess

                prefix = subprocess.run(
                    [npm, "root", "-g"],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                if prefix:
                    candidates.append(Path(prefix) / "mathjax" / "es5" / "tex-chtml.js")
            except Exception:
                pass
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _build_qmd(self, assets_dir: str) -> str:
        parts: list[str] = []
        parts.append("---")
        parts.append("format:")
        parts.append("  html:")
        parts.append("    toc: false")
        parts.append("    theme: none")
        parts.append("    page-layout: custom")
        parts.append("    include-in-header:")
        parts.append("      - styles.html")
        if self._has_latex():
            parts.append("      - mathjax.html")
        if self.extra_css:
            parts.append("      - custom.css")
        parts.append("    include-before-body: sidebar.html")
        parts.append("    include-after-body: footer.html")
        parts.append("    embed-resources: false")
        parts.append("    smooth-scroll: true")
        parts.append("    fig-responsive: true")
        parts.append("    link-color: '#264882'")
        parts.append("---")
        parts.append("")
        parts.append("``````{=html}")
        parts.append(self._build_masthead())
        for section in self._sections:
            parts.append(section._render(asset_rel_prefix=f"{assets_dir}/"))
        parts.append("``````")
        return "\n".join(parts)

    def _build_masthead(self) -> str:
        lines: list[str] = []
        lines.append('<div class="masthead">')
        lines.append('  <div class="masthead-top">')
        lines.append(
            f"    <h1>{html.escape(self.title_line1)}<br><strong>"
            f"{html.escape(self.title_line2)}</strong></h1>"
        )
        lines.append('    <div class="masthead-pipeline">')
        if self.pipeline:
            lines.append(f"      <span>pipeline</span>{html.escape(self.pipeline)}")
        if self.operator:
            lines.append(f"      <span>operator</span>{html.escape(self.operator)}")
        if self.reference:
            lines.append(f"      <span>reference</span>{html.escape(self.reference)}")
        if self.cluster:
            lines.append(f"      <span>cluster</span>{html.escape(self.cluster)}")
        lines.append("    </div>")
        lines.append("  </div>")
        lines.append('  <div class="meta-ledger">')
        for key, value in self._metadata:
            lines.append('    <div class="meta-cell">')
            lines.append(f'      <div class="meta-k">{html.escape(key)}</div>')
            lines.append(f'      <div class="meta-v">{html.escape(value)}</div>')
            lines.append("    </div>")
        lines.append("  </div>")
        lines.append("</div>")
        return "\n".join(lines)

    def _build_sidebar(self) -> str:
        lines: list[str] = []
        lines.append('<nav id="sidebar">')
        lines.append('  <div class="nav-header">')
        lines.append(self._logo_html())
        if self.run_label:
            prefix = html.escape(self.run_label_prefix)
            lines.append(f'    <div class="nav-run-label">{prefix}</div>')
            lines.append(f'    <div class="nav-title">{html.escape(self.run_label)}</div>')
        if self.run_status:
            lines.append(f'    <div class="nav-meta">{html.escape(self.run_status)}</div>')
        lines.append("  </div>")
        lines.append('  <ul class="nav-index">')
        for i, section in enumerate(self._sections):
            anchor = section._slug(section.title)
            first = " open" if i == 0 else ""
            lines.append(f'    <li class="nav-section{first}">')
            lines.append(
                f'      <a class="nav-section-link" href="#{anchor}">'
                f'<span class="nav-num">{html.escape(section.number)}</span>'
                f'<span class="nav-label">{html.escape(section.title)}</span></a>'
            )
            subsections = [it for it in section.items if isinstance(it, _SubSection)]
            if subsections:
                lines.append('      <ul class="nav-sub">')
                for sub in subsections:
                    lines.append(
                        f'        <li><a href="#{sub.anchor}">{html.escape(sub.title)}</a></li>'
                    )
                lines.append("      </ul>")
            lines.append("    </li>")
        lines.append("  </ul>")
        if self.sidebar_footer:
            lines.append('  <div class="nav-foot">')
            lines.append(f'    <div class="run-status">{html.escape(self.sidebar_footer)}</div>')
            lines.append("  </div>")
        lines.append("</nav>")
        lines.append('<main id="content">')
        return "\n".join(lines)

    def _logo_html(self) -> str:
        if self.logo_path and self.logo_path.exists():
            alt = html.escape(self.logo_alt or "logo")
            if self.logo_path.suffix.lower() == ".svg":
                svg = self.logo_path.read_text(encoding="utf-8")
                return self._normalize_svg_logo(svg)
            # Non-SVG logos are referenced as images in the sidebar.
            return (
                f'<img src="assets/{html.escape(self.logo_path.name)}" '
                f'alt="{alt}" '
                f'style="width:{self.logo_width}; height:{self.logo_height}; '
                'display:block; margin-bottom:1.5rem;">'
            )
        # Generic inline SVG placeholder when no logo is supplied.
        return (
            f'<svg style="width:{self.logo_width}; height:{self.logo_height}; '
            'display:block; margin-bottom:1.5rem;" '
            'viewBox="0 0 160 60" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="0" y="0" width="160" height="60" rx="4" fill="#e8edf4"/>'
            '<text x="80" y="34" text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="14" fill="#264882" font-weight="600">Your Logo</text>'
            "</svg>"
        )

    def _normalize_svg_logo(self, svg: str) -> str:
        """Make an arbitrary SVG logo scale to the sidebar width.

        Strips fixed width/height attributes from the root ``<svg>`` tag and
        applies the configured logo size via an inline style so the logo behaves
        consistently regardless of the source file's dimensions.
        """
        svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg, flags=re.IGNORECASE)
        svg = re.sub(r"<[?]xml[^?]*[?]>", "", svg)
        match = re.search(r"<svg\b([^>]*)>", svg, flags=re.IGNORECASE)
        if not match:
            return svg
        attrs = match.group(1)
        # Remove fixed width/height from the root SVG tag only.
        attrs = re.sub(r"\s+(width|height)\s*=\s*\"[^\"]*\"", "", attrs, flags=re.IGNORECASE)
        attrs = re.sub(r"\s+(width|height)\s*=\s*'[^']*'", "", attrs, flags=re.IGNORECASE)
        # Ensure the SVG scales proportionally.
        if not re.search(r"\bpreserveAspectRatio\s*=", attrs, flags=re.IGNORECASE):
            attrs += ' preserveAspectRatio="xMidYMid meet"'
        style = (
            f"width:{self.logo_width}; height:{self.logo_height}; "
            "display:block; margin-bottom:1.5rem;"
        )
        style_match = re.search(r'\bstyle\s*=\s*"([^"]*)"', attrs, flags=re.IGNORECASE)
        if style_match:
            existing = style_match.group(1).rstrip(" ;")
            merged = f"{existing}; {style}" if existing else style
            attrs = attrs[: style_match.start()] + f'style="{merged}"' + attrs[style_match.end() :]
        else:
            attrs += f' style="{style}"'
        return svg[: match.start()] + f"<svg{attrs}>" + svg[match.end() :]

    def _build_footer_script(self) -> str:
        lines: list[str] = []
        lines.append("</main>")
        lines.append('<footer class="report-footer">')
        lines.append(f"  <span>{html.escape(self.footer_left)}</span>")
        lines.append(f"  <span>{html.escape(self.footer_right)}</span>")
        lines.append("</footer>")
        lines.append("<script>")
        lines.append("document.querySelectorAll('.nav-section-link').forEach(link => {")
        lines.append("  link.addEventListener('click', e => {")
        lines.append("    e.preventDefault();")
        lines.append("    const li = link.closest('li');")
        lines.append("    li.classList.toggle('open');")
        lines.append("    const href = link.getAttribute('href');")
        lines.append("    document.querySelector(href).scrollIntoView({behavior:'smooth'});")
        lines.append("  });")
        lines.append("});")
        lines.append("const observer = new IntersectionObserver(entries => {")
        lines.append("  entries.forEach(entry => {")
        lines.append("    if (entry.isIntersecting) {")
        lines.append("      document.querySelectorAll('.nav-section-link')")
        lines.append("        .forEach(l => l.classList.remove('active'));")
        lines.append("      const id = entry.target.id;")
        lines.append("      const selector = '.nav-section-link[href=\"#' + id + '\"]';")
        lines.append("      const active = document.querySelector(selector);")
        lines.append("      if (active) {")
        lines.append("        active.classList.add('active');")
        lines.append("        active.closest('li').classList.add('open');")
        lines.append("      }")
        lines.append("    }")
        lines.append("  });")
        lines.append("}, {threshold: 0.5});")
        lines.append("document.querySelectorAll('.report-section')")
        lines.append("  .forEach(s => observer.observe(s));")
        lines.append("")
        lines.append("// Client-side table pagination")
        lines.append("document.querySelectorAll('.table-pager').forEach(pager => {")
        lines.append("  const tableId = pager.dataset.table;")
        lines.append("  const pageSize = parseInt(pager.dataset.pageSize, 10) || 25;")
        lines.append("  const table = document.getElementById(tableId);")
        lines.append("  if (!table) return;")
        lines.append("  const rows = Array.from(table.querySelectorAll('tbody tr'));")
        lines.append("  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));")
        lines.append("  let currentPage = 1;")
        lines.append("")
        lines.append("  function showPage(page) {")
        lines.append("    currentPage = page;")
        lines.append("    rows.forEach((row, idx) => {")
        lines.append("      const start = (currentPage - 1) * pageSize;")
        lines.append("      const end = currentPage * pageSize;")
        lines.append("      row.style.display = (idx >= start && idx < end) ? '' : 'none';")
        lines.append("    });")
        lines.append("    const info = 'Page ' + currentPage + ' of ' + totalPages;")
        lines.append("    pager.querySelector('.table-pager-info').textContent = info;")
        lines.append("    pager.querySelector('.table-pager-prev').disabled = currentPage === 1;")
        lines.append("    const last = currentPage === totalPages;")
        lines.append("    pager.querySelector('.table-pager-next').disabled = last;")
        lines.append("  }")
        lines.append("")
        lines.append("  pager.querySelector('.table-pager-prev').addEventListener('click', () => {")
        lines.append("    if (currentPage > 1) showPage(currentPage - 1);")
        lines.append("  });")
        lines.append("  pager.querySelector('.table-pager-next').addEventListener('click', () => {")
        lines.append("    if (currentPage < totalPages) showPage(currentPage + 1);")
        lines.append("  });")
        lines.append("")
        lines.append("  showPage(1);")
        lines.append("});")
        lines.append("</script>")
        return "\n".join(lines)
