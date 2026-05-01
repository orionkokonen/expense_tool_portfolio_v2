# このプロジェクトについて

Streamlit製の経費精算ツールのポートフォリオ。

主な要素:

入口: CLI (expense_tool.py) と GUI (app.py Streamlit) の2系統で同じパイプラインを共有
機能: CSV取込 → 入力チェック / 重複検出 / 社内ルール違反検出 → 月別・カテゴリ別・Top Nなどの集計
出力: CSV(errors/warnings/clean/summary) + Excel (excel_export.py) + HTML (html_report.py)
ルール: rules.json で未登録カテゴリ・禁止ワード・上限額などを外部定義
セキュリティ: 数式インジェクション対策、パストラバーサル対策、HTML/JSONのXSSエスケープ、run_idで実行ごとに成果物を分離
品質管理: pytest / ruff / mypy / GitHub Actions
デプロイ: Render (render.yaml)、DB・認証なしのファイル処理アプリ

# ユーザーについて

- プログラミングの勉強はpythonエンジニア認定基礎試験合格ぐらいで、それ以外は全く経験のない初心者。プログラミングやITに関するほとんどの知識が無いことを前提として、初心者向けに噛み砕いて、専門用語の意味も補足して解説をしてください

# 現在の目的

- ポートフォリオを面接で話せるレベルまで理解する

# 進め方

- 学習ユニット一覧(下位プロジェクト分析)
  の中で、ユーザーからやりたいといわれた勉強内容以外は取り扱わなくていいよ。
  ただし、密接にかかわってて取り扱う必要性が高い場合は取り扱って構わない。
  ボリュームは、自分のような初心者がちゃんと意味を理解するのに1時間以内で理解できるようにして。つまり、そこまで細かいことを深ぼらなくていいってこと。
- 学習ユニットについての学習をする際には、以下のフォルダやファイルは読まないでください。
  migrations/ …… Alembic自動生成。中身は学習対象外
  app/templates/, app/static/ …… HTML/CSS/JSは学習対象外
  static/vendor/ …… Bootstrap同梱コピー。読む価値なし
  instance/, tests/\_runtime_tmp/ …… 生成物
  requirements.txt, Procfile, wsgi.py …… 1ファイル1〜2行なので必要時だけ読む
- 実際のコードを見ながら説明する
- 面接で聞かれそうな質問形式で解説する
- 下の学習ユニットに沿って進めてほしい

# 学習ユニット一覧(下位プロジェクト分析)

| #   | ユニット                                                | 主なファイル                                             | 目安時間 | 進捗   |
| --- | ------------------------------------------------------- | -------------------------------------------------------- | -------- | ------ |
| 1   | アプリ全体の構成（30秒で言える説明を作る）              | README.md, expense_tool.py, app.py                       | 1時間    | 未着手 |
| 2   | データの中心パイプライン（取込 → 検証 → ルール → 集計） | expense_core.py, rules.py, rules.json                    | 2時間    | 未着手 |
| 3   | 出力の3形式（CSV/Excel/HTML）と使い分け                 | excel_export.py, html_report.py                          | 1時間    | 未着手 |
| 4   | セキュリティ対策（面接の鉄板アピール）                  | excel_export.py, html_report.py, app.py, expense_tool.py | 1.5時間  | 未着手 |
| 5   | Streamlit GUI の要点だけ（全部は読まない）              | app.py の冒頭 + 主要関数のみ                             | 1時間    | 未着手 |
| 6   | テスト + CI（品質保証セットで覚える）                   | tests/, .github/workflows/ci.yml                         | 30分     | 未着手 |

## 【ユニット1】

1. README.md の冒頭 + 「見どころ」を読む → 作品が何をするツールか1行で言えるようにする
   → README.md:1-33

2. 全体の処理フロー（CSV → 検証 → ルール → 集計 → 出力）を図で覚える
   → README.md:64-92

3. CLI と GUI の2入口構成を理解する（「同じパイプラインを共有している」が言えればOK）
   → README.md:95-135

## 【ユニット4】

1. Excel の数式インジェクション対策 → sanitize_cell
   expense_core.py:276 … sanitize_cell 本体
   excel_export.py:104 … 書き込み時に通している箇所
   何を防ぐか: セルが =, +, -, @ で始まるとExcelが数式として実行し、外部コマンドを叩かれる恐れ（CSV Injection / Formula Injection）。
   どう防ぐか: 先頭にシングルクォートを付けてただの文字列にする。

