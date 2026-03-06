# Expense Tool（経費CSVチェック＆レポート生成）

経費データの CSV ファイルを読み込み、**エラー（errors）** と **警告（warnings）** を自動検知して
CSV / Excel / HTML の 3 種類でレポートを出力するツールです。

操作方法は 2 種類：
- **CLI**（コマンドライン）：ターミナルにコマンドを打って実行
- **GUI**（Streamlit）：ブラウザの画面から CSV をアップロードしてボタンで実行

---

## このアプリでできること

- 経費 CSV の **形式チェック**（空欄・日付・金額・重複）
- **社内ルール違反の検出**（カテゴリ未登録・禁止ワード・上限超え）
- **集計レポート**の生成（月別 / カテゴリ別 / 上位加盟店 / 曜日別）
- チェック結果を **CSV / Excel / HTML** の 3 形式で出力
- GUI でサクッと試せる、ブラウザからダウンロードもできる
- 終了コードで CI / バッチ連携にも対応（エラーあり→コード 2）

---

## 全体の処理の流れ（最重要）

```
CSVファイル
    ↓
① read_csv         — CSV を読み込んで辞書のリストにする
    ↓
② check_rows       — 基本入力チェック（形式・空欄・重複など）
    ↓
  ┌─────────────────────────────────┐
  │ errors（エラー行）                │← 形式が壊れていて処理できない行
  │ ok_rows（OK行）                  │← 次のステップへ進む行
  └─────────────────────────────────┘
    ↓ ok_rows のみ
③ normalize_ok_rows — 文字列 → 整数など型を確定させる
    ↓
④ load_rules        — rules.json から社内ルールを読み込む
    ↓
⑤ apply_rules       — 社内ルール違反を検出する
    ↓
  ┌─────────────────────────────────┐
  │ warnings（警告行）               │← ルール違反の情報
  │ clean_rows（クリーン行）          │← 最終的な正常データ
  └─────────────────────────────────┘
    ↓ clean_rows を使う
⑥ make_summary      — 月別・カテゴリ別・加盟店別などを集計する
    ↓
⑦ 出力              — CSV / Excel / HTML に書き出す
```

**ポイント：** エラー行は②で除外されるので、ルールチェックと集計は「正常データだけ」を扱える設計になっています。

---

## データの流れ（入力 → 処理 → 出力）

```
[入力] expenses.csv
  date,amount,merchant,category
  2026-01-10,1200,A社,交通費
  2026/01/10,500,B社,消耗品      ← 日付形式が違う → errors へ
  2026-01-11,99999,C社,ギャンブル ← 禁止ワード    → warnings へ

         ↓ check_rows + apply_rules

[出力ファイル]
  errors.csv   → 形式エラーがある行（まず修正が必要）
  warnings.csv → 社内ルール違反の行（人間が確認・承認）
  clean.csv    → 問題なしのクリーンな行
  summary.csv  → 月別合計・カテゴリ別合計などの集計結果
  report.xlsx  → 上記 4 つ + グラフをまとめた Excel
  report.html  → ブラウザで見られるグラフつきレポート
```

---

## 画面・機能の一覧

### CLI（コマンドライン：expense_tool.py）

| コマンド | 出力されるもの |
|---|---|
| `check` | errors.csv / warnings.csv |
| `report` | 上記 + clean.csv / summary.csv / report.xlsx / report.html |

主なオプション：

| オプション | 意味 |
|---|---|
| `--rules rules.json` | 使うルールファイルを指定（既定: rules.json） |
| `--out out` | 出力先フォルダを指定（既定: out） |
| `--timestamp` | ファイル名に日時を付けて履歴として残す |
| `--top-n 10` | 上位加盟店の表示件数（既定: 10） |

### GUI（ブラウザ：app.py / Streamlit）

| 操作 | 内容 |
|---|---|
| CSV アップロード | ブラウザから CSV ファイルを選んでアップロード |
| サンプル実行 | `sample_bad.csv` / `sample_good.csv` をワンクリックで試せる |
| 出力設定 | Excel / HTML の生成有無をチェックボックスで選択 |
| 結果表示 | errors / warnings / summary の一覧を画面に表示 |
| ダウンロード | 生成した全ファイルをブラウザからダウンロード |

---

## フォルダ・主要ファイルの役割

```
expense_tool_portfolio_v2/
│
├── app.py              ← Streamlit の GUI 画面（ブラウザで操作する入口）
├── expense_tool.py     ← CLI の入口（コマンドを受け取って処理を起動する）
│
├── expense_core.py     ← 処理の中心：CSV 読み込み / 基本チェック / 集計 / CSV 出力
├── rules.py            ← rules.json を読み込み、社内ルール違反を検出する
├── excel_export.py     ← Excel（.xlsx）レポートを生成する
├── html_report.py      ← HTML レポートを生成する（グラフ付き）
│
├── rules.json          ← 社内ルールの設定ファイル（コードを変えずにルール変更できる）
├── rules.sample.json   ← rules.json のサンプル（最初にコピーして使う）
│
├── data/
│   ├── sample_bad.csv  ← わざとミスを入れたテスト用データ
│   └── sample_good.csv ← 正常データの例
│
├── tests/
│   └── test_core.py    ← pytest の単体テスト
│
├── .github/workflows/
│   └── ci.yml          ← GitHub Actions の CI 設定（push/PR のたびに自動テスト）
│
├── render.yaml         ← Render へのデプロイ設定
├── .streamlit/
│   └── config.toml     ← Streamlit のサーバー設定（headless = true）
│
├── requirements.txt        ← 実行に必要なライブラリ（openpyxl, streamlit）
└── requirements-dev.txt    ← 開発用ライブラリ（pytest, ruff, mypy など）
```

