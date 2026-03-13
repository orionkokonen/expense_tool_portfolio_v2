# -*- coding: utf-8 -*-
"""
tests/test_excel_export.py — excel_export.py の単体テスト
Excel レポートが正しく生成されるかを検証する。
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from expense_core import ExpenseRowNorm, IssueRow, SummaryRow, WarningRow
from excel_export import write_xlsx_report


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _sample_errors() -> list[IssueRow]:
    return [
        {
            "row": "2",
            "date": "2026/01/10",
            "amount": "abc",
            "merchant": "A",
            "category": "交通費",
            "reason": "日付の形式が違う / 金額が数字じゃない",
        }
    ]


def _sample_warnings() -> list[WarningRow]:
    return [
        {
            "kind": "category_unknown",
            "row": "3",
            "date": "2026-01-10",
            "month": "2026-01",
            "category": "食費",
            "merchant": "レストラン",
            "amount": "2000",
            "message": "未登録カテゴリ: 食費",
        }
    ]


def _sample_clean() -> list[ExpenseRowNorm]:
    return [
        {"row": "4", "date": "2026-01-10", "amount": 1200, "merchant": "カフェ", "category": "会議費"},
        {"row": "5", "date": "2026-02-15", "amount": 3500, "merchant": "ホテル", "category": "旅費"},
    ]


def _sample_summary() -> list[SummaryRow]:
    return [
        {"type": "month_total", "key": "month", "value": "total_amount"},
        {"type": "month_total", "key": "2026-01", "value": "1200"},
        {"type": "month_total", "key": "2026-02", "value": "3500"},
        {"type": "category_total", "key": "category", "value": "total_amount"},
        {"type": "category_total", "key": "会議費", "value": "1200"},
        {"type": "category_total", "key": "旅費", "value": "3500"},
        {"type": "stats", "key": "count", "value": "2"},
        {"type": "stats", "key": "average", "value": "2350"},
    ]


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------

class TestWriteXlsxReport:
    """Excel レポート生成のテスト。"""

    def test_creates_file(self, tmp_path: Path) -> None:
        """ファイルが生成されるか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=_sample_errors(),
            warnings=_sample_warnings(),
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        assert xlsx.exists()

    def test_sheet_names(self, tmp_path: Path) -> None:
        """期待されるシート名がすべて存在するか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=_sample_errors(),
            warnings=_sample_warnings(),
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        wb = load_workbook(xlsx)
        assert set(wb.sheetnames) == {"Errors", "Warnings", "Clean", "Summary", "Charts"}

    def test_errors_sheet_content(self, tmp_path: Path) -> None:
        """Errors シートにデータが書き込まれているか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=_sample_errors(),
            warnings=_sample_warnings(),
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        wb = load_workbook(xlsx)
        ws = wb["Errors"]
        # ヘッダ行 + データ 1 行 = 2 行
        assert ws.max_row == 2
        # ヘッダの先頭列
        assert ws.cell(row=1, column=1).value == "row"

    def test_clean_sheet_row_count(self, tmp_path: Path) -> None:
        """Clean シートに正しい行数が書き込まれているか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=_sample_errors(),
            warnings=_sample_warnings(),
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        wb = load_workbook(xlsx)
        ws = wb["Clean"]
        # ヘッダ + 2 行 = 3
        assert ws.max_row == 3

    def test_header_is_bold(self, tmp_path: Path) -> None:
        """ヘッダ行が太字になっているか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=[],
            warnings=[],
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        wb = load_workbook(xlsx)
        ws = wb["Clean"]
        assert ws.cell(row=1, column=1).font.bold is True

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """出力先の親フォルダが自動作成されるか。"""
        xlsx = tmp_path / "sub" / "dir" / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
        )
        assert xlsx.exists()

    def test_empty_data(self, tmp_path: Path) -> None:
        """すべて空でもエラーなく生成されるか。"""
        xlsx = tmp_path / "empty.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=[],
            warnings=[],
            clean=[],
            summary=[],
        )
        assert xlsx.exists()
        wb = load_workbook(xlsx)
        assert "Charts" in wb.sheetnames
