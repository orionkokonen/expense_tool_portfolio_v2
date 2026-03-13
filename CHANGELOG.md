<!-- 学習用メモ: CHANGELOG は「今どう動くか」より「いつ何が変わったか」を見る場所です。 -->

# 変更履歴

このファイルでは、プロジェクトの主要な変更点を時系列で記録します。

## 未リリース

- `excel_export.py`、`tests/test_expense_tool.py`、`tests/test_html_report.py`、`tests/test_rules.py` の import ブロックを `ruff` の期待する形式に揃えて `I001` を解消し、あわせて import の並び順の意図が追いやすいよう先頭付近の学習用コメントを整えた。ローカルでは `python -m ruff check .` と `python -m py_compile` で確認を実施。
- 今後の実装予定を管理するために `ROADMAP.md` を追加。
- 経費処理パイプライン全体で発生していた `mypy` の型不一致により、CI が失敗していた問題を修正。
- warnings と summary 用の明示的な型付き行モデルを追加し、`rules.py`、`app.py`、各レポート出力処理のデータの流れを正規化後の形式に揃えた。
- アップロード、件数カウント、出力パス、`defaultdict` 周りの Streamlit の型付けを見直し、`ruff`、`mypy`、`pytest` が再びローカルで通る状態にした。
- インデントされた HTML 断片を `st.markdown(..., unsafe_allow_html=True)` に渡す前に正規化し、Streamlit のカードで生の HTML が文字列として表示される不具合を修正。
- `app.py` の Streamlit UI ラベルを、サイドバー、タブ、メトリクス、ダウンロード操作を含めて日本語化し、画面全体の表記を統一。
- `st.file_uploader` に見えていた英語文言を CSS 上書きで日本語表示に差し替え、ドラッグアンドドロップ案内と参照ボタンも対象にした。
- ローカライズしたアップロードボタン定義の行長超過により発生していた Ruff `E501` エラーを修正。
- 最近の UI 日本語化と CI 関連変更について、読み手が意図を追いやすいように初心者向けコメントを追加。
- `app.py` と `html_report.py` の安全性を高めるため、ユーザー入力パスをプロジェクトルート配下に制限し、埋め込み JSON 内の `</script>` をエスケープし、`.gitignore` で `.env` 系ファイルを無視するようにした。
- `app.py` と `rules.py` の広すぎる例外処理を具体的な例外型に置き換え、ファイル、JSON、バリデーション失敗時の挙動を予測しやすくした。
- `expense_core.py` の `dict.get(..., "")` 利用を統一し、`html_report.py` の `MAX_TABLE_ROWS` 定数を抽出し、CDN 読み込み失敗時のフォールバック文言を追加して、レポートまわりとコア処理の保守性を改善。
- `disallow_untyped_defs` を有効化し、`excel_export.py` に `Worksheet` 型ヒントを追加し、実行時・開発時依存関係に上限制約を付けて、型安全性と依存関係管理を強化。
- `rules.py`、`expense_core.py`、`expense_tool.py`、`excel_export.py`、`html_report.py` 向けに 5 つのテストモジュールを追加し、ローカルテストは 91 件すべて成功、Streamlit 専用の `app.py` を除いてほぼ 100% のカバレッジになった。

## v0.3

- Streamlit GUI に `Run sample_bad.csv` ボタンを追加し、サンプルをワンクリックで実行できるようにした。
- Streamlit GUI に `errors.csv`、`warnings.csv`、`clean.csv`、`summary.csv`、`report.xlsx`、`report.html` の直接ダウンロードボタンを追加。
- `st.session_state["last_run"]` を保持するようにして、再実行後も結果テーブルとダウンロードボタンが表示されたままになるようにした。

## v0.2

- `rules.json` に対応し、カテゴリルール、禁止ワード、日付範囲チェック、金額上限チェックを追加。
- `warnings.csv` の出力と、警告を扱う処理の流れを追加。
- Excel（`.xlsx`）および HTML レポート生成を追加。
- 上位加盟店、曜日別合計、平均値、中央値などの集計を強化。
- 出力ファイル名に日時を付けられる `--timestamp` オプションを追加。
- カバレッジ計測と基本テストを追加。

## v0.1

- CSV の基本バリデーションとエラー検出を追加。
- `errors.csv` と `summary.csv` の出力を追加。
