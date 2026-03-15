<!-- 学習用メモ: README はコードを読む前の地図。迷ったら「全体の処理の流れ」に戻る。 -->
# 支出ツール 2.0

CSV の支出データを読み込み、入力エラーとルール警告を分けて確認しながら、
CSV / Excel / HTML の成果物を出力するポートフォリオです。

操作方法は 2 つあります。

- **CLI**: `expense_tool.py` からチェックやレポート生成を実行
- **GUI**: `app.py` の Streamlit ダッシュボードからアップロードして実行

現在の作品は、**Render 上で公開できるファイル処理アプリ**としてまとめています。
データベースや認証は持たず、アップロードした CSV をその場で検証して、
必要なレポートをダウンロードして持ち帰る使い方を想定しています。

---

## このポートフォリオの見どころ

- **入力チェックとルール警告を分離**して、先に直すべきものを明確化
- **GUI 2.0** として、`概要 / 検証 / 集計 / ダウンロード` の順に自然に読める画面構成
- **CLI と GUI が同じ処理パイプライン**を共有し、見た目だけでなく内部設計も整理
- **CSV / Excel / HTML** の複数形式で成果物を出力
- **Render デプロイ対応**の Streamlit 構成
- **pytest / ruff / mypy / GitHub Actions** で継続的に品質確認

### 安全化のポイント

- **数式インジェクション対策**: CSV / Excel 出力時に、危険な先頭文字を持つ文字列を無害化
- **GUI の `run_id` 分離**: 実行ごとに別ディレクトリへ保存し、成果物を混線させない
- **パストラバーサル対策**: GUI のパス入力はプロジェクト配下だけを許可
- **HTML / JSON の XSS 対策**: レポート埋め込みデータをエスケープして出力

---

## できること

- 支出 CSV の **基本入力チェック**
  - 必須列
  - 空欄
  - 日付形式
  - 金額の整数判定
- **重複候補の検出**
  - `(date, amount, merchant)` が同じ行を warning 扱いで通知
- **社内ルール違反の検出**
  - 未登録カテゴリ
  - 禁止ワード
  - 日付範囲外
  - 日次 / 月次 / カテゴリ別の上限超過
- **集計レポートの生成**
  - 月別
  - カテゴリ別
  - 支出先 Top N
  - 曜日別
  - 基本統計（件数 / 平均 / 中央値 / 最小 / 最大）
- **成果物のダウンロード**
  - 元 CSV
  - errors / warnings / clean / summary
  - report.xlsx
  - report.html

---

## 全体の処理の流れ

```text
CSVファイル
    ↓
① read_csv
    ↓
② check_rows
    ↓
  errors / ok_rows
    ↓
③ normalize_ok_rows
    ↓
④ load_rules
    ↓
④.5 find_duplicate_candidates
    ↓
⑤ apply_rules
    ↓
  warnings / clean_rows
    ↓
⑥ make_summary
    ↓
⑦ write_csv / write_xlsx_report / write_html_report
```

ポイントは、**形式エラーのある行を早い段階で除外**していることです。
そのため後続のルール判定と集計は、正常に読めるデータだけを前提にシンプルに書けています。

---

## CLI と GUI の違い

### CLI

- 入口: `expense_tool.py`
- サブコマンド:
  - `check`: `errors.csv` と `warnings.csv` を出力
  - `report`: 上記に加えて `clean.csv` / `summary.csv` / `report.xlsx` / `report.html` を出力
- 終了コード:
  - `0`: 入力エラーなし
  - `2`: 入力エラーあり、または `rules.json` の検証エラー
- バッチや CI から呼びやすい構成

主なオプション:

| オプション | 意味 |
|---|---|
| `--rules rules.json` | 使うルールファイルの指定 |
| `--out out` | 出力先ベースディレクトリの指定 |
| `--timestamp` | 履歴保存モード。ファイル名に日時を付ける |
| `--top-n 10` | 支出先 Top N の件数 |

