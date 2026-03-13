# -*- coding: utf-8 -*-
"""
tests/test_html_report.py — html_report.py の単体テスト
HTML レポートの生成と XSS 対策を検証する。
"""

from __future__ import annotations

from pathlib import Path

from expense_core import SummaryRow
from html_report import MAX_TABLE_ROWS, _safe_json_dumps, table_html, write_html_report


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _sample_summary() -> list[SummaryRow]:
    return [
        {"type": "month_total", "key": "month", "value": "total_amount"},
        {"type": "month_total", "key": "2026-01", "value": "5000"},
        {"type": "category_total", "key": "category", "value": "total_amount"},
        {"type": "category_total", "key": "交通費", "value": "5000"},
    ]


# ---------------------------------------------------------------------------
# _safe_json_dumps のテスト
# ---------------------------------------------------------------------------

class TestSafeJsonDumps:
    """JSON 埋め込みの安全性テスト。"""

    def test_basic_list(self) -> None:
        result = _safe_json_dumps(["2026-01", "2026-02"])
        assert result == '["2026-01", "2026-02"]'

    def test_int_list(self) -> None:
        result = _safe_json_dumps([100, 200])
        assert result == "[100, 200]"

    def test_script_tag_escaped(self) -> None:
        """</script> が埋め込まれていても安全にエスケープされるか。"""
        result = _safe_json_dumps(["</script><script>alert(1)"])
        assert "</" not in result
        assert r"<\/" in result

    def test_empty_list(self) -> None:
        result = _safe_json_dumps([])
        assert result == "[]"


# ---------------------------------------------------------------------------
# table_html のテスト
# ---------------------------------------------------------------------------

class TestTableHtml:
    """HTML テーブル生成のテスト。"""

    def test_basic_table(self) -> None:
        rows = [{"a": "1", "b": "2"}]
        html = table_html(rows, ["a", "b"])
        assert "<table>" in html
        assert "<th>a</th>" in html
        assert "<td>1</td>" in html

    def test_empty_rows(self) -> None:
        """空リストのとき「なし」表示になるか。"""
        html = table_html([], ["a", "b"])
        assert "なし" in html
        assert "<table>" not in html

    def test_xss_prevention(self) -> None:
        """<script> タグが escape されるか。"""
        rows = [{"name": "<script>alert('xss')</script>"}]
        html = table_html(rows, ["name"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_special_chars_in_header(self) -> None:
        """ヘッダにも escape が適用されるか。"""
        html = table_html([{"<b>": "val"}], ["<b>"])
        assert "&lt;b&gt;" in html


# ---------------------------------------------------------------------------
# write_html_report のテスト
# ---------------------------------------------------------------------------

class TestWriteHtmlReport:
    """HTML レポート生成の結合テスト。"""

    def test_creates_file(self, tmp_path: Path) -> None:
        """ファイルが生成されるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
            title="テストレポート",
        )
        assert html_path.exists()

    def test_title_in_html(self, tmp_path: Path) -> None:
        """タイトルが HTML に含まれるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
            title="テストレポート",
        )
        content = html_path.read_text(encoding="utf-8")
        assert "テストレポート" in content

    def test_title_xss_prevention(self, tmp_path: Path) -> None:
        """タイトルに HTML タグが含まれていても escape されるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
            title="<script>alert(1)</script>",
        )
        content = html_path.read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in content
        assert "&lt;script&gt;" in content

    def test_chart_js_cdn(self, tmp_path: Path) -> None:
        """Chart.js の CDN スクリプトタグが含まれるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
        )
        content = html_path.read_text(encoding="utf-8")
        assert "cdn.jsdelivr.net/npm/chart.js" in content

    def test_cdn_fallback_message(self, tmp_path: Path) -> None:
        """CDN フォールバックの JavaScript コードが含まれるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
        )
        content = html_path.read_text(encoding="utf-8")
        assert "typeof Chart === 'undefined'" in content

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """出力先の親フォルダが自動作成されるか。"""
        html_path = tmp_path / "sub" / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
        )
        assert html_path.exists()

    def test_max_table_rows_constant(self) -> None:
        """MAX_TABLE_ROWS 定数が正の整数か。"""
        assert isinstance(MAX_TABLE_ROWS, int)
        assert MAX_TABLE_ROWS > 0
