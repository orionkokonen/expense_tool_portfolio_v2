# -*- coding: utf-8 -*-
"""
tests/test_rules.py — ルール読み込みと判定処理のテスト。

ここで見ていること:
  - rules.json を正しく読み込めるか
  - カテゴリ、禁止ワード、日付範囲、金額上限の各ルールが効くか

考え方:
  rules.py は設定しだいで動きが変わるので、
  warn / ignore / fallback のように分岐ごとに分けて確認する。
  また、必要に応じて dataclass を直接作ると、
  ファイル準備を減らせてテストの意図が追いやすくなる。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from expense_core import ExpenseRowNorm
from rules import (
    DateRange,
    Limits,
    Rules,
    apply_rules,
    load_rules,
)

# import の並びを一定にすると、依存の向きが追いやすく、レビューでも迷いにくい。
# こうした「先頭のそろえ方」は小さく見えて、CI で同じ整形ルールを守る助けになる。

# ---------------------------------------------------------------------------
# ヘルパー: テスト用の rules.json を一時ファイルに書き出す
# ---------------------------------------------------------------------------

def _write_rules(tmp_path: Path, data: dict) -> Path:
    """テスト用の rules.json を作って Path を返す。

    tmp_path（pytest 提供の一時フォルダ）に書くので、
    テスト後に自動で片付けられる。
    本物の rules.json を触らないので、
    手元の設定を壊さず安全に試せる。
    """
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _row(
    date: str = "2026-01-10",
    amount: int = 1000,
    merchant: str = "テスト商店",
    category: str = "交通費",
    row: str = "2",
) -> ExpenseRowNorm:
    """テスト用の「整形ずみデータ」を作る。

    デフォルト引数を設定しておくと、テストケースごとに
    変えたい項目だけ指定すればよくなり、記述量が減る。
    ここでいう「整形ずみ」は、型や項目名が
    rules.py が受け取りやすい形にそろっている状態のこと。
    例: _row(category="食費") と書けば、他は共通の初期値を使える。
    """
    return {
        "row": row,
        "date": date,
        "amount": amount,
        "merchant": merchant,
        "category": category,
    }


# ---------------------------------------------------------------------------
# load_rules のテスト
# テーマ: JSON ファイルから Rules データクラスへの変換
# ---------------------------------------------------------------------------

class TestLoadRules:
    """rules.json の読み込みテスト。"""

    def test_load_basic(self, tmp_path: Path) -> None:
        """基本的な rules.json の全項目が正しく読み込まれるか。"""
        data = {
            "allowed_categories": ["交通費", "会議費"],
            "unknown_category_mode": "warn",
            "banned_words": ["ギャンブル"],
            "date_range": {"min": "2026-01-01", "max": "2026-12-31"},
            "limits": {"daily_total": 30000},
        }
        rules = load_rules(_write_rules(tmp_path, data))
        assert rules.allowed_categories == ["交通費", "会議費"]
        assert rules.unknown_category_mode == "warn"
        assert rules.banned_words == ["ギャンブル"]
        assert rules.date_range.min == "2026-01-01"
        assert rules.limits.daily_total == 30000

    def test_load_empty_json(self, tmp_path: Path) -> None:
        """空の JSON（{}）でもデフォルト値で読み込めるか。

        設定ファイルが最小限でもアプリが動くようにするための安全策。
        """
        rules = load_rules(_write_rules(tmp_path, {}))
        assert rules.allowed_categories is None
        assert rules.unknown_category_mode == "warn"
        assert rules.banned_words is None

    def test_load_invalid_mode_falls_back_to_warn(self, tmp_path: Path) -> None:
        """unknown_category_mode に想定外の値が入っていたら "warn" に戻るか。

        設定ファイルのタイプミスでアプリが壊れないようにするための安全策。
        """
        data = {"unknown_category_mode": "invalid_mode"}
        rules = load_rules(_write_rules(tmp_path, data))
        assert rules.unknown_category_mode == "warn"

    def test_load_malformed_json_raises(self, tmp_path: Path) -> None:
        """壊れた JSON（構文エラー）は json.JSONDecodeError を出すか。"""
        p = tmp_path / "rules.json"
        p.write_text("{broken", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_rules(p)

    def test_load_root_must_be_object(self, tmp_path: Path) -> None:
        p = tmp_path / "rules.json"
        p.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError):
            load_rules(p)

    def test_load_category_daily_requires_mapping(self, tmp_path: Path) -> None:
        data = {"limits": {"category_daily": ["oops"]}}
        with pytest.raises(ValueError):
            load_rules(_write_rules(tmp_path, data))

    def test_load_daily_total_requires_int(self, tmp_path: Path) -> None:
        data = {"limits": {"daily_total": "5000"}}
        with pytest.raises(ValueError):
            load_rules(_write_rules(tmp_path, data))


# ---------------------------------------------------------------------------
# apply_rules のテスト: カテゴリチェック
# テーマ: unknown_category_mode の 3 モード（warn / ignore / fallback）
# ---------------------------------------------------------------------------

class TestApplyRulesCategory:
    """カテゴリ関連のルール適用テスト。"""

    def test_unknown_category_warn(self) -> None:
        """mode=warn: 未登録カテゴリで警告が出て、カテゴリはそのまま残るか。"""
        rules = Rules(allowed_categories=["交通費"], unknown_category_mode="warn")
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 1
        assert warnings[0]["kind"] == "category_unknown"
        assert clean[0]["category"] == "食費"  # warn ではカテゴリを書き換えない

    def test_unknown_category_ignore(self) -> None:
        """mode=ignore: 未登録カテゴリでも警告が出ないか。"""
        rules = Rules(allowed_categories=["交通費"], unknown_category_mode="ignore")
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0

    def test_unknown_category_fallback(self) -> None:
        """mode=fallback: 未登録カテゴリが fallback_category に書き換わるか。"""
        rules = Rules(
            allowed_categories=["交通費"],
            unknown_category_mode="fallback",
            fallback_category="その他",
        )
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 1  # 置き換えて終わりではなく、記録も残す
        assert clean[0]["category"] == "その他"  # 集計に使う値は fallback に統一

    def test_known_category_no_warning(self) -> None:
        """登録済みカテゴリなら警告が出ないか。"""
        rules = Rules(allowed_categories=["交通費"])
        rows = [_row(category="交通費")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0

    def test_no_allowed_categories_skips_check(self) -> None:
        """allowed_categories が空リスト → 全カテゴリ許可（チェックをスキップ）。"""
        rules = Rules(allowed_categories=[])
        rows = [_row(category="なんでも")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# apply_rules のテスト: 禁止ワード
# テーマ: merchant（加盟店名）に特定の文字列が含まれていたら警告
# ---------------------------------------------------------------------------

class TestApplyRulesBannedWords:
    """禁止ワード検出のテスト。"""

    def test_banned_word_detected(self) -> None:
        """禁止ワードが merchant に含まれていたら警告が出るか。"""
        rules = Rules(banned_words=["ギャンブル"])
        rows = [_row(merchant="ギャンブル商店")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 1
        assert warnings[0]["kind"] == "banned_word"

    def test_no_banned_word(self) -> None:
        """禁止ワードに該当しなければ警告なしか。"""
        rules = Rules(banned_words=["ギャンブル"])
        rows = [_row(merchant="カフェ")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# apply_rules のテスト: 日付範囲
# テーマ: date_range の min/max による範囲外チェック
# ---------------------------------------------------------------------------

class TestApplyRulesDateRange:
    """日付範囲チェックのテスト。"""

    def test_date_before_min(self) -> None:
        """date_range.min より前の日付で警告が出るか。"""
        rules = Rules(date_range=DateRange(min="2026-02-01"))
        rows = [_row(date="2026-01-15")]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "date_range" for w in warnings)

    def test_date_after_max(self) -> None:
        """date_range.max より後の日付で警告が出るか。"""
        rules = Rules(date_range=DateRange(max="2026-06-30"))
        rows = [_row(date="2026-07-01")]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "date_range" for w in warnings)

    def test_date_in_range_no_warning(self) -> None:
        """範囲内の日付なら警告なしか。"""
        rules = Rules(date_range=DateRange(min="2026-01-01", max="2026-12-31"))
        rows = [_row(date="2026-06-15")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0

    def test_invalid_date_range_value_skips_check(self) -> None:
        """rules.json の日付が不正（"bad-date"）でも、その条件をスキップしてクラッシュしないか。"""
        rules = Rules(date_range=DateRange(min="bad-date", max="2026-12-31"))
        rows = [_row(date="2025-01-01")]
        _, warnings = apply_rules(rows, rules)
        # 設定値が壊れていても、アプリ全体が止まるより
        # その条件だけ無視して続行できたほうが実運用では安全。
        assert not any(w["message"].startswith("日付が範囲外（min=") for w in warnings)


# ---------------------------------------------------------------------------
# apply_rules のテスト: 金額上限
# テーマ: 日次・月次の合計金額が上限を超えたら警告
# ---------------------------------------------------------------------------

class TestApplyRulesLimits:
    """金額上限チェックのテスト。

    上限チェックは全行の集計後に行うため、
    テストデータも合計値が上限を超えるように組み立てる。
    """

    def test_daily_total_exceeded(self) -> None:
        """同日の合計が daily_total を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(daily_total=5000))
        rows = [
            _row(date="2026-01-10", amount=3000, row="2"),
            _row(date="2026-01-10", amount=3000, row="3"),  # 合計 6000 > 5000
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_daily_total" for w in warnings)

    def test_daily_total_within_limit(self) -> None:
        """日次合計が上限以内なら警告なしか。"""
        rules = Rules(limits=Limits(daily_total=10000))
        rows = [_row(date="2026-01-10", amount=3000)]
        _, warnings = apply_rules(rows, rules)
        assert not any(w["kind"] == "limit_daily_total" for w in warnings)

    def test_monthly_total_exceeded(self) -> None:
        """同月の合計が monthly_total を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(monthly_total=5000))
        rows = [
            _row(date="2026-01-10", amount=3000, row="2"),
            _row(date="2026-01-20", amount=3000, row="3"),  # 合計 6000 > 5000
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_monthly_total" for w in warnings)

    def test_category_daily_exceeded(self) -> None:
        """特定カテゴリの日次合計が上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(category_daily={"交通費": 2000}))
        rows = [
            _row(date="2026-01-10", amount=1500, category="交通費", row="2"),
            _row(date="2026-01-10", amount=1500, category="交通費", row="3"),  # 合計 3000 > 2000
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_category_daily" for w in warnings)

    def test_category_monthly_exceeded(self) -> None:
        """特定カテゴリの月次合計が上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(category_monthly={"交際費": 3000}))
        rows = [
            _row(date="2026-01-10", amount=2000, category="交際費", row="2"),
            _row(date="2026-01-20", amount=2000, category="交際費", row="3"),  # 合計 4000 > 3000
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_category_monthly" for w in warnings)
