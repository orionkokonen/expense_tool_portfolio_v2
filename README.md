# Expense Tool（経費CSVチェック＆レポート生成）

経費データ（CSV）を読み込み、**エラー（errors）** と **警告（warnings）** を検知し、  
CSV / Excel（.xlsx）/ HTML のレポートを出力する CLI ツールです（ポートフォリオ）。

---

## これは何？

経費CSVをチェックして、次を出します。

- **errors（エラー）**：データの構造・形式として「成立していない」もの  
  例）必須列がない、空欄、日付形式が違う、金額が数字でない、重複 など
- **warnings（警告）**：データは成立しているが「社内ルール違反」になりうるもの  
  例）カテゴリ未登録、禁止ワード、日付範囲外、上限超え など

さらに `report` では、OK行（clean）や集計（summary）、Excel/HTMLレポートまで作ります。

---

## できること（機能一覧）

### コマンド

- `check`：`errors.csv` / `warnings.csv` を出力
- `report`：`errors/warnings/clean/summary` + **Excel(.xlsx)** + **HTMLレポート** を出力

### オプション

- `--rules rules.json`：ルールファイルを指定（既定: `rules.json`）
- `--out out`：出力先フォルダを指定（既定: `out`）
- `--timestamp`：ファイル名に日時を付けて履歴を残す（例：`..._20260203_104530.csv`）
- `--top-n 10`：merchant上位集計の件数（既定: 10）

### 終了コード（重要）

- **errors が 0 件** → 終了コード `0`
- **errors が 1 件以上** → 終了コード `2`  
  （バッチ処理やCIで “失敗を検知できる” ようになります）

---

## 必要なもの

- Python 3.10+
- Excel出力に `openpyxl`

---

## インストール

通常（実行に必要な最小構成）：

```bash
python -m pip install -r requirements.txt
```

開発用（テスト/整形/型チェックなど）：

```bash
python -m pip install -r requirements-dev.txt
```

---

## 最速の使い方

### 1) ルールファイルを作る

サンプルをコピーして `rules.json` を用意します。

・Windows（コマンドプロンプト)

```bat
copy rules.sample.json rules.json
```

・Windows（PowerShell）

```powershell
Copy-Item rules.sample.json rules.json
```

・Mac / Linux

```bash
cp rules.sample.json rules.json
```

### 2) サンプルCSVで実行

チェックだけ（CSV出力）：

```bash
python expense_tool.py check data/sample_bad.csv --rules rules.json
```

全部レポート（CSV + Excel + HTML）：

```bash
python expense_tool.py report data/sample_bad.csv --rules rules.json
```

日時つきで履歴を残したい場合：

```bash
python expense_tool.py report data/sample_bad.csv --rules rules.json --timestamp
```

---

## GUIで実行（app.py / Streamlit）
1) 起動
streamlit run app.py


起動するとターミナルにURL（例：http://localhost:8501）が出るので、ブラウザで開きます。

2) GUIでできること（想定）

入力CSV（例：data/sample_bad.csv）を選ぶ or アップロードする

rules.json を指定する

check / report をボタンで実行する

errors / warnings / clean / summary を画面で確認する

必要ならファイル出力（CSV / Excel / HTML）を作る

※ GUIは「CLIが難しい人でも使える」を示すための拡張です。
本体のロジックは CLI と同じモジュール（expense_core.py / rules.py）を使う想定です。


## 出力について（重要：迷わないための説明）

### ✅ 入力CSVごとに出力フォルダが分かれる

入力が `data/sample_bad.csv` なら prefix は `sample_bad` になり、出力先はこうなります：

- `out/latest/sample_bad/errors.csv`
- `out/latest/sample_bad/warnings.csv`
- `out/latest/sample_bad/clean.csv`
- `out/latest/sample_bad/summary.csv`
- `out/latest/sample_bad/report.xlsx`
- `out/latest/sample_bad/report.html`

入力が `data/sample_good.csv` なら `out/latest/sample_good/` に出ます。

### ✅ `--timestamp` のメリット

`--timestamp` を付けると、ファイル名に日時が付き、履歴を残せます。

例：

- `out/latest/sample_bad/report_20260203_104530.xlsx`
- `out/latest/sample_bad/report_20260203_105012.xlsx`

### ⚠ `--timestamp` を付けるとファイルは増えます

「毎回増える」のは仕様です（履歴を残すため）。  
増やしたくないなら `--timestamp` を外してください。

---

## 入力CSVの形式

ヘッダ（1行目）に次の列が必要です：

- `date`
- `amount`
- `merchant`
- `category`

推奨ルール：

- date：`YYYY-MM-DD`
- amount：整数（例：`1200`）  
  ※ `1,200` はNG（`int()` にできない)

---

## ルールファイル（rules.json）の説明

`rules.json` で「会社の運用ルール」を変更できます  
（コードを書き換えずに運用変更できるのが強み）。

例：

