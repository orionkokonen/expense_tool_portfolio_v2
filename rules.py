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
    """rules.json を読み込み、Rules データクラスに変換して返す。

    不正な値（例: unknown_category_mode に想定外の文字列）が設定されていた場合は、
    エラーを出さずに安全なデフォルト値（"warn"）へフォールバックする。
    これにより、設定ファイルの記述ミスでアプリが止まることを防ぐ。

    frozen=True のデータクラスを使うのは、ルール設定が処理中に
    意図せず変更されないよう不変（immutable）にするため。
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    allowed = data.get("allowed_categories")
    banned = data.get("banned_words")

    # 想定外のモード値はデフォルトの "warn" に正規化する
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
    """rules.json の date_range 値が正しい日付形式かを確認する。

    不正な日付が設定されていた場合、その条件を無視（None 扱い）する。
    これにより、設定ミスで全行が警告になるような誤動作を防ぐ。
    """
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False


def apply_rules(rows: list[dict], rules: Rules) -> tuple[list[dict], list[dict[str, str]]]:
    """正規化済み行に対してビジネスルールを適用し、警告を生成する。

    処理は2段階に分かれている:
      1. 行ごとのチェック（カテゴリ、禁止ワード、日付範囲）
         → 各行を処理しながら日次・月次の累積合計も記録する
      2. 累積合計によるチェック（日次上限・月次上限）
         → 全行を処理してから判定する（行単位では判断できないため）

    clean_rows は「fallback モード時にカテゴリを書き換えた後」のデータを含む。
    上限チェックも書き換え後のカテゴリで行うことで、集計が一貫する。

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

    # 上限チェック用に全行の累積合計を保持する辞書
    by_day_total: dict[str, int] = {}
    by_month_total: dict[str, int] = {}
    by_day_cat: dict[tuple[str, str], int] = {}
    by_month_cat: dict[tuple[str, str], int] = {}

    # rules.json の日付値が不正な場合は None として扱い、その条件をスキップする
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

        # 未登録カテゴリのチェック
        # allowed_categories が空リストの場合はチェックしない（未設定 = 全許可）
        is_unknown = bool(allowed_set) and (category not in allowed_set)
        category_for_clean = category
        category_for_limit = category

        if is_unknown:
            if mode == "ignore":
                # 警告も出さずそのまま通す（ログ不要なケースを想定）
                pass
            elif mode == "fallback":
                # 未知カテゴリを fallback_category に置き換えて集計を続ける
                # 警告は残すことで、後から確認できるようにしている
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

        # 禁止ワードチェック（加盟店名に含まれているか）
        # 最初に一致したワードで break することで、複数ヒットしても警告は1件にとどめる
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

        # 日付範囲チェック: ISO 8601 形式（YYYY-MM-DD）は辞書順 = 時系列順なので
        # 文字列のまま比較できる。datetime への変換コストを省ける。
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

        # fallback 後のカテゴリでクリーン行を生成する
        r2 = dict(r)
        r2["category"] = category_for_clean
        clean_rows.append(r2)

        # 上限チェック用の累積合計を更新する（行ごとに加算）
        by_day_total[date_str] = by_day_total.get(date_str, 0) + amount
        by_month_total[month] = by_month_total.get(month, 0) + amount
        by_day_cat[(date_str, category_for_limit)] = (
            by_day_cat.get((date_str, category_for_limit), 0) + amount
        )
        by_month_cat[(month, category_for_limit)] = (
            by_month_cat.get((month, category_for_limit), 0) + amount
        )

    lim = rules.limits

    # 上限チェックは全行の集計が完了してから行う（途中判定では合計が確定しないため）

    # 日次合計の上限チェック
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

    # 月次合計の上限チェック
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

    # カテゴリ別日次上限チェック（カテゴリごとに別の上限を設定できる）
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

    # カテゴリ別月次上限チェック
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
