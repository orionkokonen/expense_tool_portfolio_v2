# -*- coding: utf-8 -*-
"""Expense Tool の Streamlit 画面。

CLI と同じ処理パイプラインをボタン操作でたどれるようにし、
入力 -> 判定 -> 集計 -> ダウンロードを一画面で追えるようにしている。
非 UI の処理は app_helper.py に切り出している。
"""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from app_helper import (
    RunResult,
    copy_source_csv,
    generate_run_id,
    make_output_dir,
    read_file_bytes,
    run_pipeline,
    safe_resolve,
    save_source_csv,
)
from expense_core import (
    IssueRow,
    SummaryRow,
    WarningRow,
)
from ui_html import normalize_html_fragment

# セッションに直前の実行結果を残し、画面が再描画されても結果を見失わないようにする。
LAST_RUN_KEY = "last_run"
# サンプル CSV は「まず触ってみる」入口。入力形式の学習にも使う。
SAMPLE_BAD_CSV_PATH = Path("data/sample_bad.csv")
SAMPLE_GOOD_CSV_PATH = Path("data/sample_good.csv")

# Streamlit のページ設定は先に一度だけ行う必要がある。
st.set_page_config(page_title="支出ツール 2.0", layout="wide")



def _render_html_markup(markup: str) -> None:
    """HTML 文字列を Streamlit に渡す前の共通入口。

    `st.markdown(..., unsafe_allow_html=True)` は HTML を描画できるが、
    複数行文字列の行頭に空白が残っていると Markdown 側が
    「コードブロック」と誤解してしまうことがある。
    毎回同じ前処理を書き忘れないよう、この関数に集約している。
    """
    # 表示崩れの原因だった「先頭インデント付き HTML」をここで必ず正規化する。
    st.markdown(normalize_html_fragment(markup), unsafe_allow_html=True)


def _inject_styles() -> None:
    """画面全体で使う CSS をまとめて差し込む。

    見た目の調整を 1 か所へ集めておくと、配色や余白を直したいときに
    集計ロジックまで触らずに済む。初心者でも「見た目」と「処理」の
    役割を分けて追いやすくなる。
    """
    _render_html_markup(
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

          /* Streamlit 標準のアップロード欄は文言を直接日本語化しにくい。
             そこで元の英語を見えなくし、見た目だけ日本語へ差し替える。 */
          [data-testid="stFileUploaderDropzoneInstructions"] > div:first-child,
          [data-testid="stFileUploaderDropzoneInstructions"] > span:first-child {
            font-size: 0;
          }

          [data-testid="stFileUploaderDropzoneInstructions"] > div:first-child::after,
          [data-testid="stFileUploaderDropzoneInstructions"] > span:first-child::after {
            content: "ここにファイルをドラッグ＆ドロップ";
            font-size: 1rem;
          }

          [data-testid="stFileUploaderDropzoneInstructions"] small {
            font-size: 0;
          }

          [data-testid="stFileUploaderDropzoneInstructions"] small::after {
            content: "1ファイルあたり上限 200MB・CSV";
            font-size: 0.95rem;
          }

          [data-testid="stFileUploaderDropzone"] button {
            font-size: 0;
            position: relative;
          }

          [data-testid="stFileUploaderDropzone"] button::after {
            content: "ファイルを選択";
            font-size: 1rem;
          }

          /* タブの文字色を常に読めるようにする */
          button[data-baseweb="tab"] {
            color: var(--muted) !important;
            font-weight: 600;
          }

          button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--accent) !important;
            font-weight: 700;
          }

          /* 元ファイルのパス表示も薄すぎるので補正 */
          [data-testid="stCaptionContainer"] {
            color: var(--muted) !important;
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
        """
    )


def _to_int(value: Any) -> int | None:
    """値を整数に寄せる。

    変換失敗で例外を投げず None にすることで、表示側の集計処理を安全に続けやすくする。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: int | None, suffix: str = "") -> str:
    """数値を画面向けの表示文字列にする。

    None を "-" にして、「まだ計算できない」と 0 を見分けやすくする。
    """
    if value is None:
        return "-"
    return f"{value:,}{suffix}"


def _summary_pairs(summary: list[SummaryRow], summary_type: str) -> list[tuple[str, int]]:
    """summary の共通形式から、グラフ向けの `(ラベル, 数値)` を抜き出す。

    ヘッダ行や数値でない値はここで除外し、描画側の分岐を減らす。
    """
    pairs: list[tuple[str, int]] = []
    for row in summary:
        if row["type"] != summary_type:
            continue
        amount = _to_int(row["value"])
        if amount is None:
            continue
        key = row["key"]
        if not key:
            continue
        pairs.append((key, amount))
    return pairs


