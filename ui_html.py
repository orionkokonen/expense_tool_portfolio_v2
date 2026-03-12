"""Streamlit に渡す HTML 断片を整えるための小さな補助関数群。

見た目をそろえるために複数行文字列へインデントを入れることは多いが、
そのまま `st.markdown(..., unsafe_allow_html=True)` に渡すと、
Markdown 側が「HTML」ではなく「コード」として扱うことがある。
ここで余分な空白と空行を落としておくと、描画が安定する。
"""

from __future__ import annotations

from textwrap import dedent


def normalize_html_fragment(markup: str) -> str:
    """HTML 文字列の先頭空白を整え、コード表示への化けを防ぐ。

    `dedent()` で共通インデントを外し、その後 `strip()` で各行の
    左右の空白を落としている。これにより、テンプレート文字列を
    読みやすくインデントして書いても、表示時には素直な HTML になる。
    """
    return "\n".join(
        line.strip()
        for line in dedent(markup).splitlines()
        if line.strip()
    )
