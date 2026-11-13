"""Pure maths for the small line charts of the Progress tab (no Tk needed)."""

from __future__ import annotations

from collections.abc import Sequence


def scale_points(
    values: Sequence[float], width: int, height: int, pad: int = 12
) -> list[tuple[float, float]]:
    """Canvas coordinates of ``values`` (oldest first) inside a ``width`` x ``height`` box.

    Points are spread evenly from left to right (a single point sits in the
    middle); the lowest value is drawn at the bottom and the highest at the
    top. When every value is equal the line runs through the middle. The
    vertical axis grows downwards, as on a canvas.
    """
    if not values:
        return []
    inner_w, inner_h = max(1, width - 2 * pad), max(1, height - 2 * pad)
    low, high = min(values), max(values)
    span = high - low
    count = len(values)
    points: list[tuple[float, float]] = []
    for i, value in enumerate(values):
        x = pad + (inner_w / 2 if count == 1 else inner_w * i / (count - 1))
        y = pad + (inner_h / 2 if span == 0 else inner_h * (1 - (value - low) / span))
        points.append((x, y))
    return points
