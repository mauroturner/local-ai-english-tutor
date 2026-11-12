"""Pure layout maths for the resizable settings window."""

from __future__ import annotations


def content_padding(width: int, max_width: int = 640, min_pad: int = 16) -> int:
    """Horizontal padding that keeps a column at most ``max_width`` wide, centred.

    Never less than ``min_pad``; below ``max_width + 2 * min_pad`` the column simply
    fills the window.
    """
    return max(min_pad, -(-(width - max_width) // 2))
