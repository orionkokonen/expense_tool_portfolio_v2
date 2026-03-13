# -*- coding: utf-8 -*-
"""
tests/test_html_report.py — HTML レポート生成のテスト。

ここで見ていること:
  - JSON を HTML に埋め込むときに危険な文字列をそのまま出さないか
  - 表の HTML が正しく組み立てられるか
  - レポート用ファイルが必要な内容つきで出力されるか

特に大事な点:
  XSS は「悪意ある文字列がブラウザで実行されてしまう問題」。
  画面表示のテストに見えても、安全性を守る確認として重要になる。
"""
from __future__ import annotations

from pathlib import Path

from expense_core import SummaryRow
from html_report import (
    MAX_TABLE_ROWS,
    _safe_json_dumps,
    table_html,
    write_html_report,
)

# import を整理しておくと、「標準機能」「自作コード」の境界が一目で分かる。
# 先頭の形を毎回そろえるのは、読みやすさだけでなく lint エラーの予防にも役立つ。

# ---------------------------------------------------------------------------
# ヘルパー — テストデータを作る補助関数
# ---------------------------------------------------------------------------

def _sample_summary() -> list[SummaryRow]:
    """テスト用の最小限の summary データを返す。

    実際の make_summary() が返す形式に合わせて、
    見出し行（key="month"）とデータ行（key="2026-01"）のペアを作る。
    本番に近い形は保ちつつ、量は最小限にして
    「何を試したいテストか」が埋もれないようにしている。
    """
    return [
        {"type": "month_total", "key": "month", "value": "total_amount"},
        {"type": "month_total", "key": "2026-01", "value": "5000"},
        {"type": "category_total", "key": "category", "value": "total_amount"},
        {"type": "category_total", "key": "交通費", "value": "5000"},
    ]


# ---------------------------------------------------------------------------
# _safe_json_dumps のテスト
# テーマ: HTML 内の <script> タグに埋め込む JSON が安全に生成されるか
# ---------------------------------------------------------------------------

class TestSafeJsonDumps:
    """JSON を安全に埋め込めるかを見るテスト。"""

    def test_basic_list(self) -> None:
        """通常のリストがそのまま JSON 文字列になるか。"""
        result = _safe_json_dumps(["2026-01", "2026-02"])
        assert result == '["2026-01", "2026-02"]'

    def test_int_list(self) -> None:
        """整数リストもそのまま JSON になるか。"""
        result = _safe_json_dumps([100, 200])
        assert result == "[100, 200]"

    def test_script_tag_escaped(self) -> None:
        """XSS 攻撃用の "</script>" が無害化されるか。

        "</" がそのまま残っていると、ブラウザが script 終了タグと誤認する。
        "<\\/" に置換されていれば安全。
        """
        result = _safe_json_dumps(["</script><script>alert(1)"])
        assert "</" not in result       # 危険な形が残っていないこと
        assert r"<\/" in result         # エスケープ後の安全な形があること

    def test_empty_list(self) -> None:
        """空リストでもエラーにならず "[]" が返るか。"""
        result = _safe_json_dumps([])
        assert result == "[]"


# ---------------------------------------------------------------------------
# table_html のテスト
# テーマ: HTML テーブルの生成と、セル内容の XSS 対策
# ---------------------------------------------------------------------------

class TestTableHtml:
    """HTML テーブル生成のテスト。"""

    def test_basic_table(self) -> None:
        """最低限のデータで <table> が正しく組み立てられるか。"""
        rows = [{"a": "1", "b": "2"}]
        html = table_html(rows, ["a", "b"])
        assert "<table>" in html
        assert "<th>a</th>" in html     # ヘッダセル
        assert "<td>1</td>" in html     # データセル

    def test_empty_rows(self) -> None:
        """データが 0 件のとき、テーブルではなく「なし」と表示されるか。"""
        html = table_html([], ["a", "b"])
        assert "なし" in html
        assert "<table>" not in html    # 空テーブルは生成しない

    def test_xss_prevention(self) -> None:
        """セルに "<script>" が入っていても、エスケープされて実行されないか。

        escape() により "<" → "&lt;"、">" → "&gt;" に変換される。
        """
        rows = [{"name": "<script>alert('xss')</script>"}]
        html = table_html(rows, ["name"])
        assert "<script>" not in html          # 生の script タグがないこと
        assert "&lt;script&gt;" in html        # エスケープ済みであること

    def test_special_chars_in_header(self) -> None:
        """ヘッダ（列名）にも同じ XSS 対策が適用されるか。"""
        html = table_html([{"<b>": "val"}], ["<b>"])
        assert "&lt;b&gt;" in html


# ---------------------------------------------------------------------------
# write_html_report のテスト
# テーマ: ファイル生成・タイトル表示・CDN フォールバック・ディレクトリ自動作成
# ---------------------------------------------------------------------------

class TestWriteHtmlReport:
    """HTML レポート生成の結合テスト。

    tmp_path は pytest が提供する一時フォルダ。
    テストごとに別フォルダが用意されるため、テスト同士が干渉しない。
    """

    def test_creates_file(self, tmp_path: Path) -> None:
        """関数を呼ぶと HTML ファイルが生成されるか。"""
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
        """引数で渡したタイトルが HTML ファイルの中に含まれるか。"""
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
        """タイトルに悪意ある HTML タグが含まれていても無害化されるか。"""
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
        assert "<script>alert(1)</script>" not in content  # 生タグがないこと
        assert "&lt;script&gt;" in content                 # エスケープ済みであること

    def test_chart_js_cdn(self, tmp_path: Path) -> None:
        """Chart.js を読み込む CDN の URL が HTML に含まれるか。"""
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
        """CDN が読み込めなかった場合のフォールバック処理が含まれるか。"""
        html_path = tmp_path / "report.html"
        write_html_report(
            path=html_path,
            errors=[],
            warnings=[],
            clean=[],
            summary=_sample_summary(),
        )
        content = html_path.read_text(encoding="utf-8")
        # `typeof` は「その名前の変数が存在するか」を安全に調べる書き方。
        # ここでは Chart.js が読み込めたかを確認するために使っている。
        assert "typeof Chart === 'undefined'" in content

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """出力先の親フォルダが存在しなくても自動作成されるか。"""
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
        """MAX_TABLE_ROWS 定数が正の整数として定義されているか。"""
        assert isinstance(MAX_TABLE_ROWS, int)
        assert MAX_TABLE_ROWS > 0
