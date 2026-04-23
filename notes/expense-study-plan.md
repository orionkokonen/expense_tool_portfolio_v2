# 学習ユニット一覧(下位プロジェクト分析)

| #   | ユニット                                                | 主なファイル                                             | 目安時間 | 進捗   |
| --- | ------------------------------------------------------- | -------------------------------------------------------- | -------- | ------ |
| 1   | アプリ全体の構成（30秒で言える説明を作る）              | README.md, expense_tool.py, app.py                       | 1時間    | 未着手 |
| 2   | データの中心パイプライン（取込 → 検証 → ルール → 集計） | expense_core.py, rules.py, rules.json                    | 2時間    | 未着手 |
| 3   | 出力の3形式（CSV/Excel/HTML）と使い分け                 | excel_export.py, html_report.py                          | 1時間    | 未着手 |
| 4   | セキュリティ対策（面接の鉄板アピール）                  | excel_export.py, html_report.py, app.py, expense_tool.py | 1.5時間  | 未着手 |
| 5   | Streamlit GUI の要点だけ（全部は読まない）              | app.py の冒頭 + 主要関数のみ                             | 1時間    | 未着手 |
| 6   | テスト + CI（品質保証セットで覚える）                   | tests/, .github/workflows/ci.yml                         | 30分     | 未着手 |

## 進め方

- #1 → #4 を最優先（全体像 → セキュリティ。ここまで終われば面接で恥はかかない）
- 余裕があれば #2、#3、#5、#6 を埋める
- 各ユニット終了時に notes/expense-interview-qa.md の該当Qを声に出して練習する

# 必須でやること

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

# 余裕があったらやること

## 【ユニット1】

4. **出力が3形式（CSV / Excel / HTML）**あることを押さえる

1. expense_tool.py と app.py の冒頭だけ眺める → どの関数（check_rows, apply_rules など）に処理が飛ぶか目で確認（深読みはユニット2以降でやる）

1. errors と warnings の使い分けの意図を自分の言葉で説明できるようにする
   → README.md:207-217

1. なぜ DB・認証なしの構成なのかを言えるようにする（ファイル処理アプリとして割り切っている点）
   → README.md:344-366

## 【ユニット4】

5. run_id で成果物を分離
   app_helper.py:69 generate_run_id / app_helper.py:117-119 make_output_dir
   何のため: 複数ユーザーが同時実行しても他人のファイルを上書き／閲覧できないように、実行ごとに out/gui/<run_id>/ に隔離。
   一言で: 「マルチテナント風の衝突回避」

A. なぜ "errors / warnings" を分けたか （ユニット2とも重なるが、セキュリティ観点でも「検証層で弾く＝後工程に不正データを流さない」設計として語れる）

B. rules.json の厳密バリデーション rules.py:50-135 … 設定ファイルの型不正を黙って補正せず ValueError で停止。"fail-fast" は地味に聞かれる。

C. CDNフォールバック html_report.py:146-151 … 可用性の話だがセキュリティ隣接（SRI = Subresource Integrity まで触れると深い）。

D. @dataclass(frozen=True) rules.py:23-47 … ルール設定が実行中に書き換わらない＝改ざん耐性。

E. DB・認証なしの割り切り README.md:344-366 … 「そもそも攻撃面を減らす設計」と言える。

## 【ユニット2】

3. rules.json を外部化している理由
   コードを書き換えずに、カテゴリ・禁止ワード・上限額を変更できる。rules.py:138-175（load_rules）で JSON → Rules dataclass に変換する流れを押さえる。

重複検出のキー
(date, amount, merchant.lower()) で同じなら重複候補。除外せず warning だけ付ける（人判断に任せる）。rules.py:194-231

A. @dataclass(frozen=True) の意味
処理中に設定値が書き換えられない＝安全。rules.py:23-47

B. unknown_category_mode の3モード
warn / ignore / fallback の違い。fallback は「未知カテゴリを『その他』に書き換えて集計を続ける」挙動。rules.py:292-325

C. 上限チェックが2パスに分かれている理由
行ごとのチェック中は累積合計を貯めるだけ、全行処理後に一気に判定。途中で判定すると「まだ合計が確定していない」から。rules.py:393-465

