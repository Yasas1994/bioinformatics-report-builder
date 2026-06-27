"""Programmatic builder for UMG bioinformatics HTML reports.

The package exposes a small fluent API that writes a Quarto `.qmd` document
plus the required CSS / sidebar / footer includes.  Rendering is then done
with Quarto::

    from bioinformatics_report import Report

    report = Report(title_line1="Project", title_line2="Analysis Report")
    report.add_section("01", "Summary").add_overview("...")
    report.save("my_report")
    # quarto render my_report/report.qmd --to html
"""

from .report import Report, Section

__all__ = ["Report", "Section"]
__version__ = "0.1.0"