def _summary_stats(summary: list[SummaryRow]) -> dict[str, int]:
    """summary から統計値だけを辞書にまとめ直す。

    `average` や `max` を名前で引けるようにして、画面側の読みやすさを保つ。
    """
    stats: dict[str, int] = {}
    for row in summary:
        if row["type"] != "stats":
            continue
        amount = _to_int(row["value"])
        if amount is None:
            continue
        key = row["key"]
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
    """データフレーム表示用の辞書リストへ整形する。

    列名を引数で受け取ることで、月別・カテゴリ別など複数の表で同じ関数を再利用できる。
    """
    return [
        {key_label: key, value_label: _format_number(value, suffix)}
        for key, value in pairs
    ]


def _count_warning_kinds(warnings: list[WarningRow]) -> list[tuple[str, int]]:
    """警告の種類ごとの件数を数える。"""
    counts: Counter[str] = Counter()
    for warning in warnings:
        kind = warning["kind"].strip()
        if kind:
            counts[kind] += 1
    return counts.most_common()


def _count_error_reasons(errors: list[IssueRow]) -> list[tuple[str, int]]:
    """エラー理由ごとの件数を数える。

    `reason` は " / " 区切りで複数理由を持てるため、先に分解してから集計する。
    """
    counts: Counter[str] = Counter()
    for error in errors:
        text = error["reason"].strip()
        if not text:
            continue
        for reason in text.split(" / "):
            reason = reason.strip()
            if reason:
                counts[reason] += 1
    return counts.most_common()


def _render_html_card(title: str, body: str, eyebrow: str | None = None) -> None:
    """説明カードの外枠をそろえて描画する。

    `body` にはカードの中身の HTML を渡し、この関数では枠や見出しを担当する。
    タイトル類を `escape()` しておくと、CSV 由来の文字列に `<` や `>` が混ざっても
    HTML のタグとして誤解されず、表示崩れを防げる。
    """
    eyebrow_html = f'<div class="eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    _render_html_markup(
        f"""
        <div class="soft-card">
          {eyebrow_html}
          <h3>{escape(title)}</h3>
          {body}
        </div>
        """
    )


def _render_bar_card(
    title: str,
    pairs: list[tuple[str, int]],
    *,
    suffix: str = "円",
    tone: str = "default",
    empty_message: str = "表示できるデータがありません。",
) -> None:
    """横棒グラフ風のカードを HTML と CSS だけで描画する。

    専用のグラフライブラリを使わず、金額に応じて棒の幅を変えている。
    数字だけでなく長さでも差が分かるので、一覧をざっと見たときに
    傾向をつかみやすい。
    """
    if not pairs:
        _render_html_markup(
            f"""
            <div class="bar-card">
              <h3>{escape(title)}</h3>
              <p class="empty-copy">{escape(empty_message)}</p>
            </div>
            """
        )
        return

    # 全件が 0 円でも 0 で割って幅計算が壊れないよう、最低値を 1 にして守る。
    max_value = max(value for _, value in pairs) or 1
    rows_html: list[str] = []
    for label, value in pairs:
        # 値が小さい項目でも棒が完全に消えると比較しづらい。
        # 最低幅を少し残して、「項目が存在すること」が目で分かるようにする。
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

    # 行ごとに作った HTML を 1 枚のカードへまとめ、共通入口から描画する。
    _render_html_markup(
        f"""
        <div class="bar-card">
          <h3>{escape(title)}</h3>
          {''.join(rows_html)}
        </div>
        """
    )


def _render_hero() -> None:
    """画面上部の導入ブロックを描画する。

    初見でも「この画面で何ができるか」が最初の数秒で分かるようにする。
    """
    _render_html_markup(
        """
        <div class="hero">
          <div class="eyebrow">Portfolio 2.0</div>
          <h1>支出ツール</h1>
          <p>
            CSV チェックとレポート生成を、読む順番が自然なダッシュボードに再構成しました。
            入力、判定、要点、詳細、ダウンロードを一画面で追える構成です。
          </p>
          <div class="hero-tags">
            <div class="hero-tag">検証を優先</div>
            <div class="hero-tag">読みやすい導線</div>
            <div class="hero-tag">CSV / Excel / HTML</div>
          </div>
        </div>
        """
    )