```json
{
  "allowed_categories": [
    "交通費",
    "交際費",
    "消耗品費",
    "会議費",
    "旅費",
    "通信費",
    "その他"
  ],
  "unknown_category_mode": "warn",
  "fallback_category": "その他",
  "banned_words": ["ギャンブル", "パチンコ", "競馬"],
  "date_range": { "min": "2026-01-01", "max": "2026-12-31" },
  "limits": {
    "daily_total": 30000,
    "monthly_total": 200000,
    "category_daily": { "交通費": 10000 },
    "category_monthly": { "交際費": 30000 }
  }
}
```

### unknown_category_mode（超重要）

`allowed_categories` に無いカテゴリが来た時の扱いを決めます。

- `"warn"`：警告を出し、`fallback_category` に置換して clean に入れる（おすすめ）
- `"error"`：ルール違反を「エラー扱い」にする（厳格運用向け）
- `"off"`：カテゴリ未登録でも何もしない（運用ゆるめ）

---

## errors と warnings の違い

- **errors**：形式が壊れていて「集計できない」レベル  
  → まず直さないと処理が進まない
- **warnings**：形式はOKだが「会社ルールに違反の可能性」  
  → 人間が確認して修正・承認判断するための情報

この分離によって、「データ品質」と「運用ルール」を混ぜずに扱える設計になっています。

---

## Excel / HTML レポートの中身

`report` コマンドで以下が出ます：

- Excel：`out/latest/<prefix>/report.xlsx`
  - `Errors / Warnings / Clean / Summary`
  - `Charts`（実装によりシートが存在し、グラフ表示も可能）
- HTML：`out/latest/<prefix>/report.html`
  - ブラウザで見られるレポート（グラフ付き）

---

## サンプル

- `data/sample_good.csv`：正常データ例
- `data/sample_bad.csv`：わざとミスを入れたテスト用データ

### sample_bad.csv に入れているミス例

- `2026/01/06`（日付の形式が違う）
- `2026-13-01`（存在しない日付）
- `1,200`（カンマ入りで `int` にできない）
- `abc`（数字じゃない）
- 日付空欄 / merchant空欄 / category空欄
- 重複（同じ date+amount+merchant）
- merchant の大文字小文字違い（Amazon と amazon）

---

## よくあるトラブル（FAQ）

### Q1. Excel出力でエラーが出た（PermissionErrorっぽい）

A. 生成した `.xlsx` をExcelで開いたままだと、上書き保存できず失敗します。  
Excelを閉じてからもう一度実行してください。

### Q2. `pip install -r ...` が変なエラーになった

A. `python -m pip ...` を使うと安定します。

```bash
python -m pip install -r requirements-dev.txt
```

### Q3. `--timestamp` で out にファイルが増え続ける

A. 仕様です。履歴を残すために毎回新しいファイル名になります。  
増やしたくない場合は `--timestamp` を付けないでください。

---

## プロジェクト構成（ざっくり）

- `expense_tool.py`：CLI入口（引数解析・入出力）
- `expense_core.py`：CSV読み込み・基本チェック（errors）・集計・CSV出力
- `rules.py`：rules.json 読み込みとルール適用（warnings生成）
- `excel_export.py`：Excelレポート出力
- `html_report.py`：HTMLレポート出力
- `data/`：サンプルCSV
- `out/`：出力先
- `tests/`：pytest

---

## これを作った意図

- 構造エラー（errors） と 運用ルール違反（warnings） を分離して設計した
- ルールを `rules.json` に外部化し、「運用変更＝コード変更」にならないようにした
- 出力を CSV / Excel / HTML に分け、用途別に見やすくした
- 終了コードを整備し、バッチやCIに組み込める形にした

## コンソール出力（例）

例：コマンドプロンプトで以下を実行

```bat
python expense_tool.py report data/sample_bad.csv --rules rules.json


レポート作成完了
  出力先: out\latest\sample_bad
  errors:   out\latest\sample_bad\errors.csv（件数: 8）
  warnings: out\latest\sample_bad\warnings.csv（件数: 1）
  clean:    out\latest\sample_bad\clean.csv（OK行: 3）
  summary:  out\latest\sample_bad\summary.csv
  excel:    out\latest\sample_bad\report.xlsx
  html:     out\latest\sample_bad\report.html
  全体: 11 / OK: 3 / エラー: 8 / 警告: 1
```

---

## GUI update (A/B): sample run + downloads

### New sidebar actions

- `Run with uploaded CSV`: runs validation/report flow for the uploaded file.
- `Run sample_bad.csv`: runs `data/sample_bad.csv` without any upload.

### Download outputs from the browser

After each run, the app now shows direct download buttons:

- `errors.csv`
- `warnings.csv`
- `clean.csv`
- `summary.csv`
- `report.xlsx` (when Excel output is enabled)
- `report.html` (when HTML output is enabled)

If a file cannot be read, the app shows a warning instead of a broken button.

### State persistence

The GUI stores the latest run in `st.session_state["last_run"]`, so result tables and download buttons remain visible after Streamlit reruns.
