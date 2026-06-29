"""Example: generic company quarterly report.

This script shows how the builder can be used for any domain, not just
bioinformatics. It also demonstrates switching the company logo at runtime
via Report.set_logo().
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from bioinformatics_report import Report

OUT = Path(__file__).with_suffix("").parent / "out" / "generic_company"
ASSETS = OUT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# ── Generate a placeholder company logo (SVG) ────────────────────────────
logo_path = ASSETS / "acme_logo.svg"
logo_path.write_text(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60" width="200" height="60">
  <rect width="200" height="60" rx="6" fill="#1a2a4a"/>
  <text x="100" y="38" text-anchor="middle" font-family="Arial, sans-serif"
        font-size="22" font-weight="700" fill="#ffffff">ACME Corp</text>
</svg>""",
    encoding="utf-8",
)

# ── Generate a placeholder figure ────────────────────────────────────────
quarters = ["Q1", "Q2", "Q3", "Q4"]
revenue = np.array([2.1, 2.4, 2.8, 3.2])
fig, ax = plt.subplots(figsize=(6, 3))
ax.bar(quarters, revenue, color=["#264882", "#637A9F", "#9FADC4", "#D38726"])
ax.set_ylabel("Revenue ($M)")
ax.set_title("Quarterly Revenue")
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
fig.tight_layout()
fig_path = ASSETS / "revenue.png"
fig.savefig(fig_path, dpi=150)
plt.close(fig)

# ── Build report ─────────────────────────────────────────────────────────
report = Report(
    title_line1="ACME Corporation",
    title_line2="Quarterly Business Report",
    date="2026-06-27",
    run_label="FY2026 · Q2",
    run_status="Report finalized · 2026-06-27",
    run_label_prefix="report",
    sidebar_footer="Report ready",
    footer_left="ACME Corporation · FY2026 Q2",
    footer_right="Confidential · Internal use only",
)

# Switch the logo easily at runtime (SVG, PNG or JPG are supported).
report.set_logo(logo_path, alt="ACME Corp", width="180px", height="auto")

report.set_metadata(
    [
        ("Date", "2026-06-27"),
        ("Quarter", "Q2 FY2026"),
        ("Revenue", "$3.2 M"),
        ("Growth", "+14% YoY"),
        ("Customers", "1,240"),
    ]
)

summary = report.add_section("01", "Executive Summary", count="FY2026 Q2")
summary.set_overview(
    "ACME Corp delivered strong results in the second quarter, driven by "
    "new enterprise contracts and improved operational efficiency."
)
summary.add_metrics(
    [
        {"label": "Revenue", "value": "$3.2 M", "sub": "+14% year over year", "highlight": True},
        {"label": "New Customers", "value": "142", "sub": "vs. 98 in Q1"},
        {"label": "Gross Margin", "value": "68%", "sub": "+3 pp vs. prior quarter"},
        {"label": "Churn", "value": "2.1%", "sub": "below 3% target"},
        {"label": "Headcount", "value": "84", "sub": "+6 since Q1"},
    ]
)

financials = report.add_section("02", "Financial Performance")
financials.add_subsection("Revenue trend", "s2-revenue")
financials.add_figure(fig_path, caption="Quarterly revenue for FY2026.", width="80%")
financials.add_subsection("Key ratios", "s2-ratios")
financials.add_table(
    headers=["Metric", "Q1", "Q2", "Change"],
    rows=[
        ["Gross margin", "65%", "68%", "+3 pp"],
        ["Operating margin", "18%", "22%", "+4 pp"],
        ["Customer acquisition cost", "$1,200", "$980", "-18%"],
    ],
)

outlook = report.add_section("03", "Outlook")
outlook.add_text(
    "Management expects revenue growth to continue through the second half "
    "of the fiscal year, with a target of $6.8 M for the full year."
)
outlook.add_notice("Note", "Forward-looking statements are subject to market risks.", kind="info")

qmd = report.save(OUT, filename="generic_company_report.qmd")
print(f"Generic company report written to: {qmd}")
print("Render with: quarto render", qmd, "--to html")
