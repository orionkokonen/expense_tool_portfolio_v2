# -*- coding: utf-8 -*-
"""Streamlit UI for the expense tool portfolio."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
import tempfile
from typing import Any

import streamlit as st

from expense_core import check_rows, make_summary, normalize_ok_rows, read_csv, write_csv
from excel_export import write_xlsx_report
from html_report import write_html_report
from rules import apply_rules, load_rules

LAST_RUN_KEY = "last_run"
SAMPLE_BAD_CSV_PATH = Path("data/sample_bad.csv")
SAMPLE_GOOD_CSV_PATH = Path("data/sample_good.csv")

st.set_page_config(page_title="Expense Tool Portfolio 2.0", layout="wide")


def _inject_styles() -> None:
    """Add a readability-first visual layer without changing app logic."""
    st.markdown(
        """
        <style>
          :root {
            --ink: #122338;
            --muted: #5c6b7c;
            --line: #d8ded8;
            --paper: #f7f3ea;
            --card: rgba(255, 255, 255, 0.84);
            --accent: #185c53;
            --accent-soft: #e2f0eb;
            --warm: #f3e4cf;
            --warn: #c06a1b;
            --danger: #a63d3d;
            --shadow: 0 18px 40px rgba(18, 35, 56, 0.08);
          }

          [data-testid="stAppViewContainer"] {
            background:
              radial-gradient(circle at top right, rgba(24, 92, 83, 0.12), transparent 24rem),
              radial-gradient(circle at left top, rgba(243, 228, 207, 0.9), transparent 22rem),
              linear-gradient(180deg, #fcfaf5 0%, var(--paper) 100%);
          }

          [data-testid="stHeader"] {
            background: rgba(252, 250, 245, 0.78);
          }

          div.block-container {
            max-width: 1240px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
          }

          .hero {
            background:
              linear-gradient(135deg, rgba(24, 92, 83, 0.12), rgba(243, 228, 207, 0.72)),
              rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(18, 35, 56, 0.08);
            border-radius: 26px;
            box-shadow: var(--shadow);
            padding: 30px 32px;
            margin-bottom: 1.2rem;
          }

          .eyebrow {
            color: var(--accent);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
          }

          .hero h1,
          .hero h2 {
            color: var(--ink);
            font-family: "Bahnschrift", "Aptos Display", "Yu Gothic UI Semibold", sans-serif;
            line-height: 1.05;
            margin: 0;
          }

          .hero h1 {
            font-size: clamp(2.1rem, 2rem + 1.8vw, 3.4rem);
          }

          .hero h2 {
            font-size: clamp(1.6rem, 1.4rem + 1.1vw, 2.4rem);
          }

          .hero p {
            color: var(--muted);
            font-family: "Aptos", "BIZ UDPGothic", "Yu Gothic UI", sans-serif;
            font-size: 1rem;
            line-height: 1.75;
            margin: 0.75rem 0 0;
            max-width: 54rem;
          }

          .hero-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
          }

          .hero-tag {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(18, 35, 56, 0.08);
            border-radius: 999px;
            color: var(--ink);
            font-size: 0.88rem;
            padding: 0.4rem 0.8rem;
          }

          .soft-card {
            background: var(--card);
            border: 1px solid rgba(18, 35, 56, 0.08);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 1.1rem 1.15rem;
            height: 100%;
          }

          .soft-card h3 {
            color: var(--ink);
            font-family: "Bahnschrift", "Aptos Display", "Yu Gothic UI Semibold", sans-serif;
            font-size: 1.02rem;
            margin: 0.2rem 0 0.55rem;
          }

          .soft-card p {
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.65;
            margin: 0;
          }

          .bullet-list {
            color: var(--muted);
            line-height: 1.7;
            margin: 0.25rem 0 0;
            padding-left: 1.1rem;
          }

          .bar-card {
            background: var(--card);
            border: 1px solid rgba(18, 35, 56, 0.08);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 1.1rem 1.15rem 1rem;
            margin-bottom: 1rem;
          }

          .bar-card h3 {
            color: var(--ink);
            font-family: "Bahnschrift", "Aptos Display", "Yu Gothic UI Semibold", sans-serif;
            font-size: 1.02rem;
            margin: 0 0 0.85rem;
          }

          .bar-row {
            margin-bottom: 0.9rem;
          }

          .bar-row:last-child {
            margin-bottom: 0;
          }

          .bar-meta {
            align-items: baseline;
            display: flex;
            gap: 0.75rem;
            justify-content: space-between;
            margin-bottom: 0.35rem;
          }

          .bar-label {
            color: var(--ink);
            font-size: 0.93rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .bar-value {
            color: var(--muted);
            flex-shrink: 0;
            font-size: 0.88rem;
          }

          .bar-track {
            background: rgba(18, 35, 56, 0.06);
            border-radius: 999px;
            height: 9px;
            overflow: hidden;
          }

          .bar-fill {
            background: linear-gradient(90deg, #1e6f64 0%, #3ca496 100%);
            border-radius: 999px;
            height: 100%;
          }

          .bar-fill.warn {
            background: linear-gradient(90deg, #b86a22 0%, #db9d62 100%);
          }

          .bar-fill.danger {
            background: linear-gradient(90deg, #9e4343 0%, #da7f7f 100%);
          }

          .empty-copy {
            color: var(--muted);
            line-height: 1.75;
            margin: 0.25rem 0 0;
          }

          .file-chip {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(18, 35, 56, 0.08);
            border-radius: 14px;
            color: var(--ink);
            font-family: "Consolas", "Courier New", monospace;
            font-size: 0.82rem;
            margin-bottom: 0.55rem;
            padding: 0.75rem 0.9rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded_file, dir_path: Path) -> Path:
    path = dir_path / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def _stamp_name(prefix: str, base: str, ext: str) -> str:
    return f"{prefix}_{base}.{ext}"


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: int | None, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value:,}{suffix}"


def _summary_pairs(summary: list[dict[str, str]], summary_type: str) -> list[tuple[str, int]]:
    pairs: list[tuple[str, int]] = []
    for row in summary:
        if row.get("type") != summary_type:
            continue
        amount = _to_int(row.get("value"))
        if amount is None:
            continue
        key = str(row.get("key") or "")
        if not key:
            continue
        pairs.append((key, amount))
    return pairs


def _summary_stats(summary: list[dict[str, str]]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for row in summary:
        if row.get("type") != "stats":
            continue
        amount = _to_int(row.get("value"))
        if amount is None:
            continue
        key = str(row.get("key") or "")
        if key:
            stats[key] = amount
    return stats


def _pairs_to_display_rows(
    pairs: list[tuple[str, int]],
    *,
    key_label: str,
    value_label: str,
    suffix: str = "円",
) -> list[dict[str, str]]:
    return [
        {key_label: key, value_label: _format_number(value, suffix)}
        for key, value in pairs
    ]


def _count_warning_kinds(warnings: list[dict[str, str]]) -> list[tuple[str, int]]:
    counts = Counter()
    for warning in warnings:
        kind = (warning.get("kind") or "").strip()
        if kind:
            counts[kind] += 1
    return counts.most_common()


def _count_error_reasons(errors: list[dict[str, str]]) -> list[tuple[str, int]]:
    counts = Counter()
    for error in errors:
        text = (error.get("reason") or "").strip()
        if not text:
            continue
        for reason in text.split(" / "):
            reason = reason.strip()
            if reason:
                counts[reason] += 1
    return counts.most_common()


def _render_html_card(title: str, body: str, eyebrow: str | None = None) -> None:
    eyebrow_html = f'<div class="eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    st.markdown(
        f"""
        <div class="soft-card">
          {eyebrow_html}
          <h3>{escape(title)}</h3>
          {body}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_bar_card(
    title: str,
    pairs: list[tuple[str, int]],
    *,
    suffix: str = "円",
    tone: str = "default",
    empty_message: str = "表示できるデータがありません。",
) -> None:
    if not pairs:
        st.markdown(
            f"""
            <div class="bar-card">
              <h3>{escape(title)}</h3>
              <p class="empty-copy">{escape(empty_message)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    max_value = max(value for _, value in pairs) or 1
    rows_html: list[str] = []
    for label, value in pairs:
        width = max(8, round((value / max_value) * 100))
        rows_html.append(
            f"""
            <div class="bar-row">
              <div class="bar-meta">
                <div class="bar-label">{escape(label)}</div>
                <div class="bar-value">{escape(_format_number(value, suffix))}</div>
              </div>
              <div class="bar-track">
                <div class="bar-fill {escape(tone)}" style="width: {width}%"></div>
              </div>
            </div>
            """
        )

    st.markdown(
        f"""
        <div class="bar-card">
          <h3>{escape(title)}</h3>
          {''.join(rows_html)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _run_pipeline(
    *,
    csv_path: Path,
    rules_path: Path,
    out_dir: Path,
    top_n: int,
    do_excel: bool,
    do_html: bool,
) -> dict[str, Any]:
    _ensure_dir(out_dir)
    prefix = csv_path.stem

    rows = read_csv(str(csv_path))
    ok_rows, errors = check_rows(rows)
    rules = load_rules(rules_path)
    ok_norm = normalize_ok_rows(ok_rows)
    clean_rows, warnings = apply_rules(ok_norm, rules)
    summary = make_summary(clean_rows, top_n=top_n)

    errors_csv = out_dir / _stamp_name(prefix, "errors", "csv")
    warnings_csv = out_dir / _stamp_name(prefix, "warnings", "csv")
    clean_csv = out_dir / _stamp_name(prefix, "clean", "csv")
    summary_csv = out_dir / _stamp_name(prefix, "summary", "csv")

    write_csv(str(errors_csv), errors, ["row", "date", "amount", "merchant", "category", "reason"])
    write_csv(
        str(warnings_csv),
        warnings,
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
            warnings=warnings,
            clean=clean_rows,
            summary=summary,
        )
        output_paths["report_xlsx"] = xlsx_path

    if do_html:
        write_html_report(
            path=html_path,
            errors=errors,
            warnings=warnings,
            clean=clean_rows,
            summary=summary,
            title="Expense Tool Report",
        )
        output_paths["report_html"] = html_path

    return {
        "source_name": csv_path.name,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "clean_rows": clean_rows,
        "input_count": len(rows),
        "valid_count": len(ok_rows),
        "clean_count": len(clean_rows),
        "top_n": top_n,
        "output_paths": {key: str(value) for key, value in output_paths.items()},
        "enabled_outputs": {"excel": do_excel, "html": do_html},
    }


def _render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Portfolio 2.0</div>
          <h1>Expense Tool</h1>
          <p>
            CSV チェックとレポート生成を、読む順番が自然なダッシュボードに再構成しました。
            入力、判定、要点、詳細、ダウンロードを一画面で追える構成です。
          </p>
          <div class="hero-tags">
            <div class="hero-tag">Validation First</div>
            <div class="hero-tag">Readable Workflow</div>
            <div class="hero-tag">CSV / Excel / HTML</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state() -> None:
    st.caption("左サイドバーで CSV を選ぶか、サンプルを実行してください。")

    step1, step2, step3 = st.columns(3)
    with step1:
        _render_html_card(
            "1. CSV を選ぶ",
            """
            <p>
              `date / amount / merchant / category` の4列を持つ CSV をアップロードします。
              UTF-8 を前提にしています。
            </p>
            """,
            eyebrow="Input",
        )
    with step2:
        _render_html_card(
            "2. 結果を読む",
            """
            <p>
              エラーと警告を分けて表示し、先に直すべき箇所を上段で要約します。
              明細はタブで必要なときだけ確認できます。
            </p>
            """,
            eyebrow="Review",
        )
    with step3:
        _render_html_card(
            "3. 成果物を出す",
            """
            <p>
              clean / summary の CSV に加えて、Excel と HTML のレポートを同じ画面から取得できます。
            </p>
            """,
            eyebrow="Export",
        )

    st.markdown("")

    col_left, col_right = st.columns([1.1, 0.9])
    with col_left:
        _render_html_card(
            "この 2.0 で変えたこと",
            """
            <ul class="bullet-list">
              <li>情報を「操作」ではなく「判断」の順に並べ替え</li>
              <li>要点をメトリクスと短い文章で先に提示</li>
              <li>詳細表はタブ分割して視線のノイズを削減</li>
            </ul>
            """,
            eyebrow="What Changed",
        )
    with col_right:
        st.code(
            "date,amount,merchant,category\n"
            "2026-01-10,1200,Cafe,food\n"
            "2026-01-11,3500,Hotel,travel",
            language="csv",
        )


def _build_insights(
    *,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    category_pairs: list[tuple[str, int]],
    merchant_pairs: list[tuple[str, int]],
) -> list[str]:
    lines: list[str] = []

    if errors:
        lines.append(f"エラーが {len(errors)} 件あるため、元 CSV の修正が先です。")
    elif warnings:
        lines.append(f"形式チェックは通過していますが、ルール警告が {len(warnings)} 件あります。")
    else:
        lines.append("エラーも警告もなく、そのままレポートを共有できる状態です。")

    if category_pairs:
        category, amount = max(category_pairs, key=lambda item: item[1])
        lines.append(f"支出最大カテゴリは {category} で、合計 {_format_number(amount, '円')} です。")

    if merchant_pairs:
        merchant, amount = merchant_pairs[0]
        lines.append(f"支出先トップは {merchant} で、合計 {_format_number(amount, '円')} です。")

    return lines


def _render_run_header(last_run: dict[str, Any]) -> None:
    errors = last_run["errors"]
    warnings = last_run["warnings"]

    if errors:
        eyebrow = "Needs Fix"
        headline = "先に CSV を修正する段階です"
        copy = "形式エラーが残っているため、集計値よりも入力ミスの解消を優先してください。"
    elif warnings:
        eyebrow = "Review Recommended"
        headline = "集計は可能ですが、ルール面の確認が必要です"
        copy = "未知カテゴリや上限超過など、判断が必要な警告を含んでいます。"
    else:
        eyebrow = "Ready"
        headline = "クリーンに通過しました"
        copy = "検証とルール適用の両方を通過しており、成果物の配布に進めます。"

    source_name = escape(last_run["source_name"])
    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">{eyebrow}</div>
          <h2>{headline}</h2>
          <p>{copy}<br />Source: <strong>{source_name}</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source_path = last_run.get("source_path")
    if source_path:
        st.caption(f"Source path: {source_path}")


def _render_overview(last_run: dict[str, Any]) -> None:
    errors = last_run["errors"]
    warnings = last_run["warnings"]
    summary = last_run["summary"]

    month_pairs = _summary_pairs(summary, "month_total")
    category_pairs = _summary_pairs(summary, "category_total")
    merchant_pairs = _summary_pairs(summary, "merchant_top")
    weekday_pairs = _summary_pairs(summary, "weekday_total")
    stats = _summary_stats(summary)

    total_spend = sum(value for _, value in month_pairs)
    avg_spend = stats.get("average")
    max_spend = stats.get("max")
    count = stats.get("count", last_run["clean_count"])
    pass_rate = 0.0
    if last_run["input_count"]:
        pass_rate = last_run["clean_count"] / last_run["input_count"]

    metric_cols = st.columns(5)
    metric_cols[0].metric("Input rows", _format_number(last_run["input_count"]))
    metric_cols[1].metric("Clean rows", _format_number(last_run["clean_count"]))
    metric_cols[2].metric("Errors", _format_number(len(errors)))
    metric_cols[3].metric("Warnings", _format_number(len(warnings)))
    metric_cols[4].metric("Pass rate", f"{pass_rate:.0%}")

    left, right = st.columns([1.1, 0.9])
    with left:
        bullets = "".join(
            f"<li>{escape(line)}</li>"
            for line in _build_insights(
                errors=errors,
                warnings=warnings,
                category_pairs=category_pairs,
                merchant_pairs=merchant_pairs,
            )
        )
        _render_html_card(
            "判定メモ",
            f'<ul class="bullet-list">{bullets}</ul>',
            eyebrow="Read This First",
        )
    with right:
        snapshot_cols = st.columns(2)
        snapshot_cols[0].metric("Total spend", _format_number(total_spend, "円"))
        snapshot_cols[1].metric("Average", _format_number(avg_spend, "円"))
        snapshot_cols[0].metric("Max spend", _format_number(max_spend, "円"))
        snapshot_cols[1].metric("Count", _format_number(count))

    top_left, top_right = st.columns(2)
    with top_left:
        _render_bar_card("月別支出", month_pairs, empty_message="月別集計がありません。")
        _render_bar_card("カテゴリ別支出", category_pairs, empty_message="カテゴリ集計がありません。")
    with top_right:
        _render_bar_card(
            f"支出先 Top {last_run['top_n']}",
            merchant_pairs,
            empty_message="支出先ランキングを作れませんでした。",
        )
        _render_bar_card("曜日別支出", weekday_pairs, empty_message="曜日別集計がありません。")


def _render_validation(last_run: dict[str, Any]) -> None:
    errors = last_run["errors"]
    warnings = last_run["warnings"]
    clean_rows = last_run["clean_rows"]

    insight_left, insight_right = st.columns(2)
    with insight_left:
        _render_bar_card(
            "エラー理由の内訳",
            _count_error_reasons(errors),
            suffix="件",
            tone="danger",
            empty_message="エラーはありません。",
        )
    with insight_right:
        _render_bar_card(
            "警告種別の内訳",
            _count_warning_kinds(warnings),
            suffix="件",
            tone="warn",
            empty_message="警告はありません。",
        )

    tab_errors, tab_warnings, tab_clean = st.tabs(["Errors", "Warnings", "Clean Preview"])

    with tab_errors:
        if errors:
            st.dataframe(errors, use_container_width=True, hide_index=True)
        else:
            st.success("エラーはありません。")

    with tab_warnings:
        if warnings:
            st.dataframe(warnings, use_container_width=True, hide_index=True)
        else:
            st.success("警告はありません。")

    with tab_clean:
        preview_rows = [
            {
                "date": row.get("date", ""),
                "amount": row.get("amount", ""),
                "merchant": row.get("merchant", ""),
                "category": row.get("category", ""),
            }
            for row in clean_rows[:100]
        ]
        st.caption("プレビューは先頭 100 行まで表示しています。")
        if preview_rows:
            st.dataframe(preview_rows, use_container_width=True, hide_index=True)
        else:
            st.info("クリーン行がありません。")


def _render_summary(last_run: dict[str, Any]) -> None:
    summary = last_run["summary"]

    month_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "month_total"),
        key_label="month",
        value_label="amount",
    )
    category_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "category_total"),
        key_label="category",
        value_label="amount",
    )
    merchant_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "merchant_top"),
        key_label="merchant",
        value_label="amount",
    )
    weekday_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "weekday_total"),
        key_label="weekday",
        value_label="amount",
    )
    stats = _summary_stats(summary)
    stats_rows = [
        {"metric": key, "value": _format_number(value, "円" if key != "count" else "")}
        for key, value in stats.items()
    ]

    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("Month / Category")
        st.dataframe(month_rows, use_container_width=True, hide_index=True)
        st.dataframe(category_rows, use_container_width=True, hide_index=True)
    with top_right:
        st.subheader("Merchant / Weekday")
        st.dataframe(merchant_rows, use_container_width=True, hide_index=True)
        st.dataframe(weekday_rows, use_container_width=True, hide_index=True)

    st.subheader("Stats")
    st.dataframe(stats_rows, use_container_width=True, hide_index=True)


def _render_downloads(last_run: dict[str, Any]) -> None:
    output_paths = {key: Path(value) for key, value in last_run["output_paths"].items()}

    file_col, button_col = st.columns([0.9, 1.1])
    with file_col:
        st.subheader("Generated files")
        for path in output_paths.values():
            st.markdown(
                f'<div class="file-chip">{escape(str(path))}</div>',
                unsafe_allow_html=True,
            )

    with button_col:
        st.subheader("Download outputs")
        source_bytes = last_run.get("source_bytes")
        if isinstance(source_bytes, bytes):
            st.download_button(
                label="Source CSV",
                data=source_bytes,
                file_name=last_run["source_name"],
                mime="text/csv",
                use_container_width=True,
                key="download_source_csv",
            )

        download_specs = [
            ("errors_csv", "errors.csv", "text/csv"),
            ("warnings_csv", "warnings.csv", "text/csv"),
            ("clean_csv", "clean.csv", "text/csv"),
            ("summary_csv", "summary.csv", "text/csv"),
            (
                "report_xlsx",
                "report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("report_html", "report.html", "text/html"),
        ]

        for key, label, mime in download_specs:
            path = output_paths.get(key)
            if path is None:
                continue
            payload = _read_bytes(path)
            if payload is None:
                st.warning(f"Could not read output file: {path}")
                continue
            st.download_button(
                label=f"Download {label}",
                data=payload,
                file_name=path.name,
                mime=mime,
                use_container_width=True,
                key=f"download_{key}",
            )


def main() -> None:
    _inject_styles()
    _render_hero()

    with st.sidebar:
        st.header("Run control")
        uploaded_csv = st.file_uploader("CSV ファイル", type=["csv"])
        st.caption("必須列: date / amount / merchant / category")

        with st.expander("Report options", expanded=True):
            top_n = st.number_input("Top merchants", min_value=1, max_value=50, value=10, step=1)
            do_excel = st.checkbox("Generate Excel (.xlsx)", value=True)
            do_html = st.checkbox("Generate HTML report", value=True)

        with st.expander("Paths", expanded=False):
            rules_path_str = st.text_input("rules.json path", value="rules.json")
            out_dir_str = st.text_input("Output directory", value="out/gui")

        st.divider()
        st.caption("Quick samples")
        run_upload_btn = st.button("Run uploaded CSV", type="primary", use_container_width=True)
        sample_bad_col, sample_good_col = st.columns(2)
        with sample_bad_col:
            run_sample_bad_btn = st.button("sample_bad", use_container_width=True)
        with sample_good_col:
            run_sample_good_btn = st.button("sample_good", use_container_width=True)

    run_error: str | None = None

    if run_upload_btn or run_sample_bad_btn or run_sample_good_btn:
        rules_path = Path(rules_path_str)
        out_dir = Path(out_dir_str)
        result: dict[str, Any] | None = None

        if not rules_path.exists():
            run_error = f"rules.json not found: {rules_path}"
        else:
            try:
                if run_upload_btn:
                    if uploaded_csv is None:
                        run_error = "Please upload a CSV file before running."
                    else:
                        with tempfile.TemporaryDirectory() as tmp:
                            csv_path = _save_upload(uploaded_csv, Path(tmp))
                            result = _run_pipeline(
                                csv_path=csv_path,
                                rules_path=rules_path,
                                out_dir=out_dir,
                                top_n=int(top_n),
                                do_excel=do_excel,
                                do_html=do_html,
                            )
                            if result is not None:
                                result["source_bytes"] = uploaded_csv.getvalue()
                else:
                    sample_csv_path = (
                        SAMPLE_BAD_CSV_PATH if run_sample_bad_btn else SAMPLE_GOOD_CSV_PATH
                    )
                    if not sample_csv_path.exists():
                        run_error = f"Sample CSV not found: {sample_csv_path}"
                    else:
                        result = _run_pipeline(
                            csv_path=sample_csv_path,
                            rules_path=rules_path,
                            out_dir=out_dir,
                            top_n=int(top_n),
                            do_excel=do_excel,
                            do_html=do_html,
                        )
                        if result is not None:
                            result["source_path"] = str(sample_csv_path.resolve())
                            result["source_bytes"] = _read_bytes(sample_csv_path)
            except Exception as exc:  # pragma: no cover - UI surface
                run_error = f"Run failed: {exc}"

        if result is not None:
            st.session_state[LAST_RUN_KEY] = result

    if run_error:
        st.error(run_error)

    last_run = st.session_state.get(LAST_RUN_KEY)
    if last_run is None:
        _render_empty_state()
        return

    _render_run_header(last_run)

    tab_overview, tab_validation, tab_summary, tab_downloads = st.tabs(
        ["Overview", "Validation", "Summary", "Downloads"]
    )
    with tab_overview:
        _render_overview(last_run)
    with tab_validation:
        _render_validation(last_run)
    with tab_summary:
        _render_summary(last_run)
    with tab_downloads:
        _render_downloads(last_run)


main()
