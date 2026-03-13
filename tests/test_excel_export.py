# -*- coding: utf-8 -*-
"""
tests/test_excel_export.py — excel_export.py の単体テスト

検証のポイント:
  - ファイルが生成されるか
  - 期待するシート構成になっているか
  - データが正しい位置に書き込まれているか
  - 見た目（太字ヘッダ）が適用されているか
  - フォルダ自動作成・空データでのエラー耐性

openpyxl.load_workbook で生成済みファイルを読み直して検証する。
「作る側」と「読む側」を分離することで、出力が壊れていれば確実に検出できる。
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from expense_core import ExpenseRowNorm, IssueRow, SummaryRow, WarningRow
from excel_export import write_xlsx_report


# ---------------------------------------------------------------------------
# ヘルパー — テストデータを作る補助関数
# 実際のパイプラインが返す形式と同じ辞書構造を再現する。
# ---------------------------------------------------------------------------

def _sample_errors() -> list[IssueRow]:
    """エラー行のサンプル（日付形式違い + 金額が数字でない）。"""
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
    """警告行のサンプル（未登録カテゴリ）。"""
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
    """クリーン行のサンプル（amount が int になっている正規化済みデータ）。"""
    return [
        {"row": "4", "date": "2026-01-10", "amount": 1200, "merchant": "カフェ", "category": "会議費"},
        {"row": "5", "date": "2026-02-15", "amount": 3500, "merchant": "ホテル", "category": "旅費"},
    ]


def _sample_summary() -> list[SummaryRow]:
    """集計結果のサンプル。type でフィルタして使う想定。"""
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
    """Excel レポート生成のテスト。

    tmp_path: pytest が提供する一時フォルダ（テストごとに別フォルダが作られる）。
    """

    def test_creates_file(self, tmp_path: Path) -> None:
        """関数を呼ぶと .xlsx ファイルが作られるか。"""
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
        """期待する 5 つのシートがすべて存在するか。"""
        xlsx = tmp_path / "report.xlsx"
        write_xlsx_report(
            path=xlsx,
            errors=_sample_errors(),
            warnings=_sample_warnings(),
            clean=_sample_clean(),
            summary=_sample_summary(),
        )
        wb = load_workbook(xlsx)
        # set() = 順番を無視して「同じ要素を持つか」だけで比較できる集合
        assert set(wb.sheetnames) == {"Errors", "Warnings", "Clean", "Summary", "Charts"}

    def test_errors_sheet_content(self, tmp_path: Path) -> None:
        """Errors シートにヘッダ + データが正しく書き込まれているか。"""
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
        assert ws.max_row == 2                          # ヘッダ 1 行 + データ 1 行
        assert ws.cell(row=1, column=1).value == "row"  # ヘッダの先頭列

    def test_clean_sheet_row_count(self, tmp_path: Path) -> None:
        """Clean シートの行数が「ヘッダ + データ件数」になっているか。"""
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
        assert ws.max_row == 3  # ヘッダ 1 行 + データ 2 行

    def test_header_is_bold(self, tmp_path: Path) -> None:
        """ヘッダ行のフォントが太字（bold）になっているか。

        見た目のテストも書いておくと、スタイル設定コードを消してしまったときに気づける。
        """
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
        """出力先の途中のフォルダが存在しなくても自動作成されるか。"""
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
        """全データが空でもエラーにならず生成できるか（境界値テスト）。"""
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
