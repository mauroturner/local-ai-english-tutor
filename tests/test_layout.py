"""content_padding: centre a capped-width column inside a resizable window."""

from __future__ import annotations

import pytest

from english_tutor.ui.layout import content_padding


@pytest.mark.parametrize(
    ("width", "expected"),
    [(0, 16), (300, 16), (500, 16), (640, 16), (672, 16), (700, 30), (900, 130), (1000, 180)],
)
def test_content_padding_defaults(width, expected):
    assert content_padding(width) == expected


def test_content_never_exceeds_the_maximum_width():
    for width in range(400, 1600, 37):
        pad = content_padding(width)
        assert width - 2 * pad <= 640


def test_custom_limits():
    assert content_padding(1000, max_width=400, min_pad=8) == 300
    assert content_padding(100, max_width=400, min_pad=8) == 8
