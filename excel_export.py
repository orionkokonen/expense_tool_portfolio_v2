# -*- coding: utf-8 -*-
"""
excel_export.py
Excel（.xlsx）を生成する
シート: Errors / Warnings / Summary / Clean / Charts
見栄え: フィルタ / 列幅調整 / ヘッダ太字 / フリーズ
グラフ: 月別推移(棒) / カテゴリ比率(円)
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


def write_xlsx_report(
    *,
    path: Path,
    errors: list[dict],
    warnings: list[dict],
    clean: list[dict],
    summary: list[dict],
) -> None:
    """Excelレポートを生成して指定パスに保存する。

    シート構成:
      - Errors   : バリデーションエラー行
      - Warnings : ビジネスルール違反行
      - Clean    : 問題なしのクリーン行
      - Summary  : 集計結果
      - Charts   : グラフ（月別・カテゴリ別）

    出力先ディレクトリが存在しない場合は自動生成する。
    Render のような環境ではデプロイ時にディレクトリが存在しない場合があるため、
    mkdir を明示的に呼んでいる。
    """
    wb = Workbook()

    # Workbook 作成時に自動生成されるデフォルトシートは不要なので削除する
    # これをやらないと意図しない空シートが先頭に残ってしまう
    default = wb.active
    wb.remove(default)

    _add_table_sheet(
        wb, "Errors", errors, ["row", "date", "amount", "merchant", "category", "reason"]
    )
    _add_table_sheet(
        wb,
        "Warnings",
        warnings,
        ["kind", "row", "date", "month", "category", "merchant", "amount", "message"],
    )
    _add_table_sheet(wb, "Clean", clean, ["date", "amount", "merchant", "category"])
    _add_table_sheet(wb, "Summary", summary, ["type", "key", "value"])

    charts_ws = wb.create_sheet("Charts")
    _build_charts(charts_ws, summary)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _add_table_sheet(wb: Workbook, title: str, rows: list[dict], columns: list[str]) -> None:
    """データをテーブル形式でシートに書き込む。

    ヘッダを太字にし、先頭行をフリーズ、オートフィルタを設定することで
    Excelで開いたときに操作しやすいレイアウトにしている。
    列幅は内容に応じて自動調整する（_auto_width）。
    """
    ws = wb.create_sheet(title)

    # header
    ws.append(columns)
    header_font = Font(bold=True)
    for col_idx in range(1, len(columns) + 1):
        c = ws.cell(row=1, column=col_idx)
        c.font = header_font
        c.alignment = Alignment(vertical="center")

    # rows
    for r in rows:
        ws.append([r.get(c, "") for c in columns])

    # 先頭行を固定し、フィルタを有効にする（データ量が多い場合の操作性向上）
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(1, ws.max_row)}"

    _auto_width(ws, max_width=50)


def _auto_width(ws, max_width: int = 60) -> None:
    """各列の最大文字数に応じて列幅を自動調整する。

    openpyxl はデフォルトで列幅を自動調整しないため、
    手動でセル内容の最大文字数を計算して適用する。
    max_width で上限を設けることで、長い文字列による列の過剰な広がりを防ぐ。
    """
    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        # 各列の最大文字数（ざっくり）
        max_len = 0
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=col_idx).value
            if v is None:
                continue
            s = str(v)
            if len(s) > max_len:
                max_len = len(s)
        ws.column_dimensions[letter].width = min(max_len + 2, max_width)


def _build_charts(ws, summary: list[dict]) -> None:
    """
    Chartsシートに
    - 月別合計テーブル + 棒グラフ
    - カテゴリ合計テーブル + 円グラフ
    を作る

    summary リストからグラフ用データ（月別・カテゴリ別）を抽出してテーブルを組み立て、
    openpyxl の Reference でグラフのデータ範囲を指定する。
    テーブルをシートに書き込んでからそれを参照する構造にすることで、
    グラフデータが Excel 上でも確認・編集しやすい状態になる。
    """
    ws["A1"] = "Month totals"
    ws["A1"].font = Font(bold=True)

    # summary はフラット構造なので type でフィルタしてグラフ用データを取り出す
    month_rows = [
        (r["key"], int(r["value"]))
        for r in summary
        if r.get("type") == "month_total" and r.get("key") not in ("month",)
    ]
    cat_rows = [
        (r["key"], int(r["value"]))
        for r in summary
        if r.get("type") == "category_total" and r.get("key") not in ("category",)
    ]

    # 月別表（A3:B...）
    ws.append([])  # A2 empty
    ws.append(["month", "total_amount"])  # row3
    for m, v in month_rows:
        ws.append([m, v])

    month_start = 3
    month_end = 3 + len(month_rows)

    # 棒グラフ（右側）
    if month_rows:
        chart = BarChart()
        chart.title = "Monthly total"
        chart.y_axis.title = "amount"
        chart.x_axis.title = "month"
        data = Reference(ws, min_col=2, min_row=month_start, max_row=month_end)
        cats = Reference(ws, min_col=1, min_row=month_start + 1, max_row=month_end)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showVal = False
        ws.add_chart(chart, "D3")

    # カテゴリ表（月別表の直下に配置）
    row0 = month_end + 3
    ws[f"A{row0}"] = "Category totals"
    ws[f"A{row0}"].font = Font(bold=True)

    ws.append([])  # blank
    ws.append(["category", "total_amount"])
    for c, v in cat_rows:
        ws.append([c, v])

    cat_header_row = row0 + 2
    cat_start = cat_header_row
    cat_end = cat_header_row + len(cat_rows)

    if cat_rows:
        pie = PieChart()
        pie.title = "Category ratio"
        data = Reference(ws, min_col=2, min_row=cat_start, max_row=cat_end)
        labels = Reference(ws, min_col=1, min_row=cat_start + 1, max_row=cat_end)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        ws.add_chart(pie, f"D{cat_start}")
