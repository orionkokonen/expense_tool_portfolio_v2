# このファイルは、結果を見やすいHTMLレポートに変換する処理です。
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

# ── 定数: テーブルの最大行数 ──
# 数千行を一度にテーブルへ入れるとブラウザが重くなるため、
# 表示は先頭 N 件に限定する。全件は CSV ダウンロードで確認できる。
# 「200」をコード中に直書き（マジックナンバー）すると変更時に探す手間がかかるので、
# 名前付き定数に切り出して一箇所で管理する。
MAX_TABLE_ROWS = 200


def _safe_json_dumps(data: list[str] | list[int]) -> str:
    """Python のリストを、HTML 内の <script> タグに安全に埋め込める JSON 文字列に変換する。

    なぜ必要か:
      json.dumps だけだと、データに "</script>" という文字列が含まれていた場合、
      ブラウザが「ここで script タグが終わった」と誤認し、
      残りの文字列が HTML として実行されてしまう（XSS = クロスサイトスクリプティング攻撃）。

    対策:
      - ensure_ascii=True → 日本語などを \\uXXXX 形式に変換し、HTML 特殊文字を避ける
      - .replace("</", "<\\/") → "</script>" を "<\\/script>" にして、
        ブラウザが script 終了タグと誤認しないようにする
    """
    return json.dumps(data, ensure_ascii=True).replace("</", r"<\/")


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

    # 全件を一気に HTML テーブルへ入れるとブラウザが重くなるため、表示だけ先頭に絞る。
    # 元データは CSV 側で残るので、「読むための画面」と「保存用ファイル」を役割分担している。
    errors_head = errors[:MAX_TABLE_ROWS]
    warnings_head = warnings[:MAX_TABLE_ROWS]
    clean_head = clean[:MAX_TABLE_ROWS]

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
    <h2>Errors（先頭{MAX_TABLE_ROWS}件）</h2>
    {table_html(errors_head, ["row", "date", "amount", "merchant", "category", "reason"])}
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Warnings（先頭{MAX_TABLE_ROWS}件）</h2>
    {table_html(warnings_head, ["kind", "row", "date", "month", "category", "merchant", "amount",
                                "message"])}
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Clean（先頭{MAX_TABLE_ROWS}件）</h2>
    {table_html(clean_head, ["date", "amount", "merchant", "category"])}
  </div>

  <!-- Chart.js を CDN（外部サーバー）から読み込む。
       CDN = Content Delivery Network。ライブラリを自分のサーバーに置かずに済むが、
       ネットワークが使えない環境では読み込めない欠点がある。 -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    // ── CDN フォールバック（読み込み失敗時の代替処理）──
    // オフライン環境や CDN 障害時にグラフが表示できなくても、
    // テーブル部分は問題なく見られるようにメッセージで案内する。
    // typeof で存在チェックすると、未定義でもエラーにならない。
    if (typeof Chart === 'undefined') {{
      document.getElementById('chartMonth').parentElement.innerHTML +=
        '<p style="color:#999">グラフの表示には外部ライブラリ (Chart.js) が必要です。'
        + 'オフライン環境では表示できません。</p>';
      document.getElementById('chartCat').parentElement.innerHTML +=
        '<p style="color:#999">グラフの表示には外部ライブラリ (Chart.js) が必要です。</p>';
    }} else {{
      // ── Python → JavaScript へのデータ受け渡し ──
      // Python の f-string でこの HTML を組み立てるとき、
      // _safe_json_dumps() の戻り値がここに直接埋め込まれる。
      // 例: const monthLabels = ["2026-01", "2026-02"];
      // XSS 対策済みの JSON なので、悪意ある文字列が混入しても安全。
      const monthLabels = {_safe_json_dumps(month_labels)};
      const monthValues = {_safe_json_dumps(month_values)};
      const catLabels = {_safe_json_dumps(cat_labels)};
      const catValues = {_safe_json_dumps(cat_values)};

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
    }}
  </script>
</body>
</html>
"""
    # 保存直前に親フォルダを作っておくと、出力先を変えても失敗しにくい。
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def table_html(rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> str:
    """辞書のリストを HTML の <table> に変換する。

    XSS（クロスサイトスクリプティング）対策:
      CSV の内容をそのまま HTML に埋め込むと、セルに "<script>alert(1)</script>" と
      書かれていた場合、ブラウザがそれを JavaScript として実行してしまう。
      escape() を通すと "<" が "&lt;" に変わり、ただの文字として表示される。
    """
    if not rows:
        # 空テーブルより「データなし」と明示した方が、読み手が迷いにくい。
        return "<p class='muted'>（なし）</p>"

    # 先にヘッダを固定しておくと、「どの列を見ている表か」が HTML からも追いやすい。
    ths = "".join(f"<th>{escape(c)}</th>" for c in columns)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{escape(str(r.get(c, '')))}</td>" for c in columns)
        trs.append(f"<tr>{tds}</tr>")

    return f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
