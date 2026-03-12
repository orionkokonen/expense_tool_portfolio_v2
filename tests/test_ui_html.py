from ui_html import normalize_html_fragment


def test_normalize_html_fragment_removes_leading_indentation() -> None:
    """行頭の空白が落ち、HTML がコード表示に化けないことを守る。"""
    raw = """
        <div class="bar-card">
          <h3>Monthly total</h3>
              <div class="bar-row">
                <div class="bar-label">2026-01</div>
                <div class="bar-value">2,781円</div>
              </div>
        </div>
    """

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

    assert normalize_html_fragment(raw) == "<div>\n<p>Hello</p>\n</div>"
