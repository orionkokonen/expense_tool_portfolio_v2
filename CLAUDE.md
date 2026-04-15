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

- Pythonエンジニア認定基礎試験合格済みの初心者
- 専門用語は噛み砕いて説明する
- 面接で話せるレベルまで理解するのが目的

# 現在の目的

ポートフォリオを面接で話せるレベルまで理解する

# 進め方

- 実際のコードを見ながら説明する
- 面接で聞かれそうな質問形式で解説する
- 初心者向けに噛み砕いて説明する
- 必要に応じて専門用語の意味も補足する
- 下の学習ユニットに沿って進めてほしい