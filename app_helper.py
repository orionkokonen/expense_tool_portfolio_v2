# -*- coding: utf-8 -*-
"""
app_helper.py — app.py（Streamlit GUI）の非 UI 処理をまとめた補助モジュール。

切り出し対象:
  - パイプライン実行 (run_pipeline)
  - 出力パス生成 (make_output_paths)
  - run result 生成（run_pipeline の戻り値構築）
  - パス安全化 (safe_resolve)
  - ダウンロード用ファイル読込ヘルパー (read_file_bytes)
  - run_id 生成 (generate_run_id)
  - セッション結果型 (RunResult)

app.py には Streamlit のレイアウト、表示用ヘルパー、イベント配線だけを残す。

読み方のおすすめ:
  - まず `run_pipeline()` で GUI 実行の全体像を見る
  - 次に `safe_resolve()` と `read_file_bytes()` で安全面の補助を追う
  - 最後に `RunResult` を見ると、画面側へ何を渡しているか分かる
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import TypedDict

from excel_export import write_xlsx_report
from expense_core import (
    IssueRow,
    SummaryRow,
    WarningRow,
    check_rows,
    make_summary,
    normalize_ok_rows,
    read_csv,
    write_csv,
)
from html_report import write_html_report
from rules import apply_rules, find_duplicate_candidates, load_rules

# --- 型定義 ---

class RunResult(TypedDict):
    """パイプライン実行結果。session_state に保持する最小限の情報。

    TypedDict を使うと、「どのキーがある前提か」が辞書でも読み取りやすくなる。
    UI 側はこの形だけを信じて描画すればよいので、責務の境界がはっきりする。
    """
    source_name: str
    source_path: str
    run_id: str
    input_count: int
    valid_count: int
    clean_count: int
    top_n: int
    errors: list[IssueRow]
    warnings: list[WarningRow]
    summary: list[SummaryRow]
    clean_preview: list[dict[str, str | int]]
    output_paths: dict[str, str]
    enabled_outputs: dict[str, bool]


# --- run_id 生成 ---

def generate_run_id() -> str:
    """実行ごとに一意な ID を生成する。

    UUID4 の先頭 8 文字を使う。ファイルシステムに安全で、衝突リスクも十分に低い。
    """
    return uuid.uuid4().hex[:8]


# --- パス安全化 ---

def safe_resolve(raw: str, project_root: Path) -> Path | None:
    """ユーザー入力のパスを安全な絶対パスに変換する。

    仕組み:
      1. Path.cwd() / raw → 相対パスを現在ディレクトリ基準で結合
      2. .resolve()       → ".." などを展開し、最終的な絶対パスにする
      3. is_relative_to() → プロジェクト外を指していたら None で拒否

    文字列前方一致ではなく Path.is_relative_to() 相当のパス比較を使うことで、
    "project2" のような近い別パスを誤って許可するリスクを防ぐ。
    None を返したらパス不正、呼び出し側でエラーメッセージを表示する。
    """
    try:
        resolved = (Path.cwd() / raw).resolve()
    except (OSError, ValueError):
        return None
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    return resolved


# --- ダウンロード用ファイル読込ヘルパー ---

def read_file_bytes(path: Path) -> bytes | None:
    """ダウンロード用にファイルを bytes で読む。

    読めない場合は None を返し、画面側で警告表示に回してアプリ全体は止めない。
    """
    try:
        return path.read_bytes()
    except OSError:
        return None


# --- 出力パス生成 ---

def make_output_dir(base_dir: Path, run_id: str) -> Path:
    """run_id 付きのサブディレクトリを作成して返す。"""
    out_dir = base_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _stamp_name(prefix: str, base: str, ext: str) -> str:
    """出力ファイル名を共通ルールで組み立てる。"""
    return f"{prefix}_{base}.{ext}"


# --- パイプライン実行 ---

def run_pipeline(
    *,
    csv_path: Path,
    rules_path: Path,
    out_dir: Path,
    top_n: int,
    do_excel: bool,
    do_html: bool,
    run_id: str,
) -> RunResult:
    """GUI から使う共通実行パイプライン。

    CLI と同じ順序で処理し、画面表示とダウンロードに必要な最小限の情報を返す。
    full clean_rows や source_bytes は保持せず、メモリ使用量を抑える。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = csv_path.stem

    # まず「入力として読めるか」を確認し、その後で社内ルールと集計へ進む。
    rows = read_csv(str(csv_path))
    ok_rows, errors = check_rows(rows)
    rules = load_rules(rules_path)
    ok_norm = normalize_ok_rows(ok_rows)

    # 重複候補を warning として検出（clean_rows からは除外しない）
    dup_warnings = find_duplicate_candidates(ok_norm)

    clean_rows, rule_warnings = apply_rules(ok_norm, rules)
    all_warnings = dup_warnings + rule_warnings

    summary = make_summary(clean_rows, top_n=top_n)

    # 画面からも外部ファイルからも追いやすいよう、成果物の名前を統一する。
    errors_csv = out_dir / _stamp_name(prefix, "errors", "csv")
    warnings_csv = out_dir / _stamp_name(prefix, "warnings", "csv")
    clean_csv = out_dir / _stamp_name(prefix, "clean", "csv")
    summary_csv = out_dir / _stamp_name(prefix, "summary", "csv")

    write_csv(str(errors_csv), errors, ["row", "date", "amount", "merchant", "category", "reason"])
    write_csv(
        str(warnings_csv),
        all_warnings,
        ["kind", "row", "date", "month", "category", "merchant", "amount", "message"],
    )
    write_csv(str(clean_csv), clean_rows, ["date", "amount", "merchant", "category"])
    write_csv(str(summary_csv), summary, ["type", "key", "value"])

    output_paths: dict[str, Path] = {
        "errors_csv": errors_csv,
        "warnings_csv": warnings_csv,
        "clean_csv": clean_csv,
        "summary_csv": summary_csv,
    }

    xlsx_path = out_dir / _stamp_name(prefix, "report", "xlsx")
    html_path = out_dir / _stamp_name(prefix, "report", "html")

    if do_excel:
        write_xlsx_report(
            path=xlsx_path,
            errors=errors,
            warnings=all_warnings,
            clean=clean_rows,
            summary=summary,
        )
        output_paths["report_xlsx"] = xlsx_path

    if do_html:
        write_html_report(
            path=html_path,
            errors=errors,
            warnings=all_warnings,
            clean=clean_rows,
            summary=summary,
            title="支出レポート",
        )
        output_paths["report_html"] = html_path

    # clean_rows のプレビュー（先頭100行、表示用の列のみ）
    clean_preview: list[dict[str, str | int]] = [
        {
            "date": row.get("date", ""),
            "amount": row.get("amount", ""),
            "merchant": row.get("merchant", ""),
            "category": row.get("category", ""),
        }
        for row in clean_rows[:100]
    ]

    # session_state へ入れる値は「再表示に必要なものだけ」に絞る。
    # 元CSVの bytes や full clean_rows を持ち続けないことで、実行後のメモリを抑える。
    return {
        "source_name": csv_path.name,
        "source_path": str(csv_path),
        "run_id": run_id,
        "errors": errors,
        "warnings": all_warnings,
        "summary": summary,
        "clean_preview": clean_preview,
        "input_count": len(rows),
        "valid_count": len(ok_rows),
        "clean_count": len(clean_rows),
        "top_n": top_n,
        "output_paths": {key: str(value) for key, value in output_paths.items()},
        "enabled_outputs": {"excel": do_excel, "html": do_html},
    }


def save_source_csv(uploaded_bytes: bytes, filename: str, out_dir: Path) -> Path:
    """アップロードされた CSV を run_id ディレクトリに保存する。

    ダウンロード時はこの保存ファイルを読む方式にする（session_state に bytes を持たない）。
    こうしておくと、画面メモリとダウンロード元ファイルの責務を分けやすい。
    """
    dest = out_dir / filename
    dest.write_bytes(uploaded_bytes)
    return dest


def copy_source_csv(source_path: Path, out_dir: Path) -> Path:
    """サンプル CSV を run_id ディレクトリにコピーする。

    サンプル実行でもアップロード実行と同じ保存ルールにそろえることで、
    ダウンロード処理を 1 本化しやすくしている。
    """
    dest = out_dir / source_path.name
    shutil.copy2(source_path, dest)
    return dest
