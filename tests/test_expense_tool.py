# -*- coding: utf-8 -*-
"""
tests/test_expense_tool.py — expense_tool.py (CLI) の単体テスト
サブコマンド check / report の実行と出力ファイル生成を検証する。
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from expense_tool import build_parser, datetime_now_stamp, main


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """テスト用の CSV を書き出す。"""
    fieldnames = ["date", "amount", "merchant", "category"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _good_rows() -> list[dict[str, str]]:
    return [
        {"date": "2026-01-10", "amount": "1200", "merchant": "カフェA", "category": "会議費"},
        {"date": "2026-01-15", "amount": "3500", "merchant": "ホテルB", "category": "旅費"},
    ]


def _bad_rows() -> list[dict[str, str]]:
    return [
        {"date": "2026/01/10", "amount": "abc", "merchant": "", "category": ""},
    ]


# ---------------------------------------------------------------------------
# build_parser のテスト
# ---------------------------------------------------------------------------

class TestBuildParser:
    """CLI パーサーのテスト。"""

    def test_check_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check", "data/test.csv"])
        assert args.cmd == "check"
        assert args.csv_path == "data/test.csv"

    def test_report_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["report", "data/test.csv", "--top-n", "5"])
        assert args.cmd == "report"
        assert args.top_n == 5

    def test_default_values(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check", "test.csv"])
        assert args.rules == "rules.json"
        assert args.out == "out"
        assert args.top_n == 10
        assert args.timestamp is False


# ---------------------------------------------------------------------------
# datetime_now_stamp のテスト
# ---------------------------------------------------------------------------

def test_datetime_now_stamp() -> None:
    """タイムスタンプ文字列が期待される形式か。"""
    stamp = datetime_now_stamp()
    # YYYYMMDD_HHMMSS → 15 文字
    assert len(stamp) == 15
    assert stamp[8] == "_"


# ---------------------------------------------------------------------------
# main() のテスト: check サブコマンド
# ---------------------------------------------------------------------------

class TestMainCheck:
    """check サブコマンドの結合テスト。"""

    def test_check_good_csv(self, tmp_path: Path) -> None:
        """正常 CSV → 終了コード 0。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["check", str(csv_path), "--out", str(out_dir)])
        assert code == 0
        # errors.csv と warnings.csv が生成されている
        latest = out_dir / "latest" / "good"
        assert (latest / "errors.csv").exists()
        assert (latest / "warnings.csv").exists()

    def test_check_bad_csv(self, tmp_path: Path) -> None:
        """エラー行ありの CSV → 終了コード 2。"""
        csv_path = tmp_path / "bad.csv"
        _write_csv(csv_path, _bad_rows())
        out_dir = tmp_path / "out"
        code = main(["check", str(csv_path), "--out", str(out_dir)])
        assert code == 2


# ---------------------------------------------------------------------------
# main() のテスト: report サブコマンド
# ---------------------------------------------------------------------------

class TestMainReport:
    """report サブコマンドの結合テスト。"""

    def test_report_good_csv(self, tmp_path: Path) -> None:
        """正常 CSV で全レポートが生成されるか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["report", str(csv_path), "--out", str(out_dir)])
        assert code == 0
        latest = out_dir / "latest" / "good"
        assert (latest / "errors.csv").exists()
        assert (latest / "warnings.csv").exists()
        assert (latest / "clean.csv").exists()
        assert (latest / "summary.csv").exists()
        assert (latest / "report.xlsx").exists()
        assert (latest / "report.html").exists()

    def test_report_with_timestamp(self, tmp_path: Path) -> None:
        """--timestamp つきで history フォルダに出力されるか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["report", str(csv_path), "--out", str(out_dir), "--timestamp"])
        assert code == 0
        history = out_dir / "history" / "good"
        assert history.exists()
        # タイムスタンプ付きファイルが生成されている
        files = list(history.iterdir())
        assert len(files) > 0
