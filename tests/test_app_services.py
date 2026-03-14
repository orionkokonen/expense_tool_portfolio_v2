# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app_services import (
    MAX_UPLOAD_SIZE_BYTES,
    resolve_project_path,
    run_pipeline,
    save_upload,
)


class _FakeUpload:
    def __init__(self, name: str, content: bytes, size: int | None = None) -> None:
        self.name = name
        self._content = content
        self.size = len(content) if size is None else size

    def getbuffer(self) -> bytes:
        return self._content


def _write_csv(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "amount", "merchant", "category"])
        writer.writeheader()
        writer.writerow(
            {
                "date": "2026-01-10",
                "amount": "1200",
                "merchant": "Cafe",
                "category": "食費",
            }
        )


def _write_rules(path: Path) -> None:
    path.write_text(json.dumps({"allowed_categories": ["食費"]}), encoding="utf-8")


def test_resolve_project_path_allows_project_file(tmp_path: Path) -> None:
    resolved = resolve_project_path("rules.json", project_root=tmp_path)
    assert resolved == (tmp_path / "rules.json").resolve()


def test_resolve_project_path_blocks_sibling_directory(tmp_path: Path) -> None:
    raw = str(Path("..") / f"{tmp_path.name}_backup" / "rules.json")
    assert resolve_project_path(raw, project_root=tmp_path) is None


def test_save_upload_sanitizes_filename(tmp_path: Path) -> None:
    saved = save_upload(_FakeUpload("..\\nested\\evil.csv", b"date,amount\n"), tmp_path)
    assert saved.parent == tmp_path
    assert saved.name.startswith("upload_")
    assert ".." not in saved.name


def test_save_upload_rejects_large_files(tmp_path: Path) -> None:
    upload = _FakeUpload("large.csv", b"x", size=MAX_UPLOAD_SIZE_BYTES + 1)
    with pytest.raises(ValueError):
        save_upload(upload, tmp_path)


def test_run_pipeline_writes_clean_csv_with_row_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    rules_path = tmp_path / "rules.json"
    out_dir = tmp_path / "out"
    _write_csv(csv_path)
    _write_rules(rules_path)

    run_pipeline(
        csv_path=csv_path,
        rules_path=rules_path,
        out_dir=out_dir,
        top_n=10,
        do_excel=False,
        do_html=False,
    )

    clean_csv = out_dir / "sample_clean.csv"
    with open(clean_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == ["row", "date", "amount", "merchant", "category"]
