# -*- coding: utf-8 -*-
"""
html_report.py — HTML レポートの生成
errors / warnings / clean をテーブルで表示し、
月別・カテゴリ別のグラフを Chart.js（CDN）で描画する。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

from expense_core import SummaryRow


def write_html_report(
    *,
    path: Path,
    errors: Sequence[Mapping[str, object]],
    warnings: Sequence[Mapping[str, object]],
    clean: Sequence[Mapping[str, object]],
    summary: Sequence[SummaryRow],
    title: str = "Expense Tool Report",
) -> None:
    """HTML 形式のレポートファイルを生成して保存する。

    グラフは Chart.js（CDN）を使うことで、Matplotlib などのライブラリなしに
    ブラウザ上でグラフを表示できる。

    集計データを json.dumps() で JavaScript 変数に埋め込む設計なので、
    1 つの HTML ファイルだけで完結する（サーバーへの追加リクエスト不要）。

    セキュリティ: CSV の内容をそのまま HTML に出力すると "<script>" などが
    実行されてしまう（XSS）ので、escape() で必ず無害化してから埋め込む。
    """
    # summary のフラットリストから月別・カテゴリ別のデータを取り出す
    month_rows = [
        (r["key"], int(r["value"]))
        for r in summary
        if r["type"] == "month_total" and r["key"] != "month"
    ]
    cat_rows = [
        (r["key"], int(r["value"]))
        for r in summary
        if r["type"] == "category_total" and r["key"] != "category"
    ]

    month_labels = [m for m, _ in month_rows]
    month_values = [v for _, v in month_rows]
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [v for _, v in cat_rows]

    # HTML が重くなりすぎないよう先頭 200 件に制限する。
    # 全データは CSV ダウンロードから参照できる。
    errors_head = errors[:200]
    warnings_head = warnings[:200]
    clean_head = clean[:200]

    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    margin: 24px; line-height: 1.5; }}
    h1 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    @media (min-width: 900px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #eee; padding: 6px 8px; font-size: 14px; }}
    th {{ background: #f7f7f7; text-align: left; }}
    .muted {{ color: #666; font-size: 13px; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p class="muted">errors: {len(errors)} / warnings: {len(warnings)} / clean_rows: {len(clean)}</p>

  <div class="grid">
    <div class="card">
      <h2>Monthly total</h2>
      <canvas id="chartMonth"></canvas>
    </div>
    <div class="card">
      <h2>Category ratio</h2>
      <canvas id="chartCat"></canvas>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Errors（先頭200件）</h2>
    {table_html(errors_head, ["row", "date", "amount", "merchant", "category", "reason"])}
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Warnings（先頭200件）</h2>
    {table_html(warnings_head, ["kind", "row", "date", "month", "category", "merchant", "amount",
                                "message"])}
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Clean（先頭200件）</h2>
    {table_html(clean_head, ["date", "amount", "merchant", "category"])}
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    // Python 側で json.dumps() したデータを JavaScript 変数として埋め込む。
    // サーバーへの追加リクエストなしにグラフを描画できる。
    const monthLabels = {json.dumps(month_labels)};
    const monthValues = {json.dumps(month_values)};
    const catLabels = {json.dumps(cat_labels)};
    const catValues = {json.dumps(cat_values)};

    const ctxM = document.getElementById('chartMonth');
    new Chart(ctxM, {{
      type: 'bar',
      data: {{
        labels: monthLabels,
        datasets: [{{ label: 'total', data: monthValues }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: true }}
        }}
      }}
    }});

    const ctxC = document.getElementById('chartCat');
    new Chart(ctxC, {{
      type: 'pie',
      data: {{
        labels: catLabels,
        datasets: [{{ data: catValues }}]
      }},
      options: {{
        responsive: true
      }}
    }});
  </script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def table_html(rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> str:
    """辞書のリストを HTML テーブルに変換する。

    セル値に escape() を適用することで XSS（クロスサイトスクリプティング）を防ぐ。
    CSV の内容に "<script>" のような文字列が含まれていても HTML として実行されない。
    """
    if not rows:
        return "<p class='muted'>（なし）</p>"

    ths = "".join(f"<th>{escape(c)}</th>" for c in columns)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{escape(str(r.get(c, '')))}</td>" for c in columns)
        trs.append(f"<tr>{tds}</tr>")

    return f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
