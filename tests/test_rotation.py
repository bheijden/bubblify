"""Tests for rpy_to_quaternion / quaternion_to_rpy conversions."""

from __future__ import annotations

import math

import pytest

from bubblify.core import quaternion_to_rpy, rpy_to_quaternion


def _roundtrip_rpy(rpy):
    return quaternion_to_rpy(rpy_to_quaternion(rpy))


def test_zero_rotation_roundtrip():
    w, x, y, z = rpy_to_quaternion((0.0, 0.0, 0.0))
    assert (w, x, y, z) == pytest.approx((1.0, 0.0, 0.0, 0.0), abs=1e-12)
    assert _roundtrip_rpy((0.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0, 0.0), abs=1e-12)


@pytest.mark.parametrize("angle", [-math.pi / 2, -math.pi / 4, math.pi / 4, math.pi / 2 - 1e-3])
def test_single_axis_roundtrip_roll(angle):
    assert _roundtrip_rpy((angle, 0.0, 0.0))[0] == pytest.approx(angle, abs=1e-9)


@pytest.mark.parametrize("angle", [-math.pi / 2 + 1e-3, -math.pi / 4, math.pi / 4, math.pi / 2 - 1e-3])
def test_single_axis_roundtrip_pitch(angle):
    assert _roundtrip_rpy((0.0, angle, 0.0))[1] == pytest.approx(angle, abs=1e-9)


@pytest.mark.parametrize("angle", [-math.pi / 2, -math.pi / 4, math.pi / 4, math.pi / 2])
def test_single_axis_roundtrip_yaw(angle):
    assert _roundtrip_rpy((0.0, 0.0, angle))[2] == pytest.approx(angle, abs=1e-9)


def test_compound_roundtrip():
    rpy = (0.3, -0.5, 1.1)
    out = _roundtrip_rpy(rpy)
    for a, b in zip(rpy, out):
        assert a == pytest.approx(b, abs=1e-9)


def test_quaternion_unit_norm():
    for rpy in [(0.1, 0.2, 0.3), (-1.0, 0.5, 2.0), (math.pi / 3, -math.pi / 4, 0.0)]:
        w, x, y, z = rpy_to_quaternion(rpy)
        norm = math.sqrt(w * w + x * x + y * y + z * z)
        assert norm == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_gimbal_lock_pitch(sign):
    """pitch = ±π/2 enters gimbal lock; pitch should round-trip exactly, and
    roll/yaw decomposition may differ but pitch must be preserved."""
    pitch = sign * math.pi / 2
    out_pitch = _roundtrip_rpy((0.1, pitch, 0.2))[1]
    assert out_pitch == pytest.approx(pitch, abs=1e-9)
