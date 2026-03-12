# -*- coding: utf-8 -*-
"""
expense_tool.py — CLI（コマンドライン）のエントリポイント
ターミナルからコマンドを受け取り、チェックやレポート生成を実行する。
GUI（app.py）と同じパイプラインを使っているが、引数の受け取り方が異なる。
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
    """フォルダがなければ作る（親フォルダも含めて自動作成）。"""
    path.mkdir(parents=True, exist_ok=True)


def _stamp_name(base: str, ext: str, ts: str | None) -> str:
    """出力ファイル名を組み立てる。

    ts（タイムスタンプ）があれば "errors_YYYYMMDD_HHMMSS.csv"、
    なければ "errors.csv" を返す。
    """
    if ts:
        return f"{base}_{ts}.{ext}"
    return f"{base}.{ext}"


def build_parser() -> argparse.ArgumentParser:
    """コマンドライン引数のパーサー（解析器）を組み立てて返す。

    サブコマンド:
      check  — 入力チェックのみ実行（errors / warnings を出力）
      report — チェック＋レポートを全部出力（CSV / Excel / HTML）
    """
    p = argparse.ArgumentParser(
        prog="expense_tool",
        description="経費CSVをチェックしてレポートを出すツール（ポートフォリオ）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # check / report の両方で使う引数を 1 か所にまとめ、説明のズレを防ぐ。
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
    """現在日時をファイル名に使える文字列（YYYYMMDD_HHMMSS）で返す。

    スラッシュやコロンはファイル名に使えないため、この形式に変換する。
    """
    import datetime as _dt

    now = _dt.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S")


def main(argv: list[str] | None = None) -> int:
    """CLI のメイン処理。引数を解析して check または report を実行する。

    戻り値:
      0 — エラーなし
      2 — 入力チェックエラーあり（CI などでエラー検知に使える）
    """
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # Path を使うと、パスの結合や存在確認を OS の違いを気にせず書ける。
    csv_path = Path(args.csv_path)
    rules_path = Path(args.rules)

    # 入力 CSV のファイル名（拡張子なし）を出力フォルダの一部に使う
    input_name = csv_path.stem

    base_out = Path(args.out)

    # --timestamp あり: 履歴として残す（out/history/<入力名>/）
    # --timestamp なし: 常に同じ場所に上書き（out/latest/<入力名>/）
    bucket = "history" if args.timestamp else "latest"
    out_dir = base_out / bucket / input_name
    _ensure_dir(out_dir)

    # --timestamp ありのときだけファイル名に日時を付ける
    ts = datetime_now_stamp() if args.timestamp else None

    # 1) CSV 読み込み
    rows = read_csv(str(csv_path))

    # 2) 基本入力チェック（必須列・日付・金額・重複） → errors / ok_rows
    ok_rows, errors = check_rows(rows)

    # 3) 社内ルールチェック（カテゴリ・禁止ワード・日付範囲・上限） → warnings
    rules = load_rules(rules_path)
    ok_norm = normalize_ok_rows(ok_rows)
    clean_rows, warnings = apply_rules(ok_norm, rules)

    # 4) 出力ファイルパスを組み立てる（フォルダで分けているので prefix は不要）
    errors_csv = out_dir / _stamp_name("errors", "csv", ts)
    warnings_csv = out_dir / _stamp_name("warnings", "csv", ts)
    clean_csv = out_dir / _stamp_name("clean", "csv", ts)
    summary_csv = out_dir / _stamp_name("summary", "csv", ts)
    xlsx_path = out_dir / _stamp_name("report", "xlsx", ts)
    html_path = out_dir / _stamp_name("report", "html", ts)

    # 5) check サブコマンド: errors / warnings だけ出力して終了
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

        # 終了コード: エラーがあれば 2（CI でエラー検知に使える）、なければ 0
        return 2 if len(errors) > 0 else 0

    # 6) report サブコマンド: 集計して全ファイルを出力する
    summary = make_summary(clean_rows, top_n=args.top_n)

    write_csv(str(errors_csv), errors, ["row", "date", "amount", "merchant", "category", "reason"])
    write_csv(
        str(warnings_csv),
        warnings,
        ["kind", "row", "date", "month", "category", "merchant", "amount", "message"],
    )
    write_csv(str(clean_csv), clean_rows, ["row", "date", "amount", "merchant", "category"])
    write_csv(str(summary_csv), summary, ["type", "key", "value"])

    # Excel / HTML レポートを生成する
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
