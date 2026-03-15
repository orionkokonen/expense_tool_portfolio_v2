# -*- coding: utf-8 -*-
"""
tests/test_expense_core.py: expense_core.py の単体テスト

このファイルは、経費ツールの「中心ロジック」が壊れていないかを確認する。
特に初心者のうちは、
  1. 入力チェック
  2. 正規化
  3. 集計
  4. CSV 入出力
の 4 つに分けて読むと、全体像をつかみやすい。

補足:
  テストデータにも `ExpenseRow` や `ExpenseRowNorm` の型注釈を付けている。
  これは実行のためというより、「本番コードが期待する形と同じか」を
  型チェックツールにも確認してもらうための目印になる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from expense_core import (
    ExpenseRow,
    ExpenseRowNorm,
    check_rows,
    make_summary,
    normalize_ok_rows,
    parse_amount,
    parse_date,
    read_csv,
    sanitize_cell,
    write_csv,
)


class TestParseDate:
    """日付文字列のチェック関数 `parse_date()` のテスト。"""

    def test_valid_date(self) -> None:
        """正しい YYYY-MM-DD は受け入れるか。"""
        assert parse_date("2026-01-10") is True

    def test_slash_format_is_invalid(self) -> None:
        """見た目が近くても YYYY/MM/DD は不正として弾くか。"""
        assert parse_date("2026/01/10") is False

    def test_empty_string_is_invalid(self) -> None:
        """空文字は当然日付ではないので False になるか。"""
        assert parse_date("") is False

    def test_invalid_month_is_rejected(self) -> None:
        """13 月のような存在しない日付を弾けるか。"""
        assert parse_date("2026-13-01") is False

    def test_invalid_day_is_rejected(self) -> None:
        """32 日のような存在しない日付を弾けるか。"""
        assert parse_date("2026-01-32") is False

    def test_no_separator_is_invalid(self) -> None:
        """区切りなしの 20260110 を不正扱いできるか。"""
        assert parse_date("20260110") is False

    def test_leap_year_date_is_valid(self) -> None:
        """うるう年の 2/29 は正しい日付として通るか。"""
        assert parse_date("2024-02-29") is True

    def test_non_leap_year_date_is_invalid(self) -> None:
        """うるう年でない 2/29 は不正として弾くか。"""
        assert parse_date("2026-02-29") is False


class TestParseAmount:
    """金額文字列のチェック関数 `parse_amount()` のテスト。"""

    def test_positive_int_is_valid(self) -> None:
        """普通の整数文字列を受け入れるか。"""
        assert parse_amount("1200") is True

    def test_negative_int_is_valid(self) -> None:
        """負の整数も int としては解釈できるか。"""
        assert parse_amount("-500") is True

    def test_zero_is_valid(self) -> None:
        """0 も整数として扱えるか。"""
        assert parse_amount("0") is True

    def test_decimal_is_invalid(self) -> None:
        """小数は「整数のみ」のルールでは不正になるか。"""
        assert parse_amount("12.5") is False

    def test_alpha_is_invalid(self) -> None:
        """文字列だけの入力を弾けるか。"""
        assert parse_amount("abc") is False

    def test_empty_is_invalid(self) -> None:
        """空文字を弾けるか。"""
        assert parse_amount("") is False

    def test_comma_separated_is_invalid(self) -> None:
        """カンマ入り表記を弾けるか。"""
        assert parse_amount("1,200") is False

    def test_whitespace_only_is_invalid(self) -> None:
        """空白だけの入力を弾けるか。"""
        assert parse_amount("  ") is False


class TestCheckRows:
    """`check_rows()` のテスト。

    この関数は、CSV の各行を
    「次の処理へ進める OK 行」と「修正が必要な error 行」に分ける。
    """

    def test_valid_row_goes_to_ok_rows(self) -> None:
        """正常な 1 行が ok_rows に入るか。"""
        rows = [
            {
                "date": "2026-01-10",
                "amount": "1200",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        ok_rows, errors = check_rows(rows)
        assert len(ok_rows) == 1
        assert len(errors) == 0

    def test_missing_column_becomes_error(self) -> None:
        """必須列が欠けている行を error として拾えるか。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A"}]
        ok_rows, errors = check_rows(rows)
        assert len(ok_rows) == 0
        assert len(errors) == 1
        assert "列がない" in errors[0]["reason"]

    def test_empty_required_field_becomes_error(self) -> None:
        """必須項目が空欄なら error になるか。"""
        rows = [
            {
                "date": "",
                "amount": "1200",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "空欄" in errors[0]["reason"]

    def test_invalid_date_becomes_error(self) -> None:
        """日付形式が違う行を error にできるか。"""
        rows = [
            {
                "date": "2026/01/10",
                "amount": "1200",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "日付の形式" in errors[0]["reason"]

    def test_invalid_amount_becomes_error(self) -> None:
        """金額が数字でない行を error にできるか。"""
        rows = [
            {
                "date": "2026-01-10",
                "amount": "abc",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "金額" in errors[0]["reason"]

    def test_duplicate_row_passes_check_rows(self) -> None:
        """重複行は check_rows では弾かず、両方とも ok_rows に入るか。

        重複判定は check_rows の責務から外し、warning として別途検出する。
        """
        row = {
            "date": "2026-01-10",
            "amount": "1200",
            "merchant": "A",
            "category": "交通費",
        }
        ok_rows, errors = check_rows([row, dict(row)])
        assert len(ok_rows) == 2
        assert len(errors) == 0

    def test_multiple_errors_are_joined(self) -> None:
        """1 行に複数の問題があれば、理由が連結されるか。"""
        rows = [{"date": "", "amount": "abc", "merchant": "", "category": ""}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert " / " in errors[0]["reason"]

    def test_row_number_starts_from_2(self) -> None:
        """CSV の 1 行目はヘッダなので、データ行番号は 2 から始まるか。"""
        rows = [
            {
                "date": "2026-01-10",
                "amount": "1200",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        ok_rows, _ = check_rows(rows)
        assert ok_rows[0]["row"] == "2"


class TestNormalizeOkRows:
    """`normalize_ok_rows()` のテスト。

    入力チェックを通った行を、計算しやすい型へ変換する。
    ここでは amount が文字列から整数になる点が特に重要。
    """

    def test_amount_becomes_int(self) -> None:
        """amount が文字列から int に変わるか。"""
        # ExpenseRow は「入力チェック後だが、まだ amount は文字列」の形。
        # テスト側でもこの型を使うと、関数に渡す前提が読みやすくなる。
        ok_rows: list[ExpenseRow] = [
            {
                "row": "2",
                "date": "2026-01-10",
                "amount": "1200",
                "merchant": "A",
                "category": "交通費",
            }
        ]
        normalized = normalize_ok_rows(ok_rows)
        assert normalized[0]["amount"] == 1200
        assert isinstance(normalized[0]["amount"], int)

    def test_whitespace_is_stripped(self) -> None:
        """前後の空白を除去してから正規化するか。"""
        ok_rows: list[ExpenseRow] = [
            {
                "row": "2",
                "date": " 2026-01-10 ",
                "amount": " 1200 ",
                "merchant": " A ",
                "category": " 交通費 ",
            }
        ]
        normalized = normalize_ok_rows(ok_rows)
        assert normalized[0]["date"] == "2026-01-10"
        assert normalized[0]["merchant"] == "A"
        assert normalized[0]["category"] == "交通費"


class TestMakeSummary:
    """`make_summary()` のテスト。

    集計ロジックは「正しい件数・正しい合計」が最優先。
    そのため、ここでは出力の見た目ではなく中身を確認する。
    """

    def test_month_total_is_aggregated(self) -> None:
        """月別合計が正しく集計されるか。"""
        # make_summary() は「正規化ずみの行」を受け取る関数なので、
        # ここでは ExpenseRowNorm を使って amount を整数でそろえておく。
        rows: list[ExpenseRowNorm] = [
            {
                "row": "2",
                "date": "2026-01-10",
                "amount": 1000,
                "merchant": "A",
                "category": "交通費",
            },
            {
                "row": "3",
                "date": "2026-01-20",
                "amount": 2000,
                "merchant": "B",
                "category": "会議費",
            },
            {
                "row": "4",
                "date": "2026-02-05",
                "amount": 500,
                "merchant": "C",
                "category": "交通費",
            },
        ]
        summary = make_summary(rows, top_n=10)
        month_items = [
            row
            for row in summary
            if row["type"] == "month_total" and row["key"] != "month"
        ]
        january = next(row for row in month_items if row["key"] == "2026-01")
        assert len(month_items) == 2
        assert january["value"] == "3000"

    def test_category_total_is_aggregated(self) -> None:
        """カテゴリ別合計が正しく集計されるか。"""
        rows: list[ExpenseRowNorm] = [
            {
                "row": "2",
                "date": "2026-01-10",
                "amount": 1000,
                "merchant": "A",
                "category": "交通費",
            },
            {
                "row": "3",
                "date": "2026-01-20",
                "amount": 2000,
                "merchant": "B",
                "category": "交通費",
            },
        ]
        summary = make_summary(rows, top_n=10)
        category_items = [
            row
            for row in summary
            if row["type"] == "category_total" and row["key"] != "category"
        ]
        assert len(category_items) == 1
        assert category_items[0]["value"] == "3000"

    def test_merchant_top_is_limited_by_top_n(self) -> None:
        """top_n の件数だけ支出先が残るか。"""
        rows: list[ExpenseRowNorm] = [
            {
                "row": str(i),
                "date": "2026-01-10",
                "amount": i * 100,
                "merchant": f"M{i}",
                "category": "交通費",
            }
            for i in range(1, 6)
        ]
        summary = make_summary(rows, top_n=3)
        merchant_items = [
            row
            for row in summary
            if row["type"] == "merchant_top" and not row["key"].startswith("top_")
        ]
        assert len(merchant_items) == 3

    def test_stats_are_generated(self) -> None:
        """count / min / max / average / median が出るか。"""
        rows: list[ExpenseRowNorm] = [
            {
                "row": "2",
                "date": "2026-01-10",
                "amount": 1000,
                "merchant": "A",
                "category": "交通費",
            },
            {
                "row": "3",
                "date": "2026-01-11",
                "amount": 3000,
                "merchant": "B",
                "category": "交通費",
            },
        ]
        summary = make_summary(rows, top_n=10)
        stats = {row["key"]: row["value"] for row in summary if row["type"] == "stats"}
        assert stats["count"] == "2"
        assert stats["min"] == "1000"
        assert stats["max"] == "3000"
        assert "average" in stats
        assert "median" in stats

    def test_empty_rows_only_emit_count(self) -> None:
        """データが 0 件でも count は出て、平均などは出ないか。"""
        # 空リストは中身がないので、何の型のリストかを mypy だけでは判断しにくい。
        # 先に型を書いておくと、「集計対象の空データ」だと明確に伝えられる。
        empty_rows: list[ExpenseRowNorm] = []
        summary = make_summary(empty_rows, top_n=10)
        stats = {row["key"]: row["value"] for row in summary if row["type"] == "stats"}
        assert stats["count"] == "0"
        assert "average" not in stats


class TestSanitizeCell:
    """`sanitize_cell()` のテスト。

    CSV / Excel 出力時に数式インジェクションを防ぐための無害化関数。
    """

    def test_equals_prefix(self) -> None:
        """= で始まる文字列に ' が付くか。"""
        assert sanitize_cell("=SUM(A1)") == "'=SUM(A1)"

    def test_plus_prefix(self) -> None:
        """+ で始まる文字列に ' が付くか。"""
        assert sanitize_cell("+cmd") == "'+cmd"

    def test_at_prefix(self) -> None:
        """@ で始まる文字列に ' が付くか。"""
        assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_minus_non_numeric(self) -> None:
        """非数値の - 始まり文字列に ' が付くか。"""
        assert sanitize_cell("-cmd|stuff") == "'-cmd|stuff"

    def test_minus_numeric_not_sanitized(self) -> None:
        """負の整数（返金・訂正）は壊さないか。"""
        assert sanitize_cell("-500") == "-500"

    def test_normal_string_unchanged(self) -> None:
        """通常の文字列は変わらないか。"""
        assert sanitize_cell("カフェA") == "カフェA"

    def test_empty_string_unchanged(self) -> None:
        """空文字はそのまま返るか。"""
        assert sanitize_cell("") == ""

    def test_zero_string_unchanged(self) -> None:
        """数値 "0" はそのまま返るか。"""
        assert sanitize_cell("0") == "0"


class TestCheckRowsFormatOnly:
    """check_rows が形式エラーだけを返すことのテスト。"""

    def test_only_format_errors(self) -> None:
        """形式エラーのみ検出し、重複はエラーに含めないか。"""
        rows = [
            {"date": "2026/01/10", "amount": "abc", "merchant": "A", "category": "交通費"},
            {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"},
            {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"},
        ]
        ok_rows, errors = check_rows(rows)
        assert len(errors) == 1  # 形式エラーのみ
        assert len(ok_rows) == 2  # 重複行も通る
        assert "重複" not in errors[0]["reason"]


class TestCsvIO:
    """CSV の読み書き関数のテスト。"""

    def test_read_csv(self, tmp_path: Path) -> None:
        """通常の CSV を読み込めるか。"""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "date,amount,merchant,category\n2026-01-10,1200,A,交通費\n",
            encoding="utf-8",
        )
        rows = read_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-10"

    def test_read_csv_empty_file_raises(self, tmp_path: Path) -> None:
        """ヘッダなしファイルは ValueError になるか。"""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="列名"):
            read_csv(str(csv_path))

    def test_read_csv_missing_file_raises(self) -> None:
        """存在しないファイルは FileNotFoundError になるか。"""
        with pytest.raises(FileNotFoundError):
            read_csv("missing.csv")

    def test_write_csv(self, tmp_path: Path) -> None:
        """辞書リストを CSV に書き出せるか。"""
        csv_path = tmp_path / "out.csv"
        write_csv(str(csv_path), [{"a": "1", "b": "2"}], ["a", "b"])
        content = csv_path.read_text(encoding="utf-8")
        assert "a,b" in content
        assert "1,2" in content
