# CHANGELOG

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
