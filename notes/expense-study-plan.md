# 学習ユニット一覧(下位プロジェクト分析)


| #  | ユニット | 主なファイル | 目安時間 | 進捗 |
| -- | -------- | ------------ | -------- | ---- |
| 1  | アプリ全体の構成（30秒で言える説明を作る） | README.md, expense_tool.py, app.py | 1時間 | 未着手 |
| 2  | データの中心パイプライン（取込 → 検証 → ルール → 集計） | expense_core.py, rules.py, rules.json | 2時間 | 未着手 |
| 3  | 出力の3形式（CSV/Excel/HTML）と使い分け | excel_export.py, html_report.py | 1時間 | 未着手 |
| 4  | セキュリティ対策（面接の鉄板アピール） | excel_export.py, html_report.py, app.py, expense_tool.py | 1.5時間 | 未着手 |
| 5  | Streamlit GUI の要点だけ（全部は読まない） | app.py の冒頭 + 主要関数のみ | 1時間 | 未着手 |
| 6  | テスト + CI（品質保証セットで覚える） | tests/, .github/workflows/ci.yml | 30分 | 未着手 |

## 進め方

- #1 → #4 を最優先（全体像 → セキュリティ。ここまで終われば面接で恥はかかない）
- 余裕があれば #2、#3、#5、#6 を埋める
- 各ユニット終了時に notes/expense-interview-qa.md の該当Qを声に出して練習する


# 必須でやること

- 【ユニット1】

1 README.md の冒頭 + 「見どころ」を読む → 作品が何をするツールか1行で言えるようにする
→ README.md:1-33

2 全体の処理フロー（CSV → 検証 → ルール → 集計 → 出力）を図で覚える
→ README.md:64-92

3 CLI と GUI の2入口構成を理解する（「同じパイプラインを共有している」が言えればOK）
→ README.md:95-135

4 **出力が3形式（CSV / Excel / HTML）**あることを押さえる

- 【ユニット4】

- 【ユニット2】

1. パイプラインの4段階を言えるようにする
読み込み → 入力チェック → 型変換 → ルール適用＋集計 の順番と「なぜこの順番か」。
→ expense_core.py:78-91（read_csv）、expense_core.py:119-186（check_rows）、expense_core.py:189-207（normalize_ok_rows）

ポイント: 「全部文字列のまま check_rows で弾いて、正常と確定した後に int 化する」という順序。先に int() すると例外処理があちこちに散らばるから。

2. errors と warnings の使い分け

errors = 形式エラー。後工程から除外する（expense_core.py:119-186）
warnings = ルール違反。clean_rows には残す（人が確認する問題）
これは面接で「なぜ2つに分けた?」と必ず聞かれる設計判断。

3. rules.json を外部化している理由
コードを書き換えずに、カテゴリ・禁止ワード・上限額を変更できる。rules.py:138-175（load_rules）で JSON → Rules dataclass に変換する流れを押さえる。

4. 集計（make_summary）のフラット構造
{"type", "key", "value"} の3列固定にしている理由 → CSV/Excel/HTML で同じ形を使い回せるから。expense_core.py:210-273

5. 重複検出のキー
(date, amount, merchant.lower()) で同じなら重複候補。除外せず warning だけ付ける（人判断に任せる）。rules.py:194-231

- 【ユニット3】

1. 3形式の使い分けを即答できる
CSV = 元データとして残す（全件）。後続処理や他システムに渡しやすい
Excel = 人が目で確認する用。シート分割＋グラフ＋フィルタで操作性が高い
HTML = ブラウザで共有する用。Chart.jsでグラフ表示、1ファイルで完結 → 「同じ集計データを3つの用途に出し分けている」が言えればOK
2. Excelのシート構成（5枚）を覚える
excel_export.py:63-76

Errors / Warnings / Clean / Summary / Charts
なぜシート分割？ → エラーと正常データを1画面で切り替えて見れる。ユニット2で学ぶ「errors/warnings/clean」の三分割がそのまま出力に反映されている
3. SummaryRow のフラット構造が3形式に効いている
excel_export.py:145-154, html_report.py:63-72

{"type", "key", "value"} の3列固定だから、CSV/Excel/HTML 全部で 同じロジックで type="month_total" をフィルタ できる
→ 「出力先が増えても集計側を変えなくていい」設計判断（面接で聞かれる）
4. HTMLの表示件数を絞っている理由
html_report.py:23, html_report.py:79-83

MAX_TABLE_ROWS = 200 で先頭200件だけ表示
なぜ？ → 数千行を一度に描画するとブラウザが重い。全件は CSV 側で担保（役割分担）


- 【ユニット5】

- 【ユニット6】



# 余裕があったらやること

- 【ユニット1】

1 expense_tool.py と app.py の冒頭だけ眺める → どの関数（check_rows, apply_rules など）に処理が飛ぶか目で確認（深読みはユニット2以降でやる）

2 errors と warnings の使い分けの意図を自分の言葉で説明できるようにする
→ README.md:207-217

3 なぜ DB・認証なしの構成なのかを言えるようにする（ファイル処理アプリとして割り切っている点）
→ README.md:344-366

4 rules.json を外部化している意図（コードを書き換えずにルールを変えられる）を押さえる
→ README.md:221-228

- 【ユニット4】

- 【ユニット2】

A. @dataclass(frozen=True) の意味
処理中に設定値が書き換えられない＝安全。rules.py:23-47

B. unknown_category_mode の3モード
warn / ignore / fallback の違い。fallback は「未知カテゴリを『その他』に書き換えて集計を続ける」挙動。rules.py:292-325

C. 上限チェックが2パスに分かれている理由
行ごとのチェック中は累積合計を貯めるだけ、全行処理後に一気に判定。途中で判定すると「まだ合計が確定していない」から。rules.py:393-465

D. _validate_rules_data の厳密検証
rules.json の型が不正なら黙って補正せず ValueError。「設定ミスを早く気づかせる」設計。rules.py:50-135

E. TypedDict を使う理由
辞書のキーと型を IDE・mypy に教えられる。dict のまま使うより安全。expense_core.py:25-76

- 【ユニット3】

A. Excelの細かい操作性の作り込み
excel_export.py:108-112

freeze_panes="A2"（ヘッダ固定）、auto_filter（フィルタ）、_auto_width（列幅自動）
→ 「渡した相手がすぐ使える状態にする」意識

B. Chart.js を CDN で使っている設計判断
html_report.py:140, html_report.py:146-151

メリット: Matplotlibなど重いライブラリ不要、HTML1ファイルで完結
デメリット: オフラインだと読み込めない → フォールバックで「ライブラリが必要です」と表示
→ トレードオフを意識した設計、と言える

C. openpyxl の Reference でグラフを作る流れ
excel_export.py:167-178

データをシートに書き込む → Reference で範囲指定 → BarChart / PieChart に渡す
棒グラフ（月別）＋円グラフ（カテゴリ別）の2種類

D. セキュリティ対策の"出力側"の部分（ユニット4の予習）
sanitize_cell（Excelの数式インジェクション対策） excel_export.py:104
escape()（HTMLのXSS対策）html_report.py:215
_safe_json_dumps（</script> 対策）html_report.py:26-39
→ ユニット4で深掘りするので、ここでは「3形式それぞれに対策がある」だけ押さえればOK

- 【ユニット5】

- 【ユニット6】