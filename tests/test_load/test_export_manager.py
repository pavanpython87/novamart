import pandas as pd

from src.load.export_manager import export_marts, export_to_csv, export_to_excel, export_to_pdf

DF = pd.DataFrame([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])


def test_export_to_csv(tmp_path):
    output_path = tmp_path / "out.csv"
    export_to_csv(DF, str(output_path))
    assert output_path.exists()
    result = pd.read_csv(output_path)
    assert len(result) == 2


def test_export_to_excel_writes_multi_sheet_workbook(tmp_path):
    output_path = tmp_path / "out.xlsx"
    export_to_excel({"sheet1": DF, "sheet2": DF}, str(output_path))
    assert output_path.exists()
    sheets = pd.read_excel(output_path, sheet_name=None)
    assert set(sheets.keys()) == {"sheet1", "sheet2"}


def test_export_to_pdf_creates_file(tmp_path):
    output_path = tmp_path / "out.pdf"
    export_to_pdf(DF, str(output_path), title="Test Report")
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_export_marts_csv_only(tmp_path):
    written = export_marts({"mart_a": DF, "mart_b": DF}, str(tmp_path), formats=("csv",))
    assert (tmp_path / "mart_a.csv").exists()
    assert (tmp_path / "mart_b.csv").exists()
    assert written["mart_a"] == [str(tmp_path / "mart_a.csv")]


def test_export_marts_all_formats(tmp_path):
    written = export_marts({"mart_a": DF}, str(tmp_path), formats=("csv", "excel", "pdf"))
    assert (tmp_path / "mart_a.csv").exists()
    assert (tmp_path / "marts.xlsx").exists()
    assert (tmp_path / "mart_a.pdf").exists()
    assert len(written["mart_a"]) == 3
