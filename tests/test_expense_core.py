# -*- coding: utf-8 -*-
"""
tests/test_expense_core.py — expense_core.py の拡充テスト
既存の test_core.py を補完し、エッジケースやエラーケースをカバーする。
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from expense_core import (
    check_rows,
    make_summary,
    normalize_ok_rows,
    parse_amount,
    parse_date,
    read_csv,
    write_csv,
)


# ---------------------------------------------------------------------------
# parse_date の追加テスト
# ---------------------------------------------------------------------------

class TestParseDate:
    """日付パーサーのエッジケース。"""

    def test_valid_date(self) -> None:
        assert parse_date("2026-01-10") is True

    def test_slash_format(self) -> None:
        assert parse_date("2026/01/10") is False

    def test_empty_string(self) -> None:
        assert parse_date("") is False

    def test_month_13(self) -> None:
        """月が 13 の無効な日付。"""
        assert parse_date("2026-13-01") is False

    def test_day_32(self) -> None:
        """日が 32 の無効な日付。"""
        assert parse_date("2026-01-32") is False

    def test_no_separator(self) -> None:
        """区切りなしの日付文字列。"""
        assert parse_date("20260110") is False

    def test_leap_year_valid(self) -> None:
        """閏年の 2/29 は有効。"""
        assert parse_date("2024-02-29") is True

    def test_non_leap_year_feb29(self) -> None:
        """非閏年の 2/29 は無効。"""
        assert parse_date("2026-02-29") is False


# ---------------------------------------------------------------------------
# parse_amount の追加テスト
# ---------------------------------------------------------------------------

class TestParseAmount:
    """金額パーサーのエッジケース。"""

    def test_valid_positive(self) -> None:
        assert parse_amount("1200") is True

    def test_negative(self) -> None:
        """負の整数も int() で変換可能なので True。"""
        assert parse_amount("-500") is True

    def test_zero(self) -> None:
        assert parse_amount("0") is True

    def test_decimal(self) -> None:
        assert parse_amount("12.5") is False

    def test_alpha(self) -> None:
        assert parse_amount("abc") is False

    def test_empty(self) -> None:
        assert parse_amount("") is False

    def test_comma_separated(self) -> None:
        """カンマ区切りは int() では変換できない。"""
        assert parse_amount("1,200") is False

    def test_whitespace(self) -> None:
        """空白だけの文字列。"""
        assert parse_amount("  ") is False


# ---------------------------------------------------------------------------
# check_rows のテスト
# ---------------------------------------------------------------------------

class TestCheckRows:
    """入力チェックの振り分けテスト。"""

    def test_valid_row(self) -> None:
        """正常な行は ok_rows に入る。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, errors = check_rows(rows)
        assert len(ok) == 1
        assert len(errors) == 0

    def test_missing_column(self) -> None:
        """必須列が欠けていたらエラー。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A"}]  # category なし
        ok, errors = check_rows(rows)
        assert len(ok) == 0
        assert len(errors) == 1
        assert "列がない" in errors[0]["reason"]

    def test_empty_date(self) -> None:
        """date が空欄ならエラー。"""
        rows = [{"date": "", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, errors = check_rows(rows)
        assert len(errors) == 1
        assert "空欄" in errors[0]["reason"]

    def test_empty_merchant(self) -> None:
        """merchant が空欄ならエラー。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1

    def test_invalid_date_format(self) -> None:
        """日付形式が不正ならエラー。"""
        rows = [{"date": "2026/01/10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "日付の形式" in errors[0]["reason"]

    def test_invalid_amount(self) -> None:
        """金額が数字でなければエラー。"""
        rows = [{"date": "2026-01-10", "amount": "abc", "merchant": "A", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "金額が数字" in errors[0]["reason"]

    def test_duplicate_detection(self) -> None:
        """date+amount+merchant が重複したらエラー。"""
        row = {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}
        rows = [row, dict(row)]  # 同じ内容を 2 行
        ok, errors = check_rows(rows)
        assert len(ok) == 1  # 最初の 1 行だけ OK
        assert len(errors) == 1
        assert "重複" in errors[0]["reason"]

    def test_multiple_errors_in_one_row(self) -> None:
        """1 行に複数のエラーがある場合、理由が / で連結されるか。"""
        rows = [{"date": "", "amount": "abc", "merchant": "", "category": ""}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        reasons = errors[0]["reason"]
        assert " / " in reasons

    def test_row_number_starts_at_2(self) -> None:
        """行番号は 2 から始まるか（ヘッダが 1 行目）。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, _ = check_rows(rows)
        assert ok[0]["row"] == "2"


# ---------------------------------------------------------------------------
# normalize_ok_rows のテスト
# ---------------------------------------------------------------------------

class TestNormalizeOkRows:
    """型変換のテスト。"""

    def test_amount_becomes_int(self) -> None:
        """amount が int に変換されるか。"""
        ok = [{"row": "2", "date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        norm = normalize_ok_rows(ok)
        assert norm[0]["amount"] == 1200
        assert isinstance(norm[0]["amount"], int)

    def test_strips_whitespace(self) -> None:
        """各フィールドの前後空白が除去されるか。"""
        ok = [{"row": "2", "date": " 2026-01-10 ", "amount": " 1200 ", "merchant": " A ", "category": " 交通費 "}]
        norm = normalize_ok_rows(ok)
        assert norm[0]["date"] == "2026-01-10"
        assert norm[0]["merchant"] == "A"


# ---------------------------------------------------------------------------
# make_summary のテスト
# ---------------------------------------------------------------------------

class TestMakeSummary:
    """集計ロジックのテスト。"""

    def test_month_total(self) -> None:
        """月別合計が正しく集計されるか。"""
        rows = [
            {"row": "2", "date": "2026-01-10", "amount": 1000, "merchant": "A", "category": "交通費"},
            {"row": "3", "date": "2026-01-20", "amount": 2000, "merchant": "B", "category": "会議費"},
            {"row": "4", "date": "2026-02-05", "amount": 500, "merchant": "C", "category": "交通費"},
        ]
        summary = make_summary(rows, top_n=10)
        month_items = [r for r in summary if r["type"] == "month_total" and r["key"] != "month"]
        assert len(month_items) == 2
        jan = next(r for r in month_items if r["key"] == "2026-01")
        assert jan["value"] == "3000"

    def test_category_total(self) -> None:
        """カテゴリ別合計が正しいか。"""
        rows = [
            {"row": "2", "date": "2026-01-10", "amount": 1000, "merchant": "A", "category": "交通費"},
            {"row": "3", "date": "2026-01-20", "amount": 2000, "merchant": "B", "category": "交通費"},
        ]
        summary = make_summary(rows, top_n=10)
        cat_items = [r for r in summary if r["type"] == "category_total" and r["key"] != "category"]
        assert len(cat_items) == 1
        assert cat_items[0]["value"] == "3000"

    def test_merchant_top_n(self) -> None:
        """merchant_top が top_n で制限されるか。"""
        rows = [
            {"row": str(i), "date": "2026-01-10", "amount": i * 100, "merchant": f"M{i}", "category": "交通費"}
            for i in range(1, 6)
        ]
        summary = make_summary(rows, top_n=3)
        merchant_items = [r for r in summary if r["type"] == "merchant_top" and not r["key"].startswith("top_")]
        assert len(merchant_items) == 3

    def test_stats(self) -> None:
        """統計値（average, median, min, max, count）が出力されるか。"""
        rows = [
            {"row": "2", "date": "2026-01-10", "amount": 1000, "merchant": "A", "category": "交通費"},
            {"row": "3", "date": "2026-01-11", "amount": 3000, "merchant": "B", "category": "交通費"},
        ]
        summary = make_summary(rows, top_n=10)
        stats = {r["key"]: r["value"] for r in summary if r["type"] == "stats"}
        assert stats["count"] == "2"
        assert stats["min"] == "1000"
        assert stats["max"] == "3000"
        assert "average" in stats
        assert "median" in stats

    def test_empty_rows(self) -> None:
        """空のリストでも summary がエラーなく返るか。"""
        summary = make_summary([], top_n=10)
        stats = {r["key"]: r["value"] for r in summary if r["type"] == "stats"}
        assert stats["count"] == "0"
        assert "average" not in stats  # 0 件のときは平均等を出さない


# ---------------------------------------------------------------------------
# read_csv / write_csv のテスト
# ---------------------------------------------------------------------------

class TestCsvIO:
    """CSV 読み書きのテスト。"""

    def test_read_csv(self, tmp_path: Path) -> None:
        """正常な CSV を読めるか。"""
        p = tmp_path / "test.csv"
        p.write_text("date,amount,merchant,category\n2026-01-10,1200,A,交通費\n", encoding="utf-8")
        rows = read_csv(str(p))
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-10"

    def test_read_csv_empty_file(self, tmp_path: Path) -> None:
        """ヘッダなしの空ファイルで ValueError が出るか。"""
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="列名"):
            read_csv(str(p))

    def test_read_csv_file_not_found(self) -> None:
        """存在しないファイルで FileNotFoundError が出るか。"""
        with pytest.raises(FileNotFoundError):
            read_csv("nonexistent_file.csv")

    def test_write_csv(self, tmp_path: Path) -> None:
        """write_csv で正しく書き出されるか。"""
        p = tmp_path / "out.csv"
        rows = [{"a": "1", "b": "2"}]
        write_csv(str(p), rows, ["a", "b"])
        content = p.read_text(encoding="utf-8")
        assert "a,b" in content
        assert "1,2" in content
