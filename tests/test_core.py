# -*- coding: utf-8 -*-
"""
tests/test_core.py — expense_core.py の単体テスト
pytest で実行する。各関数が「正常値・異常値」を正しく判定するかを確認する。
テスト自体が「この関数をどう使うか」の短い例にもなっている。
"""

from expense_core import check_rows, make_summary, normalize_ok_rows, parse_amount, parse_date


def test_parse_date() -> None:
    """parse_date() が YYYY-MM-DD だけ True を返すか確認する。"""
    assert parse_date("2026-01-10") is True
    assert parse_date("2026/01/10") is False  # スラッシュ区切りは不正
    assert parse_date("") is False            # 空文字は不正


def test_parse_amount() -> None:
    """parse_amount() が整数文字列だけ True を返すか確認する。"""
    assert parse_amount("1200") is True
    assert parse_amount("12.5") is False  # 小数は不正
    assert parse_amount("abc") is False   # 数字以外は不正


def test_check_rows_and_summary() -> None:
    """check_rows() が OK 行とエラー行に正しく振り分け、集計できるか確認する。"""
    rows = [
        {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "消耗品"},
        {
            "date": "2026/01/10",
            "amount": "500",
            "merchant": "B",
            "category": "消耗品",
        },  # 日付が不正
    ]
    ok, errors = check_rows(rows)
    assert len(ok) == 1      # 正常行は 1 件
    assert len(errors) == 1  # エラー行は 1 件

    ok_norm = normalize_ok_rows(ok)
    summary = make_summary(ok_norm, top_n=10)
    # month_total の行が 1 件以上含まれているか（集計が動いているか）
    assert any(r["type"] == "month_total" for r in summary)
