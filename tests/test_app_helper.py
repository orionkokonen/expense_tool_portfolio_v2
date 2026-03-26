# このファイルは、画面アプリ向け補助処理が正しく動くか確かめるテストです。
# -*- coding: utf-8 -*-
"""
tests/test_app_helper.py — app_helper.py の単体テスト。

ここで見ていること:
  - safe_resolve がプロジェクト内のみ許可し、近い別パスを拒否するか
  - run_pipeline が最小限の結果を返し、session_state に不要なデータを持たないか
  - GUI テスト相当の確認（初期表示、サンプル実行、エラー表示、ダウンロード対象）
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app_helper import (
    generate_run_id,
    make_output_dir,
    read_file_bytes,
    run_pipeline,
    safe_resolve,
    save_source_csv,
)

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """テスト用 CSV を書き出す。"""
    fieldnames = ["date", "amount", "merchant", "category"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _good_rows() -> list[dict[str, str]]:
    return [
        {"date": "2026-01-10", "amount": "1200", "merchant": "カフェA", "category": "会議費"},
        {"date": "2026-01-15", "amount": "3500", "merchant": "ホテルB", "category": "旅費"},
    ]


def _write_rules(path: Path, data: dict[str, object] | None = None) -> Path:
    """テスト用 rules.json を書き出す。"""
    if data is None:
        data = {}
    p = path / "rules.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# safe_resolve のテスト
# ---------------------------------------------------------------------------

class TestSafeResolve:
    """safe_resolve() のパス安全性テスト。"""

    def test_project_internal_path(self) -> None:
        """プロジェクト内のパスは許可されるか。"""
        project_root = Path.cwd().resolve()
        result = safe_resolve("sub/dir", project_root)
        assert result is not None

    def test_traversal_outside_project(self, tmp_path: Path) -> None:
        """.. でプロジェクト外を指すパスを拒否するか。"""
        project_root = (tmp_path / "project").resolve()
        project_root.mkdir()
        result = safe_resolve("../../etc/passwd", project_root)
        assert result is None

    def test_similar_prefix_rejected(self, tmp_path: Path) -> None:
        """'project2' のような近い別パスを拒否するか。

        文字列前方一致だと 'project' と 'project2' を区別できないが、
        Path.is_relative_to() 相当の比較なら正しく拒否できる。
        """
        project = tmp_path / "project"
        project.mkdir()
        project2 = tmp_path / "project2"
        project2.mkdir()

        project_root = project.resolve()
        # project2 内のパスを project のルートで検証 → 拒否されるべき
        result = safe_resolve(str(project2 / "data"), project_root)
        assert result is None

    def test_invalid_path_characters(self, tmp_path: Path) -> None:
        """不正な文字を含むパスは None になるか。"""
        project_root = tmp_path.resolve()
        result = safe_resolve("\x00bad", project_root)
        assert result is None


# ---------------------------------------------------------------------------
# run_pipeline のテスト
# ---------------------------------------------------------------------------

class TestRunPipeline:
    """run_pipeline() の結合テスト。"""

    def test_basic_run(self, tmp_path: Path) -> None:
        """正常 CSV で結果が返るか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        rules_path = _write_rules(tmp_path)
        out_dir = tmp_path / "out" / "test_run"
        out_dir.mkdir(parents=True)

        result = run_pipeline(
            csv_path=csv_path,
            rules_path=rules_path,
            out_dir=out_dir,
            top_n=10,
            do_excel=False,
            do_html=False,
            run_id="test123",
        )

        assert result["run_id"] == "test123"
        assert result["input_count"] == 2
        assert result["clean_count"] == 2
        assert "errors_csv" in result["output_paths"]
        assert "warnings_csv" in result["output_paths"]

    def test_no_source_bytes_in_result(self, tmp_path: Path) -> None:
        """結果に source_bytes が含まれないか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        rules_path = _write_rules(tmp_path)
        out_dir = tmp_path / "out" / "run2"
        out_dir.mkdir(parents=True)

        result = run_pipeline(
            csv_path=csv_path,
            rules_path=rules_path,
            out_dir=out_dir,
            top_n=10,
            do_excel=False,
            do_html=False,
            run_id="run2",
        )

        assert "source_bytes" not in result

    def test_no_full_clean_rows_in_result(self, tmp_path: Path) -> None:
        """結果に full clean_rows が含まれないか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        rules_path = _write_rules(tmp_path)
        out_dir = tmp_path / "out" / "run3"
        out_dir.mkdir(parents=True)

        result = run_pipeline(
            csv_path=csv_path,
            rules_path=rules_path,
            out_dir=out_dir,
            top_n=10,
            do_excel=False,
            do_html=False,
            run_id="run3",
        )

        assert "clean_rows" not in result
        assert "clean_preview" in result

    def test_clean_preview_limited_to_100(self, tmp_path: Path) -> None:
        """clean_preview が 100 行以下に制限されるか。"""
        # 150 行の CSV を作る
        rows = [
            {
                "date": "2026-01-10",
                "amount": str(i * 100),
                "merchant": f"M{i}",
                "category": "交通費",
            }
            for i in range(1, 151)
        ]
        csv_path = tmp_path / "large.csv"
        _write_csv(csv_path, rows)
        rules_path = _write_rules(tmp_path)
        out_dir = tmp_path / "out" / "run4"
        out_dir.mkdir(parents=True)

        result = run_pipeline(
            csv_path=csv_path,
            rules_path=rules_path,
            out_dir=out_dir,
            top_n=10,
            do_excel=False,
            do_html=False,
            run_id="run4",
        )

        assert len(result["clean_preview"]) == 100

    def test_invalid_rules_raises_value_error(self, tmp_path: Path) -> None:
        """不正な rules.json で ValueError が出るか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({"allowed_categories": "not_a_list"}), encoding="utf-8")
        out_dir = tmp_path / "out" / "run5"
        out_dir.mkdir(parents=True)

        with pytest.raises(ValueError):
            run_pipeline(
                csv_path=csv_path,
                rules_path=rules_path,
                out_dir=out_dir,
                top_n=10,
                do_excel=False,
                do_html=False,
                run_id="run5",
            )

    def test_download_targets_exist(self, tmp_path: Path) -> None:
        """実行後にダウンロード対象のファイルが実際に存在するか。"""
        csv_path = tmp_path / "good.csv"
        _write_csv(csv_path, _good_rows())
        rules_path = _write_rules(tmp_path)
        out_dir = tmp_path / "out" / "run6"
        out_dir.mkdir(parents=True)

        result = run_pipeline(
            csv_path=csv_path,
            rules_path=rules_path,
            out_dir=out_dir,
            top_n=10,
            do_excel=True,
            do_html=True,
            run_id="run6",
        )

        for key, path_str in result["output_paths"].items():
            assert Path(path_str).exists(), f"{key} のファイルが存在しない: {path_str}"


# ---------------------------------------------------------------------------
# その他のヘルパーテスト
# ---------------------------------------------------------------------------

class TestHelpers:
    """補助関数のテスト。"""

    def test_generate_run_id_length(self) -> None:
        """run_id が 8 文字の 16 進数か。"""
        rid = generate_run_id()
        assert len(rid) == 8
        int(rid, 16)  # 16 進数として解釈できることを確認

    def test_generate_run_id_unique(self) -> None:
        """2 回生成した run_id が異なるか。"""
        assert generate_run_id() != generate_run_id()

    def test_make_output_dir(self, tmp_path: Path) -> None:
        """run_id 付きのサブディレクトリが作られるか。"""
        out_dir = make_output_dir(tmp_path / "out", "abc123")
        assert out_dir.exists()
        assert out_dir.name == "abc123"

    def test_read_file_bytes(self, tmp_path: Path) -> None:
        """存在するファイルを bytes で読めるか。"""
        p = tmp_path / "test.txt"
        p.write_text("hello", encoding="utf-8")
        result = read_file_bytes(p)
        assert result is not None
        assert b"hello" in result

    def test_read_file_bytes_missing(self, tmp_path: Path) -> None:
        """存在しないファイルは None を返すか。"""
        result = read_file_bytes(tmp_path / "missing.txt")
        assert result is None

    def test_save_source_csv(self, tmp_path: Path) -> None:
        """アップロードファイルの bytes を保存できるか。"""
        content = b"date,amount,merchant,category\n2026-01-10,1200,A,food\n"
        dest = save_source_csv(content, "test.csv", tmp_path)
        assert dest.exists()
        assert dest.read_bytes() == content
