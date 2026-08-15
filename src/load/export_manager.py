"""Automated CSV, Excel, and PDF export of mart/report tables, for
stakeholders who want a file instead of querying the warehouse directly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fpdf import FPDF, XPos, YPos

MAX_PDF_ROWS = 50


def export_to_csv(df: pd.DataFrame, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def export_to_excel(tables: dict[str, pd.DataFrame], output_path: str) -> str:
    """Writes each DataFrame to its own sheet, named after its dict key
    (truncated to Excel's 31-character sheet name limit)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return output_path


def export_to_pdf(df: pd.DataFrame, output_path: str, title: str | None = None) -> str:
    """Renders a DataFrame as a simple tabular PDF report. Truncates to
    MAX_PDF_ROWS rows since PDF is meant for a quick-glance summary, not
    bulk data export (use CSV/Excel for that)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    if title:
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    pdf.set_font("Helvetica", size=8)
    columns = list(df.columns)
    col_width = 277 / max(len(columns), 1)

    for col in columns:
        pdf.cell(col_width, 6, str(col), border=1)
    pdf.ln()

    for _, row in df.head(MAX_PDF_ROWS).iterrows():
        for col in columns:
            pdf.cell(col_width, 6, str(row[col]), border=1)
        pdf.ln()

    pdf.output(output_path)
    return output_path


def export_marts(marts: dict[str, pd.DataFrame], output_dir: str, formats: tuple[str, ...] = ("csv",)) -> dict[str, list[str]]:
    """Exports each mart table in each requested format ("csv", "excel",
    "pdf"). Excel is written once as a single multi-sheet workbook rather
    than per-mart."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[str]] = {name: [] for name in marts}

    if "csv" in formats:
        for name, df in marts.items():
            path = export_to_csv(df, str(output_dir_path / f"{name}.csv"))
            written[name].append(path)

    if "excel" in formats:
        excel_path = export_to_excel(marts, str(output_dir_path / "marts.xlsx"))
        for name in marts:
            written[name].append(excel_path)

    if "pdf" in formats:
        for name, df in marts.items():
            path = export_to_pdf(df, str(output_dir_path / f"{name}.pdf"), title=name)
            written[name].append(path)

    return written