### GUI

- 入口: `app.py`
- フレームワーク: Streamlit
- 画面構成:
  - `概要`: 件数メトリクス、要点、主要グラフ
  - `検証`: エラー / 警告 / クリーンプレビュー
  - `集計`: 月別、カテゴリ別、支出先、曜日別、統計
  - `ダウンロード`: 生成ファイルと元 CSV の取得
- 実行方法:
  - CSV をアップロードして実行
  - `sample_bad.csv` / `sample_good.csv` をワンクリック実行
- 出力設定:
  - Excel の生成有無
  - HTML の生成有無
  - 支出先 Top N
  - `rules.json` パス
  - 出力先ディレクトリ

---

## 出力構成

### CLI の出力

`python expense_tool.py report data/sample_bad.csv --rules rules.json` を実行すると、
既定では次の場所に出力されます。

```text
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

`--timestamp` を付けると `out/history/sample_bad/errors_YYYYMMDD_HHMMSS.csv` のように、
同じ入力でも履歴として残せます。

### GUI の出力

GUI の既定出力先は `out/gui` です。
実行ごとに `run_id` 付きディレクトリが作られ、その中に元 CSV と成果物を保存します。

```text
out/
└── gui/
    └── ab12cd34/
        ├── sample_bad.csv
        ├── sample_bad_errors.csv
        ├── sample_bad_warnings.csv
        ├── sample_bad_clean.csv
        ├── sample_bad_summary.csv
        ├── sample_bad_report.xlsx
        └── sample_bad_report.html
```

GUI では生成をオフにした形式は作られません。

---

## 入力 CSV の形式

1 行目にヘッダが必要です。列順は固定ではありませんが、次の 4 列は必須です。

```csv
date,amount,merchant,category
2026-01-10,1200,A社,交通費
2026-01-11,3500,B社,交際費
```

| 列名 | 形式 | NG の例 |
|---|---|---|
| `date` | `YYYY-MM-DD` | `2026/01/10`, `2026-13-01` |
| `amount` | 整数のみ | `1,200`, `1.5`, `abc` |
| `merchant` | 文字列 | 空欄、空白のみ |
| `category` | 文字列 | 空欄、空白のみ |

補足:

- 入力 CSV は **UTF-8 前提**
- **負数は許可**
  - 返金や訂正を表すケースを想定

---

## errors と warnings の違い

| | errors | warnings |
|---|---|---|
| 意味 | 形式が壊れていて後続処理に進めない | 形式は正しいが確認したいルール上の問題がある |
| 例 | 空欄、日付形式違い、金額不正 | 未登録カテゴリ、禁止ワード、上限超過、重複候補 |
| 後工程 | 除外される | `clean_rows` に残る |
| 想定アクション | まず CSV を修正する | 人が確認して修正または承認する |

重複候補は `duplicate_candidate` として warning 扱いです。
同じ `(date, amount, merchant)` の組み合わせを持つ行が複数あるとき、そのグループ全体に警告を付けます。

---

## ルールファイル `rules.json`

このポートフォリオは、**コードを書き換えずに判定ルールを変えられる**ようにしています。
`rules.sample.json` をコピーして `rules.json` を作り、必要な部分だけ調整してください。

`rules.json` は厳密にバリデーションされます。
省略されたキーにはデフォルト値が使われますが、**型や値が不正なら明示的に停止**します。

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

### `unknown_category_mode`

| 値 | 動作 |
|---|---|
| `"warn"` | 警告を出して、そのまま通す |
| `"ignore"` | 警告を出さず、そのまま通す |
| `"fallback"` | `fallback_category` に置き換えて警告も出す |

---

## フォルダ・主要ファイル

```text
expense_tool_portfolio_v2/
├── app.py                # Streamlit GUI 本体
├── app_helper.py         # GUI から使う非 UI 処理
├── expense_tool.py       # CLI エントリポイント
├── expense_core.py       # CSV 読み込み / 基本チェック / 集計 / CSV 出力
├── rules.py              # rules.json の読み込みとルール適用
├── excel_export.py       # Excel レポート生成
├── html_report.py        # HTML レポート生成
├── ui_html.py            # Streamlit 用 HTML 断片の整形ヘルパー
├── data/
│   ├── sample_bad.csv    # エラーと警告を含むサンプル
│   └── sample_good.csv   # 正常サンプル
├── tests/                # core / CLI / GUI / rules / export などのテスト
├── .github/workflows/
│   └── ci.yml            # GitHub Actions
├── .streamlit/
│   └── config.toml       # Streamlit サーバー設定
├── render.yaml           # Render デプロイ設定
├── requirements.txt      # 実行用依存関係
├── requirements-dev.txt  # 開発・検証用依存関係
└── pyproject.toml        # pytest / ruff / mypy 設定
```

---

## ローカル起動

### 最小構成でアプリを動かす

```bash
python -m pip install -r requirements.txt
```

`rules.json` が未作成なら、`rules.sample.json` をコピーして用意します。

```bash
# Mac / Linux
cp rules.sample.json rules.json

