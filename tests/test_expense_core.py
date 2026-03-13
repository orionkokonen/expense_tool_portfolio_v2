# -*- coding: utf-8 -*-
"""
tests/test_expense_core.py — expense_core.py の拡充テスト

既存の test_core.py を補完し、エッジケース（境界値や想定外の入力）をカバーする。

テストの考え方:
  - 正常系: 期待どおりの入力で正しく動くか
  - 異常系: おかしな入力に対して安全にエラーを返すか
  - 境界値: 0 件・1 件・最小値・最大値など、境目の値で壊れないか

pytest の基本:
  - assert 文が True なら通過、False なら失敗
  - pytest.raises(SomeError) は「この中で SomeError が起きるはず」という宣言
  - tmp_path は pytest が自動で用意する一時フォルダ（テスト後に自動削除）
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
# parse_date のテスト
# テーマ: 日付文字列が YYYY-MM-DD 形式かどうかの判定
# ---------------------------------------------------------------------------

class TestParseDate:
    """日付パーサーのエッジケース。

    strptime は厳密にパースするので、カレンダー上あり得ない日付も弾ける。
    """

    def test_valid_date(self) -> None:
        assert parse_date("2026-01-10") is True

    def test_slash_format(self) -> None:
        """スラッシュ区切りは不正（ハイフン区切りのみ許可）。"""
        assert parse_date("2026/01/10") is False

    def test_empty_string(self) -> None:
        assert parse_date("") is False

    def test_month_13(self) -> None:
        """月が 13 → カレンダーに存在しないので不正。"""
        assert parse_date("2026-13-01") is False

    def test_day_32(self) -> None:
        """日が 32 → どの月にも存在しないので不正。"""
        assert parse_date("2026-01-32") is False

    def test_no_separator(self) -> None:
        """区切りなし "20260110" はフォーマット不一致で不正。"""
        assert parse_date("20260110") is False

    def test_leap_year_valid(self) -> None:
        """閏年（2024年）の 2/29 は有効。"""
        assert parse_date("2024-02-29") is True

    def test_non_leap_year_feb29(self) -> None:
        """非閏年（2026年）の 2/29 は存在しないので不正。"""
        assert parse_date("2026-02-29") is False


# ---------------------------------------------------------------------------
# parse_amount のテスト
# テーマ: 金額文字列が整数に変換できるかの判定
# ---------------------------------------------------------------------------

class TestParseAmount:
    """金額パーサーのエッジケース。

    int() で変換できるかどうかだけを見ている。
    小数・カンマ区切り・空白は int() が受け付けないため False になる。
    """

    def test_valid_positive(self) -> None:
        assert parse_amount("1200") is True

    def test_negative(self) -> None:
        """負の整数も int() で変換可能なので True。"""
        assert parse_amount("-500") is True

    def test_zero(self) -> None:
        assert parse_amount("0") is True

    def test_decimal(self) -> None:
        """小数は int() で変換できないので False。"""
        assert parse_amount("12.5") is False

    def test_alpha(self) -> None:
        assert parse_amount("abc") is False

    def test_empty(self) -> None:
        assert parse_amount("") is False

    def test_comma_separated(self) -> None:
        """"1,200" は人間には読めるが int() は受け付けない。"""
        assert parse_amount("1,200") is False

    def test_whitespace(self) -> None:
        """空白だけの文字列も数値ではない。"""
        assert parse_amount("  ") is False


# ---------------------------------------------------------------------------
# check_rows のテスト
# テーマ: 入力行を OK とエラーに振り分けるロジック
# ---------------------------------------------------------------------------

class TestCheckRows:
    """入力チェックの振り分けテスト。

    check_rows は (ok_rows, errors) のタプルを返す。
    """

    def test_valid_row(self) -> None:
        """正常な行は ok_rows に入り、errors は空。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, errors = check_rows(rows)
        assert len(ok) == 1
        assert len(errors) == 0

    def test_missing_column(self) -> None:
        """必須列（ここでは category）が欠けていたらエラーになるか。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A"}]
        ok, errors = check_rows(rows)
        assert len(ok) == 0
        assert len(errors) == 1
        assert "列がない" in errors[0]["reason"]

    def test_empty_date(self) -> None:
        """date が空欄ならエラーになるか。"""
        rows = [{"date": "", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, errors = check_rows(rows)
        assert len(errors) == 1
        assert "空欄" in errors[0]["reason"]

    def test_empty_merchant(self) -> None:
        """merchant が空欄でもエラーとして検出されるか。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1

    def test_invalid_date_format(self) -> None:
        """日付がスラッシュ区切りだとフォーマットエラーになるか。"""
        rows = [{"date": "2026/01/10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "日付の形式" in errors[0]["reason"]

    def test_invalid_amount(self) -> None:
        """金額が文字列 "abc" だとエラーになるか。"""
        rows = [{"date": "2026-01-10", "amount": "abc", "merchant": "A", "category": "交通費"}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        assert "金額が数字" in errors[0]["reason"]

    def test_duplicate_detection(self) -> None:
        """同じ date+amount+merchant の行が 2 つあると重複エラーになるか。"""
        row = {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}
        rows = [row, dict(row)]  # dict(row) でコピーを作り、同じ内容の別オブジェクトにする
        ok, errors = check_rows(rows)
        assert len(ok) == 1      # 最初の 1 行だけが OK
        assert len(errors) == 1  # 2 行目が重複エラー
        assert "重複" in errors[0]["reason"]

    def test_multiple_errors_in_one_row(self) -> None:
        """1 行に複数の問題がある場合、理由が " / " で連結されるか。"""
        rows = [{"date": "", "amount": "abc", "merchant": "", "category": ""}]
        _, errors = check_rows(rows)
        assert len(errors) == 1
        reasons = errors[0]["reason"]
        # 複数の理由が " / " で区切られていること
        assert " / " in reasons

    def test_row_number_starts_at_2(self) -> None:
        """行番号はヘッダ行を 1 と数えて、データ行は 2 から始まるか。"""
        rows = [{"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        ok, _ = check_rows(rows)
        assert ok[0]["row"] == "2"


# ---------------------------------------------------------------------------
# normalize_ok_rows のテスト
# テーマ: 文字列データを計算可能な型（int など）に変換するロジック
# ---------------------------------------------------------------------------

class TestNormalizeOkRows:
    """型変換のテスト。"""

    def test_amount_becomes_int(self) -> None:
        """amount が文字列 "1200" から整数 1200 に変換されるか。"""
        ok = [{"row": "2", "date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "交通費"}]
        norm = normalize_ok_rows(ok)
        assert norm[0]["amount"] == 1200
        assert isinstance(norm[0]["amount"], int)  # 型そのものも確認

    def test_strips_whitespace(self) -> None:
        """各フィールドの前後にある余計な空白が除去されるか。"""
        ok = [{"row": "2", "date": " 2026-01-10 ", "amount": " 1200 ", "merchant": " A ", "category": " 交通費 "}]
        norm = normalize_ok_rows(ok)
        assert norm[0]["date"] == "2026-01-10"
        assert norm[0]["merchant"] == "A"


# ---------------------------------------------------------------------------
# make_summary のテスト
# テーマ: クリーン行から複数軸の集計を正しく行うか
# ---------------------------------------------------------------------------

class TestMakeSummary:
    """集計ロジックのテスト。

    make_summary は {"type", "key", "value"} のフラットなリストを返す。
    type でフィルタして、各集計軸のデータを取り出して検証する。
    """

    def test_month_total(self) -> None:
        """月別合計が正しく集計されるか（1月: 1000+2000=3000）。"""
        rows = [
            {"row": "2", "date": "2026-01-10", "amount": 1000, "merchant": "A", "category": "交通費"},
            {"row": "3", "date": "2026-01-20", "amount": 2000, "merchant": "B", "category": "会議費"},
            {"row": "4", "date": "2026-02-05", "amount": 500, "merchant": "C", "category": "交通費"},
        ]
        summary = make_summary(rows, top_n=10)
        # ヘッダ行（key="month"）を除外してデータ行だけ取り出す
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
        """top_n=3 を指定すると、上位 3 店舗だけが出力されるか。"""
        rows = [
            {"row": str(i), "date": "2026-01-10", "amount": i * 100, "merchant": f"M{i}", "category": "交通費"}
            for i in range(1, 6)  # M1〜M5 の 5 店舗
        ]
        summary = make_summary(rows, top_n=3)
        # ヘッダ行（"top_3" で始まるキー）を除外
        merchant_items = [r for r in summary if r["type"] == "merchant_top" and not r["key"].startswith("top_")]
        assert len(merchant_items) == 3

    def test_stats(self) -> None:
        """基本統計値（count, min, max, average, median）が出力されるか。"""
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
        """0 件でもエラーにならず、count=0 が返るか（境界値テスト）。"""
        summary = make_summary([], top_n=10)
        stats = {r["key"]: r["value"] for r in summary if r["type"] == "stats"}
        assert stats["count"] == "0"
        # 0 件のときは平均・中央値を計算できないので、キー自体が存在しない
        assert "average" not in stats


# ---------------------------------------------------------------------------
# read_csv / write_csv のテスト
# テーマ: ファイル I/O（読み書き）のエラー処理
# ---------------------------------------------------------------------------

class TestCsvIO:
    """CSV 読み書きのテスト。"""

    def test_read_csv(self, tmp_path: Path) -> None:
        """正常な CSV ファイルを辞書のリストとして読めるか。"""
        p = tmp_path / "test.csv"
        p.write_text("date,amount,merchant,category\n2026-01-10,1200,A,交通費\n", encoding="utf-8")
        rows = read_csv(str(p))
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-10"

    def test_read_csv_empty_file(self, tmp_path: Path) -> None:
        """ヘッダすらない空ファイルで ValueError が出るか。

        pytest.raises は「この中で指定の例外が出るはず」を宣言するブロック。
        match="列名" で、エラーメッセージに「列名」が含まれることも確認。
        """
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="列名"):
            read_csv(str(p))

    def test_read_csv_file_not_found(self) -> None:
        """存在しないファイルを指定すると FileNotFoundError が出るか。"""
        with pytest.raises(FileNotFoundError):
            read_csv("nonexistent_file.csv")

    def test_write_csv(self, tmp_path: Path) -> None:
        """write_csv で書き出した内容が正しいか。"""
        p = tmp_path / "out.csv"
        rows = [{"a": "1", "b": "2"}]
        write_csv(str(p), rows, ["a", "b"])
        content = p.read_text(encoding="utf-8")
        assert "a,b" in content   # ヘッダ行
        assert "1,2" in content   # データ行
