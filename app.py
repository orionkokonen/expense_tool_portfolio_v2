# -*- coding: utf-8 -*-
"""
app.py
Streamlit GUI for Expense Tool
"""

from __future__ import annotations

from pathlib import Path
import tempfile

import streamlit as st

from expense_core import read_csv, check_rows, normalize_ok_rows, make_summary, write_csv
from rules import load_rules, apply_rules
from excel_export import write_xlsx_report
from html_report import write_html_report


st.set_page_config(page_title="Expense Tool", layout="wide")
st.title("Expense Tool（経費CSVチェック＆レポート生成）")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded_file, dir_path: Path) -> Path:
    path = dir_path / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def _stamp_name(prefix: str, base: str, ext: str) -> str:
    return f"{prefix}_{base}.{ext}"


with st.sidebar:
    st.header("入力")
    uploaded_csv = st.file_uploader("経費CSVをアップロード", type=["csv"])
    rules_path_str = st.text_input("rules.json のパス", value="rules.json")
    out_dir_str = st.text_input("出力フォルダ", value="out/gui")
    top_n = st.number_input("merchant上位の件数", min_value=1, max_value=50, value=10, step=1)

    st.header("出力")
    do_excel = st.checkbox("Excel(.xlsx)も作る", value=True)
    do_html = st.checkbox("HTMLレポートも作る", value=True)

    run_btn = st.button("実行（check + report）", type="primary")


if not run_btn:
    st.info("左のサイドバーでCSVをアップロードして、「実行」を押してください。")
    st.stop()

if uploaded_csv is None:
    st.error("CSVが未選択です。まずCSVをアップロードしてください。")
    st.stop()

rules_path = Path(rules_path_str)
if not rules_path.exists():
    st.error(f"rules.json が見つかりません: {rules_path}")
    st.stop()

out_dir = Path(out_dir_str)
_ensure_dir(out_dir)

# 一時作業フォルダ（アップロードファイル保存用）
with tempfile.TemporaryDirectory() as tmp:
    tmp_dir = Path(tmp)
    csv_path = _save_upload(uploaded_csv, tmp_dir)

    prefix = csv_path.stem  # sample_bad など

    # 1) 取り込み
    rows = read_csv(str(csv_path))

    # 2) 構造チェック -> errors
    ok_rows, errors = check_rows(rows)

    # 3) ルールチェック -> (clean_rows, warnings)
    rules = load_rules(rules_path)
    ok_norm = normalize_ok_rows(ok_rows)
    clean_rows, warnings = apply_rules(ok_norm, rules)

    # 4) 集計（clean_rowsでやる）
    summary = make_summary(clean_rows, top_n=int(top_n))

    # 5) CSV出力
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

    # 6) Excel / HTML 出力
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

    if do_html:
        write_html_report(
            path=html_path,
            errors=errors,
            warnings=warnings,
            clean=clean_rows,
            summary=summary,
            title="Expense Tool Report",
        )

# 画面に結果表示
col1, col2 = st.columns(2)

with col1:
    st.subheader("errors（構造エラー）")
    st.write(f"件数: {len(errors)}")
    st.dataframe(errors, use_container_width=True)

with col2:
    st.subheader("warnings（ルール警告）")
    st.write(f"件数: {len(warnings)}")
    st.dataframe(warnings, use_container_width=True)

st.subheader("summary（集計）")
st.dataframe(summary, use_container_width=True)

st.subheader("出力ファイル")
st.write(f"- {errors_csv}")
st.write(f"- {warnings_csv}")
st.write(f"- {clean_csv}")
st.write(f"- {summary_csv}")
if do_excel:
    st.write(f"- {xlsx_path}")
if do_html:
    st.write(f"- {html_path}")

st.success("完了しました。")
