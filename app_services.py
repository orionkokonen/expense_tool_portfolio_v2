# -*- coding: utf-8 -*-
"""Service helpers shared by the Streamlit UI.

The UI stays focused on rendering and user interaction while this module handles
path safety, upload persistence, and the shared report pipeline.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Protocol

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

MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


class UploadLike(Protocol):
    """Minimal interface needed from Streamlit UploadedFile."""

    name: str
    size: int | None

    def getbuffer(self) -> bytes: ...


def ensure_dir(path: Path) -> None:
    """Create the directory tree ahead of writing outputs."""

    path.mkdir(parents=True, exist_ok=True)


def _stamp_name(prefix: str, base: str, ext: str) -> str:
    """Generate stable output names like ``foo_errors.csv``."""

    return f"{prefix}_{base}.{ext}"


def resolve_project_path(raw: str, *, project_root: Path | None = None) -> Path | None:
    """Resolve a user-supplied path only when it stays inside the project root."""

    candidate = raw.strip()
    if not candidate:
        return None

    root = (project_root or Path.cwd()).resolve()
    try:
        resolved = (root / candidate).resolve()
    except (OSError, RuntimeError, ValueError):
        return None

    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _safe_upload_name(name: str) -> str:
    """Drop any path components and avoid reusing user-controlled filenames."""

    original = Path(name or "").name
    suffix = Path(original).suffix.lower()
    if suffix != ".csv":
        suffix = ".csv"
    return f"upload_{secrets.token_hex(8)}{suffix}"


def save_upload(uploaded_file: UploadLike, dir_path: Path) -> Path:
    """Persist an uploaded CSV to a temp directory with a sanitized filename."""

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"アップロード上限は {MAX_UPLOAD_SIZE_MB}MB です。"
            "大きな CSV は CLI を使うか、分割して実行してください。"
        )

    ensure_dir(dir_path)
    path = dir_path / _safe_upload_name(uploaded_file.name)
    path.write_bytes(bytes(uploaded_file.getbuffer()))
    return path


def run_pipeline(
    *,
    csv_path: Path,
    rules_path: Path,
    out_dir: Path,
    top_n: int = 10,
    do_excel: bool = True,
    do_html: bool = True,
) -> dict[str, object]:
    """Run the shared check/report pipeline for the Streamlit app."""

    ensure_dir(out_dir)
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
    write_csv(str(clean_csv), clean_rows, ["row", "date", "amount", "merchant", "category"])
    write_csv(str(summary_csv), summary, ["type", "key", "value"])

    output_paths: dict[str, Path] = {
        "errors_csv": errors_csv,
        "warnings_csv": warnings_csv,
        "clean_csv": clean_csv,
        "summary_csv": summary_csv,
    }

    if do_excel:
        xlsx_path = out_dir / _stamp_name(prefix, "report", "xlsx")
        write_xlsx_report(
            path=xlsx_path,
            errors=errors,
            warnings=warnings,
            clean=clean_rows,
            summary=summary,
        )
        output_paths["report_xlsx"] = xlsx_path

    if do_html:
        html_path = out_dir / _stamp_name(prefix, "report", "html")
        write_html_report(
            path=html_path,
            errors=errors,
            warnings=warnings,
            clean=clean_rows,
            summary=summary,
            title="支出レポート",
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
