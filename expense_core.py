# -*- coding: utf-8 -*-
"""
expense_core.py
CSV読み込み / 基本チェック(errors) / 集計 / CSV出力
（ルールチェックは rules.py 側でやる）
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import TypedDict

REQUIRED_COLUMNS = ["date", "amount", "merchant", "category"]


class ExpenseRow(TypedDict):
    row: str
    date: str
    amount: str
    merchant: str
    category: str


class ExpenseRowNorm(TypedDict):
    row: str
    date: str
    amount: int
    merchant: str
    category: str


class IssueRow(TypedDict):
    row: str
    date: str
    amount: str
    merchant: str
    category: str
    reason: str


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSVの列名が読めませんでした")
        return list(reader)  # DictReader は値を str で返す（空欄なら ""）


def parse_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_amount(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False


def check_rows(rows: list[dict[str, str]]) -> tuple[list[ExpenseRow], list[IssueRow]]:
    """
    returns:
      ok_rows: 基本チェックに通った行（row番号つき）
      errors:  問題ある行（理由付き）
    """
    errors: list[IssueRow] = []
    ok_rows: list[ExpenseRow] = []

    seen: set[tuple[str, str, str]] = set()  # (date, amount, merchant_lower)

    for idx, r in enumerate(rows, start=2):  # CSVは1行目がヘッダなので2行目から
        reasons: list[str] = []

        # 必須列チェック（空欄/空白だけもNG）
        for col in REQUIRED_COLUMNS:
            if col not in r:
                reasons.append(f"列がない: {col}")
                continue
            text = r.get(col) or ""
            if text.strip() == "":
                reasons.append(f"空欄: {col}")

        # 日付チェック（空欄は上で捕まるので、ここは「空欄じゃないのに形式違い」）
        d = (r.get("date") or "").strip()
        if d and not parse_date(d):
            reasons.append("日付の形式が違う（YYYY-MM-DD）")

        # 金額チェック
        a = (r.get("amount") or "").strip()
        if a and not parse_amount(a):
            reasons.append("金額が数字じゃない")

        # 重複チェック（最低限）
        date_k = (r.get("date") or "").strip()
        amount_k = (r.get("amount") or "").strip()
        merchant_k = (r.get("merchant") or "").strip().lower()

        if date_k and amount_k and merchant_k:
            key = (date_k, amount_k, merchant_k)
            if key in seen:
                reasons.append("重複している（date+amount+merchantが同じ）")
            else:
                seen.add(key)

        if reasons:
            errors.append(
                {
                    "row": str(idx),
                    "date": r.get("date", ""),
                    "amount": r.get("amount", ""),
                    "merchant": r.get("merchant", ""),
                    "category": r.get("category", ""),
                    "reason": " / ".join(reasons),
                }
            )
        else:
            ok_rows.append(
                {
                    "row": str(idx),
                    "date": r.get("date", "").strip(),
                    "amount": r.get("amount", "").strip(),
                    "merchant": r.get("merchant", "").strip(),
                    "category": r.get("category", "").strip(),
                }
            )

    return ok_rows, errors


def normalize_ok_rows(ok_rows: list[ExpenseRow]) -> list[ExpenseRowNorm]:
    out: list[ExpenseRowNorm] = []
    for r in ok_rows:
        out.append(
            {
                "row": r["row"],
                "date": r["date"].strip(),
                "amount": int(r["amount"].strip()),
                "merchant": r["merchant"].strip(),
                "category": r["category"].strip(),
            }
        )
    return out


def make_summary(ok_rows: list[ExpenseRowNorm], top_n: int = 10) -> list[dict[str, str]]:
    by_month = defaultdict(int)
    by_category = defaultdict(int)
    by_merchant = defaultdict(int)
    by_weekday = defaultdict(int)

    amounts: list[int] = []

    for r in ok_rows:
        date_str = r["date"]
        amount = r["amount"]
        merchant = r["merchant"]
        cat = r["category"]

        month = date_str[:7]
        wd = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")  # Mon/Tue...

        by_month[month] += amount
        by_category[cat] += amount
        by_merchant[merchant] += amount
        by_weekday[wd] += amount
        amounts.append(amount)

    summary: list[dict[str, str]] = []

    summary.append({"type": "month_total", "key": "month", "value": "total_amount"})
    for m in sorted(by_month.keys()):
        summary.append({"type": "month_total", "key": m, "value": str(by_month[m])})

    summary.append({"type": "category_total", "key": "category", "value": "total_amount"})
    for c in sorted(by_category.keys()):
        summary.append({"type": "category_total", "key": c, "value": str(by_category[c])})

    summary.append({"type": "merchant_top", "key": f"top_{top_n}", "value": "total_amount"})
    merchants_sorted = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:top_n]
    for name, total in merchants_sorted:
        summary.append({"type": "merchant_top", "key": name, "value": str(total)})

    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    summary.append({"type": "weekday_total", "key": "weekday", "value": "total_amount"})
    for wd in order:
        if wd in by_weekday:
            summary.append({"type": "weekday_total", "key": wd, "value": str(by_weekday[wd])})

    summary.append({"type": "stats", "key": "count", "value": str(len(ok_rows))})
    if amounts:
        summary.append({"type": "stats", "key": "average", "value": str(int(mean(amounts)))})
        summary.append({"type": "stats", "key": "median", "value": str(int(median(amounts)))})
        summary.append({"type": "stats", "key": "min", "value": str(min(amounts))})
        summary.append({"type": "stats", "key": "max", "value": str(max(amounts))})

    return summary


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