def _render_empty_state() -> None:
    """まだ実行していないときの案内画面を描画する。

    最初の一歩を UI 内に置いておくと、README を開かなくても試し始めやすい。
    """
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
            eyebrow="入力",
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
            eyebrow="確認",
        )
    with step3:
        _render_html_card(
            "3. 成果物を出す",
            """
            <p>
              clean / summary の CSV に加えて、Excel と HTML のレポートを同じ画面から取得できます。
            </p>
            """,
            eyebrow="出力",
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
            eyebrow="変更点",
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
    errors: list[IssueRow],
    warnings: list[WarningRow],
    category_pairs: list[tuple[str, int]],
    merchant_pairs: list[tuple[str, int]],
) -> list[str]:
    """結果から短い要点文を組み立てる。

    数字だけでは優先順位が分かりにくいので、「まず何を見るか」を文章で先に示す。
    """
    lines: list[str] = []

    if errors:
        lines.append(f"エラーが {len(errors)} 件あるため、元 CSV の修正が先です。")
    elif warnings:
        lines.append(f"形式チェックは通過していますが、ルール警告が {len(warnings)} 件あります。")
    else:
        lines.append("エラーも警告もなく、そのままレポートを共有できる状態です。")

    if category_pairs:
        category, amount = max(category_pairs, key=lambda item: item[1])
        lines.append(
            f"支出最大カテゴリは {category} で、合計 {_format_number(amount, '円')} です。"
        )

    if merchant_pairs:
        merchant, amount = merchant_pairs[0]
        lines.append(f"支出先トップは {merchant} で、合計 {_format_number(amount, '円')} です。")

    return lines


def _render_run_header(last_run: dict[str, Any]) -> None:
    """直近実行の状態を一言で示すヘッダを描画する。

    先に修正すべきか、確認して配布へ進めるかを冒頭で判断できるようにする。
    """
    errors = last_run["errors"]
    warnings = last_run["warnings"]

    if errors:
        eyebrow = "要修正"
        headline = "先に CSV を修正する段階です"
        copy = "形式エラーが残っているため、集計値よりも入力ミスの解消を優先してください。"
    elif warnings:
        eyebrow = "要確認"
        headline = "集計は可能ですが、ルール面の確認が必要です"
        copy = "未知カテゴリや上限超過など、判断が必要な警告を含んでいます。"
    else:
        eyebrow = "準備完了"
        headline = "クリーンに通過しました"
        copy = "検証とルール適用の両方を通過しており、成果物の配布に進めます。"

    source_name = escape(last_run["source_name"])
    _render_html_markup(
        f"""
        <div class="hero">
          <div class="eyebrow">{eyebrow}</div>
          <h2>{headline}</h2>
          <p>{copy}<br />元ファイル: <strong>{source_name}</strong></p>
        </div>
        """
    )

    source_path = last_run.get("source_path")
    if source_path:
        st.caption(f"元ファイルのパス: {source_path}")


def _render_overview(last_run: dict[str, Any]) -> None:
    """全体像タブを描画する。

    件数メトリクス、要点メモ、主要グラフをまとめ、詳細を見る前に状況をつかめるようにする。
    """
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
    # 入力全体のうち、最終的に clean_rows へ残った割合を見る。
    pass_rate = 0.0
    if last_run["input_count"]:
        pass_rate = last_run["clean_count"] / last_run["input_count"]

    # 指標名を日本語で統一しておくと、サイドバーと結果欄を行き来しても意味を見失いにくい。
    metric_cols = st.columns(5)
    metric_cols[0].metric("入力行数", _format_number(last_run["input_count"]))
    metric_cols[1].metric("クリーン行数", _format_number(last_run["clean_count"]))
    metric_cols[2].metric("エラー数", _format_number(len(errors)))
    metric_cols[3].metric("警告数", _format_number(len(warnings)))
    metric_cols[4].metric("通過率", f"{pass_rate:.0%}")

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
            eyebrow="先に確認",
        )
    with right:
        snapshot_cols = st.columns(2)
        snapshot_cols[0].metric("総支出", _format_number(total_spend, "円"))
        snapshot_cols[1].metric("平均", _format_number(avg_spend, "円"))
        snapshot_cols[0].metric("最大支出", _format_number(max_spend, "円"))
        snapshot_cols[1].metric("件数", _format_number(count))

    top_left, top_right = st.columns(2)
    with top_left:
        _render_bar_card("月別支出", month_pairs, empty_message="月別集計がありません。")
        _render_bar_card(
            "カテゴリ別支出",
            category_pairs,
            empty_message="カテゴリ集計がありません。",
        )
    with top_right:
        _render_bar_card(
            f"支出先 Top {last_run['top_n']}",
            merchant_pairs,
            empty_message="支出先ランキングを作れませんでした。",
        )
        _render_bar_card("曜日別支出", weekday_pairs, empty_message="曜日別集計がありません。")