2. HTML の XSS対策 → escape()
   html_report.py:215 … escape(str(r.get(c, ''))) でセル値を無害化
   何を防ぐか: CSVに <script>alert(1)</script> が入っていたらブラウザで実行される。
   どう防ぐか: html.escape() で < を &lt; に変換して「ただの文字」として表示。

3. </script> 突破型XSS対策 → \_safe_json_dumps
   html_report.py:26-39
   何を防ぐか: 集計データを <script> タグ内にJSONで埋め込む設計なので、データに </script> が含まれるとそこでタグが閉じられて後続が実行される。
   どう防ぐか: ensure_ascii=True で日本語を \uXXXX 化 + </ → <\/ 置換。
   面接のキモ: 「escape() だけでは足りず、<script> の中は別対策が要る」と言えると差がつく。

4. パストラバーサル対策 → safe_resolve
   app_helper.py:84-92
   何を防ぐか: ../../etc/passwd みたいな相対パスでプロジェクト外のファイルを読まれる。
   どう防ぐか: .resolve() で絶対パスに展開 → Path.relative_to() でプロジェクトルート配下かチェック。

## 【ユニット2】

1. パイプラインの4段階を言えるようにする
   読み込み → 入力チェック → 型変換 → ルール適用＋集計 の順番と「なぜこの順番か」。
   → expense_core.py:78-91（read_csv）、expense_core.py:119-186（check_rows）、expense_core.py:189-207（normalize_ok_rows）

ポイント: 「全部文字列のまま check_rows で弾いて、正常と確定した後に int 化する」という順序。先に int() すると例外処理があちこちに散らばるから。

2. errors と warnings の使い分け
   errors = 形式エラー。後工程から除外する（expense_core.py:119-186）
   warnings = ルール違反。clean_rows には残す（人が確認する問題）
   これは面接で「なぜ2つに分けた?」と必ず聞かれる設計判断。

## 【ユニット3】

1. 3形式の使い分けを即答できる
   CSV = 元データとして残す（全件）。後続処理や他システムに渡しやすい
   Excel = 人が目で確認する用。シート分割＋グラフ＋フィルタで操作性が高い
   HTML = ブラウザで共有する用。Chart.jsでグラフ表示、1ファイルで完結 → 「同じ集計データを3つの用途に出し分けている」が言えればOK

## 【ユニット5】

1. Streamlit の実行モデルと st.session_state
   最重要ポイント。Streamlit は操作のたびにスクリプト全体が上から再実行される仕様で、これを知らないと他のコードの意図が全部ぼやけます。
   app.py:1018 st.session_state[LAST_RUN_KEY] = result で結果を保存
   app.py:1023 再実行時はそこから読み戻す
   面接ワード: 「リアクティブな再実行モデル」「セッション状態で結果を永続化」

2. main() の全体の流れ(app.py:903-1045)
   入力 → 実行 → 保存 → 描画 の4段構成を口で説明できるように。
   サイドバーで入力を集約 (app.py:912-941)
   ボタン判定で共通パイプラインへ (app.py:949)
   結果を session_state に格納 (app.py:1018)
   4つのタブで描画 (app.py:1031-1041)

3. UI と非UIロジックの分離
   run_pipeline などの重い処理は app_helper.py に切り出し、app.py は描画と入力集約に専念。
   面接ワード: 「関心の分離」「CLI (expense_tool.py) と GUI (app.py) が同じパイプラインを共有」

## 【ユニット6】

1. なぜテストとCIをセットで語るのか（30秒で言えるように）
   「テスト = コードが正しいことを証明する仕組み」「CI = それを毎回自動で走らせる仕組み」
   片方だけだと片手落ち(テストあっても回さなきゃ意味ない・CIあっても中身空なら意味ない)

2. CIの3点セット（.github/workflows/ci.yml）
   ruff check . → 書き方チェック（linter）
   mypy . → 型チェック
   pytest -q → テスト実行
   「push と PR で自動実行」「Python 3.10〜3.13 の4バージョンで並列実行」が言えればOK
