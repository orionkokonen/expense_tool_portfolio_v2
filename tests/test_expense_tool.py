# -*- coding: utf-8 -*-
"""
tests/test_expense_tool.py — expense_tool.py (CLI) の単体テスト

検証のポイント:
  - CLI パーサーがサブコマンドや引数を正しく受け取るか
  - main() 関数が CSV を処理して期待する出力ファイルを生成するか
  - 終了コード（0=正常, 2=エラーあり）が正しいか

テスト設計の考え方:
  CLI テストでは「画面に表示される文字列」ではなく
  「終了コード」と「生成されたファイル」で正否を判定する。
  こうすると表示文言を変えてもテストが壊れにくい。
"""

from __future__ import annotations

import csv
from pathlib import Path

from expense_tool import build_parser, datetime_now_stamp, main


# ---------------------------------------------------------------------------
# ヘルパー — テスト用 CSV を作る関数
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """テスト用の CSV を書き出す。

    テストごとに異なる内容の CSV が必要なので、
    ヘルパー関数にして使い回す。
    こうしておくと、テスト本文は「何を確かめたいか」に集中しやすい。
    """
    fieldnames = ["date", "amount", "merchant", "category"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _good_rows() -> list[dict[str, str]]:
    """エラーなしの正常データ。"""
    return [
        {"date": "2026-01-10", "amount": "1200", "merchant": "カフェA", "category": "会議費"},
        {"date": "2026-01-15", "amount": "3500", "merchant": "ホテルB", "category": "旅費"},
    ]


def _bad_rows() -> list[dict[str, str]]:
    """日付形式違い + 金額が文字列 → エラーになるデータ。"""
    return [
        {"date": "2026/01/10", "amount": "abc", "merchant": "", "category": ""},
    ]


# ---------------------------------------------------------------------------
# build_parser のテスト
# テーマ: argparse（コマンドライン引数の解析器）が正しく設定されているか
# ---------------------------------------------------------------------------

class TestBuildParser:
    """CLI パーサーのテスト。

    parse_args にリストを渡すと、コマンドラインから打ったのと同じ動きをする。
    """

    def test_check_command(self) -> None:
        """'check data/test.csv' → cmd="check", csv_path="data/test.csv" になるか。"""
        parser = build_parser()
        args = parser.parse_args(["check", "data/test.csv"])
        assert args.cmd == "check"
        assert args.csv_path == "data/test.csv"

    def test_report_command(self) -> None:
        """'report ... --top-n 5' → top_n=5 が渡るか。"""
        parser = build_parser()
        args = parser.parse_args(["report", "data/test.csv", "--top-n", "5"])
        assert args.cmd == "report"
        assert args.top_n == 5

    def test_default_values(self) -> None:
        """引数を省略したときのデフォルト値が正しいか。"""
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
    """タイムスタンプ文字列が "YYYYMMDD_HHMMSS"（15文字）の形式か。"""
    stamp = datetime_now_stamp()
    assert len(stamp) == 15
    assert stamp[8] == "_"  # 9文字目がアンダースコア


# ---------------------------------------------------------------------------
# main() のテスト: check サブコマンド
# テーマ: CSV の入力チェックだけを行い、集計やレポートは作らないモード
# ---------------------------------------------------------------------------

class TestMainCheck:
    """check サブコマンドの結合テスト。

    結合テスト = 複数の関数（read_csv → check_rows → write_csv）を
    つなげて動かし、全体として正しく動くかを確認するテスト。
    """

    def test_check_good_csv(self, tmp_path: Path) -> None:
        """正常 CSV → 終了コード 0（エラーなし）。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["check", str(csv_path), "--out", str(out_dir)])
        assert code == 0
        # check モードは集計までは行わないが、
        # 入力チェック結果の 2 ファイルは必ず作られる。
        latest = out_dir / "latest" / "good"
        assert (latest / "errors.csv").exists()
        assert (latest / "warnings.csv").exists()

    def test_check_bad_csv(self, tmp_path: Path) -> None:
        """エラー行ありの CSV → 終了コード 2（要修正）。"""
        csv_path = tmp_path / "bad.csv"
        _write_csv(csv_path, _bad_rows())
        out_dir = tmp_path / "out"
        code = main(["check", str(csv_path), "--out", str(out_dir)])
        assert code == 2


# ---------------------------------------------------------------------------
# main() のテスト: report サブコマンド
# テーマ: チェック + 集計 + レポート生成をすべて行うモード
# ---------------------------------------------------------------------------

class TestMainReport:
    """report サブコマンドの結合テスト。"""

    def test_report_good_csv(self, tmp_path: Path) -> None:
        """正常 CSV で全レポートファイルが生成されるか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["report", str(csv_path), "--out", str(out_dir)])
        assert code == 0
        latest = out_dir / "latest" / "good"
        # report モードは check の結果に加えて、
        # 集計用 CSV と見やすいレポート形式も作る。
        assert (latest / "errors.csv").exists()
        assert (latest / "warnings.csv").exists()
        assert (latest / "clean.csv").exists()
        assert (latest / "summary.csv").exists()
        assert (latest / "report.xlsx").exists()
        assert (latest / "report.html").exists()

    def test_report_with_timestamp(self, tmp_path: Path) -> None:
        """--timestamp オプションで history フォルダにも出力されるか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        out_dir = tmp_path / "out"
        code = main(["report", str(csv_path), "--out", str(out_dir), "--timestamp"])
        assert code == 0
        history = out_dir / "history" / "good"
        assert history.exists()
        # ここではファイル名の完全一致までは見ず、
        # 「履歴保存用の出力が何かしら作られたか」を確認する。
        files = list(history.iterdir())
        assert len(files) > 0