def _render_validation(last_run: dict[str, Any]) -> None:
    """検証結果タブを描画する。

    エラー・警告・クリーン行を分けて見せ、必要な情報だけを段階的に開けるようにする。
    """
    errors = last_run["errors"]
    warnings = last_run["warnings"]
    clean_preview = last_run["clean_preview"]

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

    tab_errors, tab_warnings, tab_clean = st.tabs(["エラー", "警告", "クリーンプレビュー"])

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
        # 画面が重くならないよう、プレビューは先頭 100 行までに絞る。
        st.caption("プレビューは先頭 100 行まで表示しています。")
        if clean_preview:
            st.dataframe(clean_preview, use_container_width=True, hide_index=True)
        else:
            st.info("クリーン行がありません。")


def _render_summary(last_run: dict[str, Any]) -> None:
    """summary.csv 相当の内容を画面向けに並べ直して表示する。"""
    summary = last_run["summary"]

    month_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "month_total"),
        key_label="月",
        value_label="金額",
    )
    category_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "category_total"),
        key_label="カテゴリ",
        value_label="金額",
    )
    merchant_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "merchant_top"),
        key_label="支出先",
        value_label="金額",
    )
    weekday_rows = _pairs_to_display_rows(
        _summary_pairs(summary, "weekday_total"),
        key_label="曜日",
        value_label="金額",
    )
    stats = _summary_stats(summary)
    # `count` だけは件数なので単位を付けず、それ以外は金額として見せる。
    stats_rows = [
        {"項目": key, "値": _format_number(value, "円" if key != "count" else "")}
        for key, value in stats.items()
    ]

    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("月別 / カテゴリ別")
        st.dataframe(month_rows, use_container_width=True, hide_index=True)
        st.dataframe(category_rows, use_container_width=True, hide_index=True)
    with top_right:
        st.subheader("支出先 / 曜日別")
        st.dataframe(merchant_rows, use_container_width=True, hide_index=True)
        st.dataframe(weekday_rows, use_container_width=True, hide_index=True)

    st.subheader("統計")
    st.dataframe(stats_rows, use_container_width=True, hide_index=True)


def _render_downloads(last_run: dict[str, Any]) -> None:
    """生成ファイル一覧とダウンロードボタンを描画する。

    ファイル内容は描画時点で読み直し、直前の実行結果とずれないようにする。
    """
    output_paths = {key: Path(value) for key, value in last_run["output_paths"].items()}

    file_col, button_col = st.columns([0.9, 1.1])
    with file_col:
        st.subheader("生成ファイル")
        for path in output_paths.values():
            _render_html_markup(f'<div class="file-chip">{escape(str(path))}</div>')

    with button_col:
        st.subheader("ダウンロード")

        # 元 CSV のダウンロード: 保存ファイルから読む（session_state に bytes を持たない）
        source_path_str = last_run.get("source_path")
        if source_path_str:
            source_data = read_file_bytes(Path(source_path_str))
            if isinstance(source_data, bytes):
                st.download_button(
                    label="元のCSVをダウンロード",
                    data=source_data,
                    file_name=last_run["source_name"],
                    mime="text/csv",
                    use_container_width=True,
                    key="download_source_csv",
                )

        # 画面ラベルと MIME type をまとめて定義し、ボタン生成を共通化する。
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
            output_path = output_paths.get(key)
            if output_path is None:
                continue
            payload = read_file_bytes(output_path)
            if payload is None:
                st.warning(f"出力ファイルを読み込めませんでした: {output_path}")
                continue
            st.download_button(
                label=f"{label} をダウンロード",
                data=payload,
                file_name=output_path.name,
                mime=mime,
                use_container_width=True,
                key=f"download_{key}",
            )


