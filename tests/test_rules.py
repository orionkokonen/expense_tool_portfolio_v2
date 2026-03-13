# -*- coding: utf-8 -*-
"""
tests/test_rules.py — rules.py の単体テスト
ルールの読み込みと適用ロジックを検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from expense_core import ExpenseRowNorm
from rules import DateRange, Limits, Rules, apply_rules, load_rules


# ---------------------------------------------------------------------------
# ヘルパー: テスト用の rules.json を一時ファイルに書き出す
# ---------------------------------------------------------------------------

def _write_rules(tmp_path: Path, data: dict) -> Path:
    """テスト用の rules.json を作って Path を返す。"""
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
    """テスト用の正規化済み行を作る。"""
    return {
        "row": row,
        "date": date,
        "amount": amount,
        "merchant": merchant,
        "category": category,
    }


# ---------------------------------------------------------------------------
# load_rules のテスト
# ---------------------------------------------------------------------------

class TestLoadRules:
    """rules.json の読み込みテスト。"""

    def test_load_basic(self, tmp_path: Path) -> None:
        """基本的な rules.json を正しく読み込めるか。"""
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
        """空の JSON（{}）でもデフォルト値で読み込めるか。"""
        rules = load_rules(_write_rules(tmp_path, {}))
        assert rules.allowed_categories is None
        assert rules.unknown_category_mode == "warn"
        assert rules.banned_words is None

    def test_load_invalid_mode_falls_back_to_warn(self, tmp_path: Path) -> None:
        """unknown_category_mode に無効な値が入っていたら warn に戻るか。"""
        data = {"unknown_category_mode": "invalid_mode"}
        rules = load_rules(_write_rules(tmp_path, data))
        assert rules.unknown_category_mode == "warn"

    def test_load_malformed_json_raises(self, tmp_path: Path) -> None:
        """壊れた JSON は json.JSONDecodeError を出すか。"""
        p = tmp_path / "rules.json"
        p.write_text("{broken", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_rules(p)


# ---------------------------------------------------------------------------
# apply_rules のテスト: カテゴリチェック
# ---------------------------------------------------------------------------

class TestApplyRulesCategory:
    """カテゴリ関連のルール適用テスト。"""

    def test_unknown_category_warn(self) -> None:
        """未登録カテゴリで mode=warn のとき警告が出るか。"""
        rules = Rules(allowed_categories=["交通費"], unknown_category_mode="warn")
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 1
        assert warnings[0]["kind"] == "category_unknown"
        # warn モードではカテゴリは書き換えない
        assert clean[0]["category"] == "食費"

    def test_unknown_category_ignore(self) -> None:
        """未登録カテゴリで mode=ignore のとき警告が出ないか。"""
        rules = Rules(allowed_categories=["交通費"], unknown_category_mode="ignore")
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0

    def test_unknown_category_fallback(self) -> None:
        """未登録カテゴリで mode=fallback のとき、カテゴリが書き換わるか。"""
        rules = Rules(
            allowed_categories=["交通費"],
            unknown_category_mode="fallback",
            fallback_category="その他",
        )
        rows = [_row(category="食費")]
        clean, warnings = apply_rules(rows, rules)
        assert len(warnings) == 1
        assert clean[0]["category"] == "その他"

    def test_known_category_no_warning(self) -> None:
        """登録済みカテゴリなら警告が出ないか。"""
        rules = Rules(allowed_categories=["交通費"])
        rows = [_row(category="交通費")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0

    def test_no_allowed_categories_skips_check(self) -> None:
        """allowed_categories が空リストなら全カテゴリ許可か。"""
        rules = Rules(allowed_categories=[])
        rows = [_row(category="なんでも")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# apply_rules のテスト: 禁止ワード
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
        """禁止ワードがなければ警告なしか。"""
        rules = Rules(banned_words=["ギャンブル"])
        rows = [_row(merchant="カフェ")]
        _, warnings = apply_rules(rows, rules)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# apply_rules のテスト: 日付範囲
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
        """不正な日付形式が rules にあっても、その条件をスキップするか。"""
        rules = Rules(date_range=DateRange(min="bad-date", max="2026-12-31"))
        rows = [_row(date="2025-01-01")]
        # min が不正なので min チェックはスキップされ、警告は出ない
        _, warnings = apply_rules(rows, rules)
        assert not any(w["message"].startswith("日付が範囲外（min=") for w in warnings)


# ---------------------------------------------------------------------------
# apply_rules のテスト: 金額上限
# ---------------------------------------------------------------------------

class TestApplyRulesLimits:
    """金額上限チェックのテスト。"""

    def test_daily_total_exceeded(self) -> None:
        """日次合計が上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(daily_total=5000))
        rows = [
            _row(date="2026-01-10", amount=3000, row="2"),
            _row(date="2026-01-10", amount=3000, row="3"),
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
        """月次合計が上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(monthly_total=5000))
        rows = [
            _row(date="2026-01-10", amount=3000, row="2"),
            _row(date="2026-01-20", amount=3000, row="3"),
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_monthly_total" for w in warnings)

    def test_category_daily_exceeded(self) -> None:
        """カテゴリ日次上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(category_daily={"交通費": 2000}))
        rows = [
            _row(date="2026-01-10", amount=1500, category="交通費", row="2"),
            _row(date="2026-01-10", amount=1500, category="交通費", row="3"),
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_category_daily" for w in warnings)

    def test_category_monthly_exceeded(self) -> None:
        """カテゴリ月次上限を超えたら警告が出るか。"""
        rules = Rules(limits=Limits(category_monthly={"交際費": 3000}))
        rows = [
            _row(date="2026-01-10", amount=2000, category="交際費", row="2"),
            _row(date="2026-01-20", amount=2000, category="交際費", row="3"),
        ]
        _, warnings = apply_rules(rows, rules)
        assert any(w["kind"] == "limit_category_monthly" for w in warnings)
