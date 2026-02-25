# -*- coding: utf-8 -*-
"""Streamlit GUI for Expense Tool."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

import streamlit as st

from expense_core import check_rows, make_summary, normalize_ok_rows, read_csv, write_csv
from excel_export import write_xlsx_report
from html_report import write_html_report
from rules import apply_rules, load_rules

LAST_RUN_KEY = "last_run"
SAMPLE_CSV_PATH = Path("data/sample_bad.csv")


st.set_page_config(page_title="Expense Tool", layout="wide")
st.title("Expense Tool - CSV Check + Report")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded_file, dir_path: Path) -> Path:
    path = dir_path / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def _stamp_name(prefix: str, base: str, ext: str) -> str:
    return f"{prefix}_{base}.{ext}"


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
        "output_paths": {k: str(v) for k, v in output_paths.items()},
        "enabled_outputs": {"excel": do_excel, "html": do_html},
    }


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


with st.sidebar:
    st.header("Input")
    uploaded_csv = st.file_uploader("Upload input CSV", type=["csv"])
    rules_path_str = st.text_input("rules.json path", value="rules.json")
    out_dir_str = st.text_input("Output directory", value="out/gui")
    top_n = st.number_input("Top merchants", min_value=1, max_value=50, value=10, step=1)

    st.header("Outputs")
    do_excel = st.checkbox("Generate Excel (.xlsx)", value=True)
    do_html = st.checkbox("Generate HTML report", value=True)

    run_upload_btn = st.button("Run with uploaded CSV", type="primary")
    run_sample_btn = st.button("Run sample_bad.csv")

run_error: str | None = None

if run_upload_btn or run_sample_btn:
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
            else:
                if not SAMPLE_CSV_PATH.exists():
                    run_error = f"Sample CSV not found: {SAMPLE_CSV_PATH}"
                else:
                    result = _run_pipeline(
                        csv_path=SAMPLE_CSV_PATH,
                        rules_path=rules_path,
                        out_dir=out_dir,
                        top_n=int(top_n),
                        do_excel=do_excel,
                        do_html=do_html,
                    )
        except Exception as exc:
            run_error = f"Run failed: {exc}"

    if result is not None:
        st.session_state[LAST_RUN_KEY] = result
        st.success(f"Run completed: {result['source_name']}")

if run_error:
    st.error(run_error)

last_run = st.session_state.get(LAST_RUN_KEY)
if last_run is None:
    st.info("Upload a CSV and run, or click 'Run sample_bad.csv'.")
    st.stop()

errors = last_run["errors"]
warnings = last_run["warnings"]
summary = last_run["summary"]
output_paths = {k: Path(v) for k, v in last_run["output_paths"].items()}

st.subheader("Run Result")
st.write(f"Source: `{last_run['source_name']}`")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Errors")
    st.write(f"Count: {len(errors)}")
    st.dataframe(errors, width="stretch")
with col2:
    st.subheader("Warnings")
    st.write(f"Count: {len(warnings)}")
    st.dataframe(warnings, width="stretch")

st.subheader("Summary")
st.dataframe(summary, width="stretch")

st.subheader("Generated files")
for path in output_paths.values():
    st.write(f"- `{path}`")

st.subheader("Download outputs")
download_specs = [
    ("errors_csv", "Download errors.csv", "text/csv"),
    ("warnings_csv", "Download warnings.csv", "text/csv"),
    ("clean_csv", "Download clean.csv", "text/csv"),
    ("summary_csv", "Download summary.csv", "text/csv"),
    ("report_xlsx", "Download report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("report_html", "Download report.html", "text/html"),
]

for key, label, mime in download_specs:
    path = output_paths.get(key)
    if path is None:
        continue
    payload = _read_bytes(path)
    if payload is None:
        st.warning(f"Could not read output file for download: {path}")
        continue
    st.download_button(
        label=label,
        data=payload,
        file_name=path.name,
        mime=mime,
        key=f"download_{key}",
    )