---

## 入力 CSV の形式

1 行目にヘッダが必要です。列の順番は問いません。

```csv
date,amount,merchant,category
2026-01-10,1200,A社,交通費
2026-01-11,3500,B社,交際費
```

| 列名 | 形式 | NG の例 |
|---|---|---|
| `date` | `YYYY-MM-DD` | `2026/01/10`（スラッシュ）`2026-13-01`（存在しない日付） |
| `amount` | 整数のみ | `1,200`（カンマ入り）`1.5`（小数）`abc`（文字） |
| `merchant` | 文字列（空欄 NG） | 空白のみ |
| `category` | 文字列（空欄 NG） | 空白のみ |

---

## ルールファイル（rules.json）の説明

「コードを書き換えずに運用ルールを変えられる」のがポイントです。
`rules.sample.json` をコピーして `rules.json` を作り、必要な部分だけ変更してください。

```json
{
  "allowed_categories": ["交通費", "交際費", "消耗品費", "会議費", "旅費", "通信費", "その他"],
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

### unknown_category_mode の選択肢

| 値 | 動作 |
|---|---|
| `"warn"` | 警告を出して `fallback_category` に置き換える（おすすめ） |
| `"ignore"` | 警告も出さずそのまま通す |
| `"fallback"` | `fallback_category` に置き換えて警告も出す |

---

## errors と warnings の違い

| | errors | warnings |
|---|---|---|
| 意味 | 形式が壊れていて集計できない | 形式は OK だが社内ルール違反の可能性 |
| 例 | 空欄・日付形式違い・金額が数字でない | カテゴリ未登録・禁止ワード・上限超え |
| 対応 | まず直す（処理が進まない） | 人間が確認して修正・承認判断 |
| その後 | 後工程から除外される | clean_rows には残る（警告として記録） |

---

## 出力ファイルの構成

入力が `data/sample_bad.csv` の場合、出力先は以下になります：

```
out/
└── latest/
    └── sample_bad/
        ├── errors.csv
        ├── warnings.csv
        ├── clean.csv
        ├── summary.csv
        ├── report.xlsx
        └── report.html
```

`--timestamp` を付けると `out/history/sample_bad/errors_20260203_104530.csv` のように
日時が付いて上書きされずに履歴として残ります。

---

## Render デプロイのポイント

このアプリは **データベースなし**（CSV ファイルを直接処理する設計）です。

### render.yaml の主要設定

```yaml
buildCommand: pip install -r requirements.txt     # デプロイ時にライブラリをインストール
startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

| 設定 | 説明 |
|---|---|
| `$PORT` | Render が自動で割り当てるポート番号。固定できないので環境変数で受け取る |
| `--server.address 0.0.0.0` | 外部（ブラウザ）からアクセスできるようにするため必須 |
| `PYTHONUNBUFFERED=1` | ログをバッファリングせず即時出力する（デバッグしやすくなる） |

### headless = true（.streamlit/config.toml）

Render などのサーバー環境にはブラウザがないため、Streamlit が自動でブラウザを開こうとすると起動エラーになります。`headless = true` でその動作を無効化しています。

### ⚠ ファイルの永続化について

Render の無料プランでは **デプロイのたびにファイルシステムがリセット**されます。
`out/` フォルダに書き出したファイルはサーバー上では消えてしまうため、
**GUI のダウンロードボタンからすぐに取得**するのが正しい使い方です。

---

## ローカル起動手順

### 準備

```bash
# 1. ライブラリをインストール
python -m pip install -r requirements.txt

# 2. rules.json を用意（サンプルをコピー）
# Mac / Linux
cp rules.sample.json rules.json
# Windows（コマンドプロンプト）
copy rules.sample.json rules.json
```

### CLI で実行

```bash
# チェックだけ（errors / warnings を出力）
python expense_tool.py check data/sample_bad.csv --rules rules.json

# 全部レポート（CSV + Excel + HTML）
python expense_tool.py report data/sample_bad.csv --rules rules.json

# タイムスタンプつきで履歴を残す
python expense_tool.py report data/sample_bad.csv --rules rules.json --timestamp
```

### GUI で実行

```bash
streamlit run app.py
```

ターミナルに `http://localhost:8501` と表示されたらブラウザで開いてください。

---

## よくあるトラブル（FAQ）

**Q. Excel 出力でエラーになる（PermissionError）**
A. 生成した `.xlsx` を Excel で開いたまま再実行すると失敗します。Excel を閉じてから実行してください。

**Q. `pip install` でエラーになる**
A. `python -m pip install -r requirements-dev.txt` のように `python -m` を付けると安定します。

**Q. `--timestamp` でファイルが増え続ける**
A. 仕様です。履歴を残すため毎回新しいファイル名になります。増やしたくない場合は `--timestamp` を外してください。

---

## テスト・品質チェック

```bash
# テスト実行
pytest -q

# コードの書き方チェック（静的チェック）
ruff check .

# 型チェック
mypy .
```

GitHub に push すると `.github/workflows/ci.yml` が自動で上記 3 つを実行します（Python 3.10〜3.13 の 4 バージョンで）。

---

## コンソール出力（例）

```
$ python expense_tool.py report data/sample_bad.csv --rules rules.json

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
