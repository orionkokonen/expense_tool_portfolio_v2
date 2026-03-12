# -*- coding: utf-8 -*-
"""
rules.py — 社内ルールの読み込みと適用
rules.json を読み込み、入力チェック済みの行に対して「社内ルール違反」を検出する。
違反は warnings として返し、clean_rows にはカテゴリ書き換え後のデータを入れる。
「止めるべき問題」と「人が確認する問題」を分けるため、ここは警告中心の設計になっている。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from expense_core import ExpenseRowNorm, WarningRow

# --- データクラス（設定値をまとめて管理する構造体）---
# frozen=True にすることで処理中に値が書き換えられないよう「読み取り専用」にしている

@dataclass(frozen=True)
class DateRange:
    """日付の有効範囲（rules.json の date_range に対応）。"""
    min: str | None = None  # "YYYY-MM-DD"
    max: str | None = None  # "YYYY-MM-DD"


@dataclass(frozen=True)
class Limits:
    """金額の上限設定（rules.json の limits に対応）。"""
    daily_total: int | None = None
    monthly_total: int | None = None
    category_daily: dict[str, int] | None = None
    category_monthly: dict[str, int] | None = None


@dataclass(frozen=True)
class Rules:
    """rules.json の全設定をまとめたデータクラス。"""
    allowed_categories: list[str] | None = None
    unknown_category_mode: str = "warn"  # "warn" | "ignore" | "fallback"
    fallback_category: str | None = None
    banned_words: list[str] | None = None
    date_range: DateRange = DateRange()
    limits: Limits = Limits()


def load_rules(path: Path) -> Rules:
    """rules.json を読み込み、Rules データクラスに変換して返す。

    unknown_category_mode に想定外の値が入っていた場合は "warn" に戻す。
    設定ファイルの記述ミスでアプリが止まらないようにするための安全策。
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

    不正な日付が設定されていた場合はその条件をスキップする（None 扱い）。
    設定ミスで全行が警告になるような誤動作を防ぐ。
    """
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False


def apply_rules(
    rows: list[ExpenseRowNorm], rules: Rules
) -> tuple[list[ExpenseRowNorm], list[WarningRow]]:
    """正規化済み行に対して社内ルールを適用し、警告を生成する。

    処理は2段階:
      1. 行ごとのチェック（カテゴリ・禁止ワード・日付範囲）
         → 各行を処理しながら日次・月次の累積合計も記録する
      2. 全行集計後の上限チェック（日次・月次の合計上限）
         → 全行を処理してから判定する（途中では合計が確定しないため）

    戻り値:
      clean_rows — fallback モード時はカテゴリを書き換えたデータ
      warnings   — 違反内容の一覧
    """
    warnings: list[WarningRow] = []
    clean_rows: list[ExpenseRowNorm] = []

    # list のままだと毎回順番に探すので、集合(set)にして判定を速くする。
    allowed_set = set(rules.allowed_categories or [])
    banned_words = rules.banned_words or []

    mode = rules.unknown_category_mode
    # fallback_category が未設定でも処理が止まらないよう、最後の受け皿を決めておく。
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
        # allowed_categories が空リストの場合はチェックしない（未設定 = 全カテゴリ許可）
        is_unknown = bool(allowed_set) and (category not in allowed_set)
        category_for_clean = category
        category_for_limit = category

        if is_unknown:
            if mode == "ignore":
                # 警告も出さずそのまま通す
                pass
            elif mode == "fallback":
                # 未知カテゴリを fallback_category に置き換えて集計を続ける。
                # 警告は残すことで、後から確認できるようにしている。
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

        # 日付範囲チェック: YYYY-MM-DD 形式は文字列のまま辞書順で比較できる
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
        r2: ExpenseRowNorm = {
            "row": row_id,
            "date": date_str,
            "amount": amount,
            "merchant": merchant,
            "category": category_for_clean,
        }
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

    # 以下の上限チェックは全行の集計が完了してから行う（途中では合計が確定しないため）

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
