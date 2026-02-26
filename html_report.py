# -*- coding: utf-8 -*-
"""
html_report.py
HTMLレポートを生成する
- errors / warnings を表にする
- month / category のグラフ（Chart.js CDN）を表示
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path


def write_html_report(
    *,
    path: Path,
    errors: list[dict],
    warnings: list[dict],
    clean: list[dict],
    summary: list[dict],
    title: str = "Expense Tool Report",
) -> None:
    """HTML形式のレポートファイルを生成して保存する。

    グラフは Chart.js（CDN）を使い、サーバーサイドでの画像生成を不要にしている。
    これにより、Matplotlib などの依存を増やさずに視覚的なレポートを実現できる。

    Python 側で集計データを json.dumps() して JavaScript 変数に埋め込む設計にすることで、
    サーバーとクライアントの間でデータを再送する必要がなく、単一のHTMLファイルとして完結する。

    XSS 対策として、ユーザーデータをHTMLに埋め込む箇所では必ず escape() を使用する。
    """
    # summary リストから月別・カテゴリ別のデータを取り出してグラフ用に整形する
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

    month_labels = [m for m, _ in month_rows]
    month_values = [v for _, v in month_rows]
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [v for _, v in cat_rows]

    # データ量が多いとHTMLが重くなるため先頭200件に制限する
    # 完全なデータは CSV ダウンロードから参照できる設計になっている
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
    // Python側で json.dumps() したデータをそのままJavaScript変数として埋め込む。
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


def table_html(rows: list[dict], columns: list[str]) -> str:
    """辞書のリストをHTML表に変換する。

    セル値には必ず escape() を適用する。
    CSVの内容に "<script>" のような文字列が含まれていた場合に
    HTML として解釈されてしまう XSS を防ぐため。
    """
    if not rows:
        return "<p class='muted'>（なし）</p>"

    ths = "".join(f"<th>{escape(c)}</th>" for c in columns)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{escape(str(r.get(c, '')))}</td>" for c in columns)
        trs.append(f"<tr>{tds}</tr>")

    return f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
