# -*- coding: utf-8 -*-

from expense_core import check_rows, make_summary, normalize_ok_rows, parse_amount, parse_date

#parse_date() が YYYY-MM-DD だけ True になるか

def test_parse_date():
    assert parse_date("2026-01-10") is True
    assert parse_date("2026/01/10") is False
    assert parse_date("") is False

#parse_amount() が整数文字列だけ True になるか

def test_parse_amount():
    assert parse_amount("1200") is True
    assert parse_amount("12.5") is False
    assert parse_amount("abc") is False

#check_rows() が「OK行とエラー行」に分けられるか

def test_check_rows_and_summary():
    rows = [
        {"date": "2026-01-10", "amount": "1200", "merchant": "A", "category": "消耗品"},
        {"date": "2026/01/10", "amount": "500", "merchant": "B", "category": "消耗品"},
    ]
    ok, errors = check_rows(rows)
    assert len(ok) == 1
    assert len(errors) == 1

    ok_norm = normalize_ok_rows(ok)
    summary = make_summary(ok_norm, top_n=10)
    # month_total のヘッダ + 1行以上
    assert any(r["type"] == "month_total" for r in summary)