def main() -> None:
    """Streamlit 画面の入口。

    サイドバーで入力を受け取り、結果を session_state に保存して再描画でも保持する。
    """
    _inject_styles()
    _render_hero()

    # 入力部はサイドバーに寄せ、中央カラムは結果の読解に専念できるようにする。
    with st.sidebar:
        # まず「何を入力する場所か」が分かるよう、見出しやラベルを日本語で統一する。
        st.header("実行設定")
        uploaded_csv = st.file_uploader("CSV ファイル", type=["csv"])
        st.caption("必須列: date / amount / merchant / category")
        run_upload_btn = st.button(
            "アップロードした CSV を実行",
            type="primary",
            use_container_width=True,
        )

        with st.expander("レポート設定", expanded=True):
            top_n = st.number_input("上位の支出先数", min_value=1, max_value=50, value=10, step=1)
            do_excel = st.checkbox("Excel (.xlsx) を生成", value=True)
            do_html = st.checkbox("HTML レポートを生成", value=True)

        with st.expander("パス設定", expanded=False):
            st.caption("rules.json のパス = 判定ルールの置き場所")
            rules_path_str = st.text_input("rules.json のパス", value="rules.json")
            st.caption("出力先ディレクトリ = 結果ファイルの保存先")
            out_dir_str = st.text_input("出力先ディレクトリ", value="out/gui")

        st.divider()
        st.caption("サンプル実行")
        sample_bad_col, sample_good_col = st.columns(2)
        with sample_bad_col:
            run_sample_bad_btn = st.button("エラーあり", use_container_width=True)
        with sample_good_col:
            run_sample_good_btn = st.button("正常サンプル", use_container_width=True)

    run_error: str | None = None

    # ── パストラバーサル対策 ──
    _project_root = Path.cwd().resolve()

    # どのボタンから実行しても、ここから先は同じパイプラインに流す。
    if run_upload_btn or run_sample_bad_btn or run_sample_good_btn:
        rules_path = safe_resolve(rules_path_str, _project_root)
        out_base = safe_resolve(out_dir_str, _project_root)
        result: RunResult | None = None

        if rules_path is None or out_base is None:
            run_error = (
                "パスがプロジェクトディレクトリの外を指しています。"
                "安全のためブロックしました。"
            )
        elif not rules_path.exists():
            run_error = f"rules.json が見つかりません: {rules_path}"
        else:
            try:
                run_id = generate_run_id()
                out_dir = make_output_dir(out_base, run_id)

                if run_upload_btn:
                    if uploaded_csv is None:
                        run_error = "実行前に CSV ファイルをアップロードしてください。"
                    else:
                        # アップロードファイルを run_id ディレクトリに保存
                        source_saved = save_source_csv(
                            uploaded_csv.getvalue(),
                            str(uploaded_csv.name),
                            out_dir,
                        )
                        result = run_pipeline(
                            csv_path=source_saved,
                            rules_path=rules_path,
                            out_dir=out_dir,
                            top_n=int(top_n),
                            do_excel=do_excel,
                            do_html=do_html,
                            run_id=run_id,
                        )
                else:
                    sample_csv_path = (
                        SAMPLE_BAD_CSV_PATH if run_sample_bad_btn else SAMPLE_GOOD_CSV_PATH
                    )
                    if not sample_csv_path.exists():
                        run_error = f"サンプル CSV が見つかりません: {sample_csv_path}"
                    else:
                        # サンプル CSV を run_id ディレクトリにコピー
                        source_saved = copy_source_csv(sample_csv_path, out_dir)
                        result = run_pipeline(
                            csv_path=source_saved,
                            rules_path=rules_path,
                            out_dir=out_dir,
                            top_n=int(top_n),
                            do_excel=do_excel,
                            do_html=do_html,
                            run_id=run_id,
                        )
            # ── 例外を具体的に列挙してキャッチする ──
            except (
                ValueError,          # CSV の形式不正、数値変換失敗、rules.json 検証エラーなど
                FileNotFoundError,   # ファイルが存在しない
                PermissionError,     # ファイルの読み書き権限がない
                UnicodeDecodeError,  # 文字コードが UTF-8 でない
                json.JSONDecodeError,  # rules.json の JSON 構文エラー
                OSError,             # ディスク容量不足などの OS レベルのエラー
            ) as exc:
                # pragma: no cover - UI surface
                run_error = f"実行に失敗しました: {exc}"

        if result is not None:
            # rerun 後もタブ表示やダウンロードボタンを維持するため、結果を保存する。
            st.session_state[LAST_RUN_KEY] = result

    if run_error:
        st.error(run_error)

    last_run = st.session_state.get(LAST_RUN_KEY)
    if last_run is None:
        _render_empty_state()
        return

    _render_run_header(last_run)

    # 情報を「全体像 → 検証 → 集計 → ダウンロード」の順で読む前提で並べる。
    # ラベルも日本語にして、画面全体の用語をそろえる。
    tab_overview, tab_validation, tab_summary, tab_downloads = st.tabs(
        ["概要", "検証", "集計", "ダウンロード"]
    )
    with tab_overview:
        _render_overview(last_run)
    with tab_validation:
        _render_validation(last_run)
    with tab_summary:
        _render_summary(last_run)
    with tab_downloads:
        _render_downloads(last_run)


# Streamlit はスクリプトを上から実行するので、最後に入口関数を呼ぶ。
main()
