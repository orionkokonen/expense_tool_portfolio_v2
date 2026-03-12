from __future__ import annotations

from textwrap import dedent


def normalize_html_fragment(markup: str) -> str:
    """Remove template indentation so Streamlit doesn't render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).splitlines()
        if line.strip()
    )
