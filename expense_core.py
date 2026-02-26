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
    """CSVを読み込んで辞書のリストとして返す。

    DictReader を使うことで列名をキーとした辞書形式になり、
    後工程でのフィールドアクセスが安全になる。
    encoding="utf-8" を明示するのは、環境依存の文字化けを防ぐため。
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSVの列名が読めませんでした")
        return list(reader)  # DictReader は値を str で返す（空欄なら ""）


def parse_date(s: str) -> bool:
    """日付文字列が YYYY-MM-DD 形式かどうかを検証する。

    strptime で厳密にパースすることで "2024-13-01" や "20240101" のような
    見た目は近いが不正な値を確実に弾く。
    """
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_amount(s: str) -> bool:
    """金額文字列が整数として解釈できるかを検証する。

    float を許容すると "1.5" などが通ってしまい後工程の集計がずれるため、
    int に限定している。
    """
    try:
        int(s)
        return True
    except ValueError:
        return False


def check_rows(rows: list[dict[str, str]]) -> tuple[list[ExpenseRow], list[IssueRow]]:
    """
    全行に対して基本バリデーションを行い、OK行とエラー行に振り分ける。

    バリデーション項目:
      - 必須列の存在・空欄チェック
      - 日付フォーマット（YYYY-MM-DD）
      - 金額が整数か
      - date + amount + merchant の組み合わせによる重複検出

    エラーがあった行は errors に、問題なければ ok_rows に追加する。
    「エラーがある行は後工程から除外する」設計にすることで、
    ルールチェックや集計が常に正常データだけを扱える。

    returns:
      ok_rows: 基本チェックに通った行（row番号つき）
      errors:  問題ある行（理由付き）
    """
    errors: list[IssueRow] = []
    ok_rows: list[ExpenseRow] = []

    # set を使って O(1) で重複を検出する。行数が多くても処理が遅くならない。
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

        # 重複チェック: merchant を小文字に正規化することで大文字・小文字の表記揺れを吸収する
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
    """バリデーション済み行の型を確定させる（str → int など）。

    check_rows の段階では全フィールドを str のまま保持する。
    型変換は「正常と確定した後」に行うことで、変換エラーが起きにくい設計にしている。
    責務を「検証」と「型変換」で分離することで、テストもしやすくなる。
    """
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
    """正常行をもとに複数軸の集計を行い、フラットなリストとして返す。

    集計軸: 月別合計 / カテゴリ別合計 / 上位N加盟店 / 曜日別合計 / 基本統計

    戻り値を {"type", "key", "value"} のフラット構造にしているのは、
    CSV や Excel への出力時に形式を統一しやすくするため。
    defaultdict(int) を使うことで、初出のキーに 0 を自動セットできる。
    """
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

        # 日付の先頭7文字（YYYY-MM）で月を取得。strptime より高速。
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

    # 上位N件に絞ることで、加盟店数が多くてもレポートが肥大化しない
    summary.append({"type": "merchant_top", "key": f"top_{top_n}", "value": "total_amount"})
    merchants_sorted = sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:top_n]
    for name, total in merchants_sorted:
        summary.append({"type": "merchant_top", "key": name, "value": str(total)})

    # 曜日を月〜日の順に固定する（辞書のキー順は挿入順なので明示的に並べる）
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
    """辞書のリストを CSV に書き出す。

    extrasaction="ignore" を指定することで、辞書に余分なキーがあっても
    エラーにならず、fieldnames に指定した列だけを出力できる。
    newline="" を明示するのは、Windows 環境での改行コード二重挿入を防ぐため。
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
