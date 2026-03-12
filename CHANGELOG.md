<!-- 学習用メモ: CHANGELOG は「今どう動くか」より「いつ何が変わったか」を見る場所。 -->

# CHANGELOG

このファイルは、ブラッシュアップや機能追加の履歴を時系列で記録します。

## Unreleased

- Added `ROADMAP.md` for tracking upcoming implementation plans.
- Fixed CI failures caused by `mypy` type mismatches across the expense processing pipeline.
- Added explicit typed row models for warnings and summary data, and aligned `rules.py`, `app.py`, and report exporters with the normalized data flow.
- Tightened Streamlit typing around uploads, counters, output paths, and `defaultdict` usage so `ruff`, `mypy`, and `pytest` all pass locally again.
- Fixed Streamlit cards rendering raw HTML as plain text by normalizing indented HTML fragments before passing them to `st.markdown(..., unsafe_allow_html=True)`.

　

## v0.3

- Streamlit GUI: added `Run sample_bad.csv` button for one-click sample execution.
- Streamlit GUI: added direct download buttons for `errors.csv`, `warnings.csv`, `clean.csv`, `summary.csv`, `report.xlsx`, and `report.html`.
- Streamlit GUI: added `st.session_state["last_run"]` persistence so result tables and download buttons remain visible after reruns.

## v0.2

- Added `rules.json` support, including category rules, banned words, date range checks, and amount limit checks.
- Added `warnings.csv` output and warning handling flow.
- Added Excel (`.xlsx`) and HTML report generation.
- Added summary enhancements (top merchants, weekday totals, average, median).
- Added `--timestamp` output naming option.
- Added coverage and basic tests.

## v0.1

- Added core CSV validation and error detection.
- Added `errors.csv` and `summary.csv` outputs.
