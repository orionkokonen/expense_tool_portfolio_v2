# -*- coding: utf-8 -*-
"""
expense_tool.py
CLIエントリポイント（コマンドを受け取って処理を実行するだけ）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from excel_export import write_xlsx_report
from expense_core import (
    check_rows,
    make_summary,
    normalize_ok_rows,
    read_csv,
    write_csv,
)
from html_report import write_html_report
from rules import apply_rules, load_rules


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _stamp_name(base: str, ext: str, ts: str | None) -> str:
    """
    base="errors", ext="csv"
      ts があれば -> "errors_YYYYMMDD_HHMMSS.csv"
      ts がなければ -> "errors.csv"
    """
    if ts:
        return f"{base}_{ts}.{ext}"
    return f"{base}.{ext}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="expense_tool",
        description="経費CSVをチェックしてレポートを出すツール（ポートフォリオ）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("csv_path", help="入力CSVのパス（例: data/expenses.csv）")
    common.add_argument(
        "--rules", default="rules.json", help="ルールJSONのパス（既定: rules.json）"
    )
    common.add_argument("--out", default="out", help="出力フォルダ（既定: out）")
    common.add_argument(
        "--timestamp", action="store_true", help="出力ファイル名に日時を付ける（履歴用）"
    )
    common.add_argument("--top-n", type=int, default=10, help="merchant上位の件数（既定: 10）")

    sub.add_parser("check", parents=[common], help="チェック結果（errors/warnings）を出力")
    sub.add_parser("report", parents=[common], help="CSV/Excel/HTMLレポートを全部出力")

    return p


def datetime_now_stamp() -> str:
    # ファイル名に安全な形式にする
    import datetime as _dt

    now = _dt.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    rules_path = Path(args.rules)

    # 入力CSVごとに分ける（sample_bad / sample_good など）
    input_name = csv_path.stem

    # 出力の大元
    base_out = Path(args.out)

    # timestamp の有無で保存先を変える
    #   timestampあり: out/history/<input_name>/
    #   timestampなし: out/latest/<input_name>/  (上書き運用)
    bucket = "history" if args.timestamp else "latest"
    out_dir = base_out / bucket / input_name
    _ensure_dir(out_dir)

    # timestamp ありのときだけファイル名に付ける
    ts = datetime_now_stamp() if args.timestamp else None

    # 1) 取り込み
    rows = read_csv(str(csv_path))

    # 2) 構造チェック（必須列、日付形式、金額、重複など） -> errors
    ok_rows, errors = check_rows(rows)

    # 3) ルールチェック（カテゴリ許可、禁止ワード、日付範囲、上限など） -> warnings
    rules = load_rules(rules_path)
    ok_norm = normalize_ok_rows(ok_rows)

    # apply_rules は (clean_rows, warnings) を返す前提
    clean_rows, warnings = apply_rules(ok_norm, rules)

    # 4) 出力ファイル名（フォルダで分けるので prefix は不要）
    errors_csv = out_dir / _stamp_name("errors", "csv", ts)
    warnings_csv = out_dir / _stamp_name("warnings", "csv", ts)
    clean_csv = out_dir / _stamp_name("clean", "csv", ts)
    summary_csv = out_dir / _stamp_name("summary", "csv", ts)
    xlsx_path = out_dir / _stamp_name("report", "xlsx", ts)
    html_path = out_dir / _stamp_name("report", "html", ts)

    # 5) check は errors/warnings だけ
    if args.cmd == "check":
        write_csv(
            str(errors_csv), errors, ["row", "date", "amount", "merchant", "category", "reason"]
        )
        write_csv(
            str(warnings_csv),
            warnings,
            ["kind", "row", "date", "month", "category", "merchant", "amount", "message"],
        )

        print("チェック完了")
        print(f"  出力先: {out_dir}")
        print(f"  errors:   {errors_csv}（件数: {len(errors)}）")
        print(f"  warnings: {warnings_csv}（件数: {len(warnings)}）")

        # 終了コード：エラーがあれば 2、なければ 0
        return 2 if len(errors) > 0 else 0

    # 6) report は全部出す（集計は clean_rows を使う）
    summary = make_summary(clean_rows, top_n=args.top_n)

    write_csv(str(errors_csv), errors, ["row", "date", "amount", "merchant", "category", "reason"])
    write_csv(
        str(warnings_csv),
        warnings,
        ["kind", "row", "date", "month", "category", "merchant", "amount", "message"],
    )
    write_csv(str(clean_csv), clean_rows, ["row", "date", "amount", "merchant", "category"])
    write_csv(str(summary_csv), summary, ["type", "key", "value"])

    # Excel / HTML
    write_xlsx_report(
        path=xlsx_path,
        errors=errors,
        warnings=warnings,
        clean=clean_rows,
        summary=summary,
    )
    write_html_report(
        path=html_path,
        errors=errors,
        warnings=warnings,
        clean=clean_rows,
        summary=summary,
        title="Expense Tool Report",
    )

    print("レポート作成完了")
    print(f"  出力先: {out_dir}")
    print(f"  errors:   {errors_csv}（件数: {len(errors)}）")
    print(f"  warnings: {warnings_csv}（件数: {len(warnings)}）")
    print(f"  clean:    {clean_csv}（OK行: {len(clean_rows)}）")
    print(f"  summary:  {summary_csv}")
    print(f"  excel:    {xlsx_path}")
    print(f"  html:     {html_path}")
    print(
        f"  全体: {len(rows)} / OK: {len(ok_rows)} / エラー: {len(errors)} / 警告: {len(warnings)}"
    )

    return 2 if len(errors) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
