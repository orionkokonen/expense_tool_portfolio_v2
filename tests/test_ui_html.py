"""tests/test_ui_html.py — HTML 整形ヘルパーの最小テスト。

`normalize_html_fragment()` は小さな関数だが、Streamlit 画面の見た目に直結する。
そのため、処理が短くても「どの空白を消して、どの並びを残すか」を
テストで固定しておくと安心して整理しやすい。
"""

from ui_html import normalize_html_fragment


def test_normalize_html_fragment_removes_leading_indentation() -> None:
    """行頭の空白が除去され、HTML がコード表示に化けないことを確認する。"""
    raw = """
        <div class="bar-card">
          <h3>Monthly total</h3>
              <div class="bar-row">
                <div class="bar-label">2026-01</div>
                <div class="bar-value">2,781円</div>
              </div>
        </div>
    """

    # 入力側は読みやすいようにインデントして書き、出力側だけをきれいに整える。
    normalized = normalize_html_fragment(raw)

    assert normalized == "\n".join(
        [
            '<div class="bar-card">',
            "<h3>Monthly total</h3>",
            '<div class="bar-row">',
            '<div class="bar-label">2026-01</div>',
            '<div class="bar-value">2,781円</div>',
            "</div>",
            "</div>",
        ]
    )


def test_normalize_html_fragment_drops_blank_lines() -> None:
    """余分な空行を消しても、HTML の並び順は保たれることを確認する。"""
    raw = """

        <div>

          <p>Hello</p>

        </div>

    """

    # 空行だけを落とし、タグの順番までは崩さないことが大事。
    assert normalize_html_fragment(raw) == "<div>\n<p>Hello</p>\n</div>"
