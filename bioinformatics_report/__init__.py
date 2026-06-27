"""Programmatic builder for branded HTML reports.

The package exposes a small fluent API that writes a Quarto `.qmd` document
plus the required CSS / sidebar / footer includes. Rendering is then done
with Quarto::

    from bioinformatics_report import Report

    report = Report(title_line1="Project", title_line2="Analysis Report")
    report.add_section("01", "Summary").add_overview("...")
    report.save("my_report")
    # quarto render my_report/report.qmd --to html
"""

from importlib.metadata import PackageNotFoundError, version

from .report import Report, Section

__all__ = ["Report", "Section"]

try:
    __version__ = version(__package__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
