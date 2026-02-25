# -*- coding: utf-8 -*-
"""
rules.py
rules.json を読み込み、正規化済みOK行（normalize_ok_rowsの出力）に対して
「社内ルール違反」を warnings として返す。

apply_rules は (clean_rows, warnings) を返す。
- clean_rows: fallbackモードのときカテゴリを書き換えた版
- warnings: kind,row,date,month,category,merchant,amount,message
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class DateRange:
    min: str | None = None  # "YYYY-MM-DD"
    max: str | None = None  # "YYYY-MM-DD"


@dataclass(frozen=True)
class Limits:
    daily_total: int | None = None
    monthly_total: int | None = None
    category_daily: dict[str, int] | None = None
    category_monthly: dict[str, int] | None = None


@dataclass(frozen=True)
class Rules:
    allowed_categories: list[str] | None = None
    unknown_category_mode: str = "warn"  # "warn" | "ignore" | "fallback"
    fallback_category: str | None = None
    banned_words: list[str] | None = None
    date_range: DateRange = DateRange()
    limits: Limits = Limits()


def load_rules(path: Path) -> Rules:
    data = json.loads(path.read_text(encoding="utf-8"))

    allowed = data.get("allowed_categories")
    banned = data.get("banned_words")

    mode = (data.get("unknown_category_mode") or "warn").lower()
    if mode not in {"warn", "ignore", "fallback"}:
        mode = "warn"

    fallback = data.get("fallback_category")

    dr = data.get("date_range") or {}
    date_range = DateRange(min=dr.get("min"), max=dr.get("max"))

    lim = data.get("limits") or {}
    limits = Limits(
        daily_total=lim.get("daily_total"),
        monthly_total=lim.get("monthly_total"),
        category_daily=lim.get("category_daily"),
        category_monthly=lim.get("category_monthly"),
    )

    return Rules(
        allowed_categories=allowed,
        unknown_category_mode=mode,
        fallback_category=fallback,
        banned_words=banned,
        date_range=date_range,
        limits=limits,
    )


def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False


def apply_rules(rows: list[dict], rules: Rules) -> tuple[list[dict], list[dict[str, str]]]:
    """
    rows: normalize_ok_rows 済み（row:str, date:str, amount:int, merchant:str, category:str）
    returns:
      clean_rows, warnings
    """
    warnings: list[dict[str, str]] = []
    clean_rows: list[dict] = []

    allowed_set = set(rules.allowed_categories or [])
    banned_words = rules.banned_words or []

    mode = rules.unknown_category_mode
    fb = rules.fallback_category or "その他"

    # 上限チェック用の合計
    by_day_total: dict[str, int] = {}
    by_month_total: dict[str, int] = {}
    by_day_cat: dict[tuple[str, str], int] = {}
    by_month_cat: dict[tuple[str, str], int] = {}

    date_min = (
        rules.date_range.min
        if (rules.date_range.min and _valid_date(rules.date_range.min))
        else None
    )
    date_max = (
        rules.date_range.max
        if (rules.date_range.max and _valid_date(rules.date_range.max))
        else None
    )

    for idx, r in enumerate(rows, start=2):
        row_id = str(r.get("row") or idx)
        date_str = r["date"]
        amount = int(r["amount"])
        merchant = r["merchant"]
        category = r["category"]
        month = date_str[:7]

        # 未登録カテゴリ
        is_unknown = bool(allowed_set) and (category not in allowed_set)
        category_for_clean = category
        category_for_limit = category

        if is_unknown:
            if mode == "ignore":
                pass
            elif mode == "fallback":
                warnings.append(
                    {
                        "kind": "category_unknown",
                        "row": row_id,
                        "date": date_str,
                        "month": month,
                        "category": category,
                        "merchant": merchant,
                        "amount": str(amount),
                        "message": f"未登録カテゴリのため {fb} 扱い: {category}",
                    }
                )
                category_for_clean = fb
                category_for_limit = fb
            else:  # warn
                warnings.append(
                    {
                        "kind": "category_unknown",
                        "row": row_id,
                        "date": date_str,
                        "month": month,
                        "category": category,
                        "merchant": merchant,
                        "amount": str(amount),
                        "message": f"未登録カテゴリ: {category}",
                    }
                )

        # 禁止ワード（merchant）
        for w in banned_words:
            if w and (w in merchant):
                warnings.append(
                    {
                        "kind": "banned_word",
                        "row": row_id,
                        "date": date_str,
                        "month": month,
                        "category": category_for_clean,
                        "merchant": merchant,
                        "amount": str(amount),
                        "message": f"禁止ワードを含む: {w}",
                    }
                )
                break

        # 日付範囲（YYYY-MM-DDなので文字比較でOK）
        if date_min and date_str < date_min:
            warnings.append(
                {
                    "kind": "date_range",
                    "row": row_id,
                    "date": date_str,
                    "month": month,
                    "category": category_for_clean,
                    "merchant": merchant,
                    "amount": str(amount),
                    "message": f"日付が範囲外（min={date_min}）",
                }
            )
        if date_max and date_str > date_max:
            warnings.append(
                {
                    "kind": "date_range",
                    "row": row_id,
                    "date": date_str,
                    "month": month,
                    "category": category_for_clean,
                    "merchant": merchant,
                    "amount": str(amount),
                    "message": f"日付が範囲外（max={date_max}）",
                }
            )

        # clean_rows（fallbackモードならカテゴリを書き換えた版が入る）
        r2 = dict(r)
        r2["category"] = category_for_clean
        clean_rows.append(r2)

        # 上限計算
        by_day_total[date_str] = by_day_total.get(date_str, 0) + amount
        by_month_total[month] = by_month_total.get(month, 0) + amount
        by_day_cat[(date_str, category_for_limit)] = (
            by_day_cat.get((date_str, category_for_limit), 0) + amount
        )
        by_month_cat[(month, category_for_limit)] = (
            by_month_cat.get((month, category_for_limit), 0) + amount
        )

    lim = rules.limits

    # 日次合計
    if lim.daily_total is not None:
        for d, total in sorted(by_day_total.items()):
            if total > lim.daily_total:
                warnings.append(
                    {
                        "kind": "limit_daily_total",
                        "row": "",
                        "date": d,
                        "month": d[:7],
                        "category": "",
                        "merchant": "",
                        "amount": str(total),
                        "message": f"日次合計が上限超え: {total} > {lim.daily_total}",
                    }
                )

    # 月次合計
    if lim.monthly_total is not None:
        for m, total in sorted(by_month_total.items()):
            if total > lim.monthly_total:
                warnings.append(
                    {
                        "kind": "limit_monthly_total",
                        "row": "",
                        "date": "",
                        "month": m,
                        "category": "",
                        "merchant": "",
                        "amount": str(total),
                        "message": f"月次合計が上限超え: {total} > {lim.monthly_total}",
                    }
                )

    # カテゴリ日次
    if lim.category_daily:
        for (d, c), total in sorted(by_day_cat.items()):
            limit_val = lim.category_daily.get(c)
            if limit_val is not None and total > limit_val:
                warnings.append(
                    {
                        "kind": "limit_category_daily",
                        "row": "",
                        "date": d,
                        "month": d[:7],
                        "category": c,
                        "merchant": "",
                        "amount": str(total),
                        "message": f"カテゴリ日次合計が上限超え: {c} {total} > {limit_val}",
                    }
                )

    # カテゴリ月次
    if lim.category_monthly:
        for (m, c), total in sorted(by_month_cat.items()):
            limit_val = lim.category_monthly.get(c)
            if limit_val is not None and total > limit_val:
                warnings.append(
                    {
                        "kind": "limit_category_monthly",
                        "row": "",
                        "date": "",
                        "month": m,
                        "category": c,
                        "merchant": "",
                        "amount": str(total),
                        "message": f"カテゴリ月次合計が上限超え: {c} {total} > {limit_val}",
                    }
                )

    return clean_rows, warnings