# Windows
copy rules.sample.json rules.json
```

### CLI で実行

```bash
# 入力チェックだけ
python expense_tool.py check data/sample_bad.csv --rules rules.json

# フルレポート生成
python expense_tool.py report data/sample_bad.csv --rules rules.json

# 履歴を残す
python expense_tool.py report data/sample_bad.csv --rules rules.json --timestamp
```

### GUI で実行

```bash
streamlit run app.py
```

起動後、通常は `http://localhost:8501` で開けます。

---

## 開発時の確認

テストや静的解析も回す場合は、開発用依存関係を入れます。

```bash
python -m pip install -r requirements-dev.txt
```

実行コマンド:

```bash
pytest -q
ruff check .
mypy .
```

GitHub Actions では push / pull request ごとに、Python 3.10 から 3.13 でこれらを実行します。

---

## Render デプロイのポイント

このアプリは **データベースなしのファイル処理アプリ**です。

`render.yaml` の主要部分:

```yaml
buildCommand: pip install -r requirements.txt
startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

補足:

- `$PORT`: Render が割り当てるポート番号
- `--server.address 0.0.0.0`: 外部アクセスのために必要
- `PYTHONUNBUFFERED=1`: ログを即時出力
- `.streamlit/config.toml` の `headless = true`: サーバー環境でブラウザ起動を抑止

### ファイル永続化について

Render の無料プランではファイルシステムの永続化を前提にできません。
そのため、GUI から生成したファイルは**その場でダウンロードする運用**が前提です。

---

## 現在のサンプル実行例

2026-03-15 時点で、現行の `data/sample_bad.csv` と `rules.json` に対して
次のコマンドを実行すると以下の結果になります。

```text
$ python expense_tool.py report data/sample_bad.csv --rules rules.json

レポート作成完了
  出力先: out\latest\sample_bad
  errors:   out\latest\sample_bad\errors.csv（件数: 6）
  warnings: out\latest\sample_bad\warnings.csv（件数: 5）
  clean:    out\latest\sample_bad\clean.csv（OK行: 5）
  summary:  out\latest\sample_bad\summary.csv
  excel:    out\latest\sample_bad\report.xlsx
  html:     out\latest\sample_bad\report.html
  全体: 11 / OK: 5 / エラー: 6 / 警告: 5
```

---

## よくある質問

**Q. Excel 出力で `PermissionError` が出る**

A. 生成済みの `.xlsx` を Excel で開いたまま再実行すると失敗します。ファイルを閉じてから再実行してください。

**Q. `pip install` で失敗する**

A. `python -m pip install ...` の形で実行すると、Python 環境の取り違えを減らせます。

**Q. `--timestamp` でファイルが増え続ける**

A. 仕様です。履歴を残すモードなので、毎回新しいファイル名になります。増やしたくない場合は `--timestamp` を外してください。