D. \_validate_rules_data の厳密検証
rules.json の型が不正なら黙って補正せず ValueError。「設定ミスを早く気づかせる」設計。rules.py:50-135

E. TypedDict を使う理由
辞書のキーと型を IDE・mypy に教えられる。dict のまま使うより安全。expense_core.py:25-76

## 【ユニット3】

2. SummaryRow のフラット構造が3形式に効いている
   excel_export.py:145-154, html_report.py:63-72
   {"type", "key", "value"} の3列固定だから、CSV/Excel/HTML 全部で 同じロジックで type="month_total" をフィルタ できる
   → 「出力先が増えても集計側を変えなくていい」設計判断（面接で聞かれる）

Excelのシート構成（5枚）を覚える
excel_export.py:63-76
Errors / Warnings / Clean / Summary / Charts
なぜシート分割？ → エラーと正常データを1画面で切り替えて見れる。ユニット2で学ぶ「errors/warnings/clean」の三分割がそのまま出力に反映されている

HTMLの表示件数を絞っている理由
html_report.py:23, html_report.py:79-83
MAX_TABLE_ROWS = 200 で先頭200件だけ表示
なぜ？ → 数千行を一度に描画するとブラウザが重い。全件は CSV 側で担保（役割分担）

A. Excelの細かい操作性の作り込み
excel_export.py:108-112

freeze_panes="A2"（ヘッダ固定）、auto_filter（フィルタ）、\_auto_width（列幅自動）
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
\_safe_json_dumps（</script> 対策）html_report.py:26-39
→ ユニット4で深掘りするので、ここでは「3形式それぞれに対策がある」だけ押さえればOK

## 【ユニット5】

4. 例外の具体列挙キャッチ(app.py:1003-1013)
   except Exception: で握りつぶさず、ValueError / FileNotFoundError / PermissionError / UnicodeDecodeError / JSONDecodeError / OSError と具体的に書いている意図を説明できるように。
   面接ワード: 「想定外の例外までは飲み込まない」「予期した失敗だけをユーザー向けエラーに変換する」

パストラバーサル対策(app.py:944-958)
ユニット4のセキュリティと直結する部分。GUI から任意のパスを入力できるので必ず守る。
Path.cwd().resolve() を基準に safe_resolve でチェック
外を指していたら実行前にブロック

A. HTML 埋め込みと XSS 対策(app.py:435-451, app.py:488-490)
st.markdown(..., unsafe_allow_html=True) を使う際、CSV 由来の文字列は必ず html.escape() をかけている。ユニット4とセットで語れると強い。

B. タブ構成の設計意図(app.py:1030-1033)
「概要 → 検証 → 集計 → ダウンロード」という判断の順に並べた、という UI 設計の話。READMEの「判定を優先」とリンク。

C. メトリクス表示と自作棒グラフ(app.py:454-507)
グラフライブラリを使わず HTML/CSS だけで棒グラフを描画している。依存を増やさない選択の理由を一言で。

D. CSS 一括注入(app.py:65-330)
\_inject_styles() にスタイルを集約し、描画関数側からロジックを分離。ファイルアップローダのラベルを CSS で日本語化している小ネタもある。

E. サンプル実行ボタン(app.py:935-940)
「READMEを開かなくても試せる」というUX配慮。ポートフォリオ作品としてのこだわりポイント。

## 【ユニット6】

3. テストが何をカバーしているか（tests/ の構成）
   test_expense_core.py → パイプラインの中心ロジック
   test_rules.py → ルール判定
   test_excel_export.py / test_html_report.py → 出力系（=セキュリティ対策の検証も兼ねる）
   「ユニット4のセキュリティ対策（数式インジェクション等）がちゃんとテストで守られている」が言えると強い

A. matrix戦略の意味：なぜ複数Pythonバージョンで回すのか（互換性担保、ライブラリ更新の早期検知）

B. ruff / mypy / pytest の役割分担：静的解析 vs 型 vs 動的テストの違い

C. requirements-dev.txt と本番用の分離の意図

D. テストの粒度感：ユニットテスト中心か、結合テストもあるか、各テストファイルを1つ開いて書き方を確認

E. CIが落ちたらマージしない運用（ブランチ保護ルールなどの話）
