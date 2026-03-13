# -*- coding: utf-8 -*-
"""
tests/test_expense_core.py: expense_core.py のテスト
"""

from __future__ import annotations

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


class TestParseDate:
    def test_valid_date(self) -> None:
        assert parse_date("2026-01-10") is True

    def test_slash_format_is_invalid(self) -> None:
        assert parse_date("2026/01/10") is False

    def test_empty_string_is_invalid(self) -> None:
        assert parse_date("") is False

    def test_invalid_month_is_rejected(self) -> None:
        assert parse_date("2026-13-01") is False

    def test_invalid_day_is_rejected(self) -> None:
        assert parse_date("2026-01-32") is False

    def test_no_separator_is_invalid(self) -> None:
        assert parse_date("20260110") is False

    def test_leap_year_date_is_valid(self) -> None:
        assert parse_date("2024-02-29") is True

    def test_non_leap_year_date_is_invalid(self) -> None:
        assert parse_date("2026-02-29") is False


class TestParseAmount:
    def test_positive_int_is_valid(self) -> None:
        assert parse_amount("1200") is True

    def test_negative_int_is_valid(self) -> None:
        assert parse_amount("-500") is True

    def test_zero_is_valid(self) -> None:
        assert parse_amount("0") is True

    def test_decimal_is_invalid(self) -> None:
        assert parse_amount("12.5") is False

    def test_alpha_is_invalid(self) -> None:
        assert parse_amount("abc") is False

    def test_empty_is_invalid(self) -> None:
        assert parse_amount("") is False

    def test_comma_separated_is_invalid(self) -> None:
        assert parse_amount("1,200") is False

    def test_whitespace_only_is_invalid(self) -> None:
        assert parse_amount("  ") is False


class TestCheckRows:
    def test_valid_row_goes_to_ok_rows(self) -> None:
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
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A"}]
        ok_rows, errors = check_rows(rows)
        assert len(ok_rows) == 0
        assert len(errors) == 1
        assert "列がない" in errors[0]["reason"]

    def test_empty_required_field_becomes_error(self) -> None:
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

    def test_duplicate_row_is_detected(self) -> None:
        row = {
            "date": "2026-01-10",
            "amount": "1200",
            "merchant": "A",
            "category": "交通費",
        }
        ok_rows, errors = check_rows([row, dict(row)])
        assert len(ok_rows) == 1
        assert len(errors) == 1
        assert "重複" in errors[0]["reason"]

    def test_multiple_errors_are_joined(self) -> None:
        rows = [{"date": "", "amount": "abc", "merchant": "", "category": ""}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert " / " in errors[0]["reason"]

    def test_row_number_starts_from_2(self) -> None:
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
    def test_amount_becomes_int(self) -> None:
        ok_rows = [
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
        ok_rows = [
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
    def test_month_total_is_aggregated(self) -> None:
        rows = [
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
        rows = [
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
        rows = [
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
        rows = [
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
        summary = make_summary([], top_n=10)
        stats = {row["key"]: row["value"] for row in summary if row["type"] == "stats"}
        assert stats["count"] == "0"
        assert "average" not in stats


class TestCsvIO:
    def test_read_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "date,amount,merchant,category\n2026-01-10,1200,A,交通費\n",
            encoding="utf-8",
        )
        rows = read_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-10"

    def test_read_csv_empty_file_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="列名"):
            read_csv(str(csv_path))

    def test_read_csv_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_csv("missing.csv")

    def test_write_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "out.csv"
        write_csv(str(csv_path), [{"a": "1", "b": "2"}], ["a", "b"])
        content = csv_path.read_text(encoding="utf-8")
        assert "a,b" in content
        assert "1,2" in content
