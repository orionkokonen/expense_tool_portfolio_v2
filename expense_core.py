# -*- coding: utf-8 -*-
"""
expense_core.py — データ処理の中心部
CSV 読み込み / 基本入力チェック / 型変換 / 集計 / CSV 書き出しを担う。
社内ルールのチェックは rules.py 側が行う。
「まず入力として正しいか」をここで固めることで、後続処理を単純にしている。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from statistics import mean, median
from typing import TypedDict

# この 4 列がそろっていることを処理の前提にする。
REQUIRED_COLUMNS = ["date", "amount", "merchant", "category"]


# --- 型定義（TypedDict = 辞書のキーと型を明示するための仕組み）---

class ExpenseRow(TypedDict):
    """入力チェック後の行（amount はまだ文字列）。"""
    row: str
    date: str
    amount: str
    merchant: str
    category: str


class ExpenseRowNorm(TypedDict):
    """型変換後の行（amount が整数になっている）。"""
    row: str
    date: str
    amount: int
    merchant: str
    category: str


class IssueRow(TypedDict):
    """エラー行（reason に問題の説明を付ける）。"""
    row: str
    date: str
    amount: str
    merchant: str
    category: str
    reason: str


class WarningRow(TypedDict):
    """ルール違反の警告 1 件。

    形式は通っているので、警告があっても clean_rows に残る場合がある。
    """
    kind: str
    row: str
    date: str
    month: str
    category: str
    merchant: str
    amount: str
    message: str


class SummaryRow(TypedDict):
    """集計結果の共通 1 行。

    `type` で表の種類を見分けることで、CSV / Excel / HTML で同じ形を使い回せる。
    """
    type: str
    key: str
    value: str


def read_csv(path: str) -> list[dict[str, str]]:
    """CSV を読み込んで「列名 → 値」の辞書リストとして返す。

    encoding="utf-8" を明示するのは、環境によって文字化けするのを防ぐため。
    空のファイルや列名がない場合は ValueError を出して呼び出し元に知らせる。
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSVの列名が読めませんでした")
        return list(reader)  # 値はすべて str（空欄なら ""）


def parse_date(s: str) -> bool:
    """日付文字列が YYYY-MM-DD 形式かどうかを確認する。

    strptime で厳密にパースするので "2024-13-01"（月が13）や
    "20240101"（区切りなし）のような不正な値も確実に弾ける。
    """
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_amount(s: str) -> bool:
    """金額文字列が整数として解釈できるかを確認する。

    "1.5" のような小数を許容すると集計がずれるため、整数のみ OK にしている。
    """
    try:
        int(s)
        return True
    except ValueError:
        return False


def check_rows(rows: list[dict[str, str]]) -> tuple[list[ExpenseRow], list[IssueRow]]:
    """全行に対して基本入力チェックを行い、OK 行とエラー行に振り分ける。

    チェック項目:
      - 必須列の存在・空欄チェック
      - 日付フォーマット（YYYY-MM-DD）
      - 金額が整数か
      - date + amount + merchant の組み合わせによる重複検出

    エラーがあった行は後工程から除外することで、
    ルールチェックや集計が常に正常データだけを扱えるようになる。

    戻り値:
      ok_rows — チェックを通った行（行番号つき）
      errors  — 問題のある行（理由つき）
    """
    errors: list[IssueRow] = []
    ok_rows: list[ExpenseRow] = []

    # set（集合）で重複を管理する。辞書と違い「存在するかどうか」だけを O(1) で確認できる。
    seen: set[tuple[str, str, str]] = set()  # (date, amount, merchant_lower)

    for idx, r in enumerate(rows, start=2):  # CSV の 1 行目はヘッダなので 2 行目から数える
        reasons: list[str] = []

        # 必須列チェック（空欄・空白だけもNG）
        for col in REQUIRED_COLUMNS:
            if col not in r:
                reasons.append(f"列がない: {col}")
                continue
            # r.get(col, "") は「キーがなければ空文字を返す」という書き方。
            # r.get(col) or "" と書く方法もあるが、値が 0 や False のとき
            # 意図せず空文字に置き換わるバグになるので、第2引数で指定する方が安全。
            text = r.get(col, "")
            if text.strip() == "":
                reasons.append(f"空欄: {col}")

        # 日付チェック（空欄は上で検出済み。ここは「空欄ではないが形式が違う」ケース）
        d = r.get("date", "").strip()
        if d and not parse_date(d):
            reasons.append("日付の形式が違う（YYYY-MM-DD）")

        # 金額チェック
        a = r.get("amount", "").strip()
        if a and not parse_amount(a):
            reasons.append("金額が数字じゃない")

        # 重複チェック: merchant を小文字に統一して大文字・小文字の表記揺れを吸収する
        date_k = r.get("date", "").strip()
        amount_k = r.get("amount", "").strip()
        merchant_k = r.get("merchant", "").strip().lower()

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
    """入力チェック済み行の型を確定させる（文字列 → 整数など）。

    check_rows では全フィールドを文字列のまま保持している。
    「正常と確定した後」に型変換することで、変換エラーが起きにくい設計になっている。
    """
    out: list[ExpenseRowNorm] = []
    for r in ok_rows:
        # ここで int 化しておくと、後続の集計では金額をそのまま足し算できる。
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


def make_summary(ok_rows: list[ExpenseRowNorm], top_n: int = 10) -> list[SummaryRow]:
    """正常行をもとに複数軸の集計を行い、フラットなリストとして返す。

    集計軸: 月別合計 / カテゴリ別合計 / 上位N加盟店 / 曜日別合計 / 基本統計

    戻り値を {"type", "key", "value"} のフラット構造にしているのは、
    CSV や Excel への書き出し形式を統一しやすくするため。
    defaultdict(int) は「まだないキーを参照したとき 0 を返す辞書」。
    """
    by_month: defaultdict[str, int] = defaultdict(int)
    by_category: defaultdict[str, int] = defaultdict(int)
    by_merchant: defaultdict[str, int] = defaultdict(int)
    by_weekday: defaultdict[str, int] = defaultdict(int)

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

    summary: list[SummaryRow] = []

    # 先頭にヘッダ行を入れておくと、summary.csv を単体で開いたときにも意味が伝わりやすい。
    summary.append({"type": "month_total", "key": "month", "value": "total_amount"})
    for m in sorted(by_month.keys()):
        summary.append({"type": "month_total", "key": m, "value": str(by_month[m])})

    summary.append({"type": "category_total", "key": "category", "value": "total_amount"})
    for c in sorted(by_category.keys()):
        summary.append({"type": "category_total", "key": c, "value": str(by_category[c])})

    # 上位 N 件に絞ることで、加盟店数が多くてもレポートが肥大化しない
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


def write_csv(path: str, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    """辞書のリストを CSV に書き出す。

    extrasaction="ignore" により、辞書に余分なキーがあっても無視して
    fieldnames で指定した列だけを出力できる。
    newline="" を明示するのは、Windows 環境で改行コードが二重に挿入されるのを防ぐため。
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
