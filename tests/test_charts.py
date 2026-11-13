"""Chart maths: where each value lands on the canvas."""

from __future__ import annotations

from english_tutor.ui.charts import scale_points


def test_nothing_to_draw():
    assert scale_points([], 200, 100) == []


def test_points_are_spread_left_to_right_and_the_highest_is_on_top():
    points = scale_points([1, 3, 2], 112, 62, pad=12)
    assert [x for x, _ in points] == [12.0, 56.0, 100.0]
    ys = [y for _, y in points]
    assert ys[1] == 12.0 and ys[0] == 50.0  # 3 is the top, 1 the bottom
    assert 12.0 < ys[2] < 50.0


def test_equal_values_run_through_the_middle():
    assert {y for _, y in scale_points([4, 4, 4], 100, 80, pad=10)} == {40.0}


def test_a_single_value_sits_in_the_middle():
    assert scale_points([7], 100, 80, pad=10) == [(50.0, 40.0)]


def test_a_tiny_box_never_divides_by_zero():
    assert len(scale_points([1, 2, 3], 4, 4, pad=12)) == 3
