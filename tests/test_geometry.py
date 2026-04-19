"""Tests for Geometry dataclass and its methods."""

from __future__ import annotations

import math

import pytest

from bubblify.core import Geometry


def test_geometry_defaults():
    g = Geometry(id=0, link="l", local_xyz=(0.0, 0.0, 0.0))
    assert g.geometry_type == "sphere"
    assert g.radius == 0.05
    assert g.size == (0.1, 0.1, 0.1)
    assert g.cylinder_radius == 0.05
    assert g.cylinder_height == 0.1
    assert g.display_as_capsule is False
    assert g.local_rpy == (0.0, 0.0, 0.0)
    assert g.local_wxyz == (1.0, 0.0, 0.0, 0.0)
    assert g.color == (255, 180, 60)
    assert g.node is None


def test_effective_radius_sphere():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0), geometry_type="sphere", radius=0.12)
    assert g.get_effective_radius() == pytest.approx(0.12)


def test_effective_radius_box_is_half_diagonal():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0), geometry_type="box", size=(0.2, 0.2, 0.2))
    expected = 0.5 * math.sqrt(0.2**2 * 3)
    assert g.get_effective_radius() == pytest.approx(expected)


def test_effective_radius_cylinder_uses_cylinder_radius():
    g = Geometry(
        id=0,
        link="l",
        local_xyz=(0, 0, 0),
        geometry_type="cylinder",
        cylinder_radius=0.08,
        cylinder_height=0.3,
    )
    assert g.get_effective_radius() == pytest.approx(0.08)


def test_update_quaternion_from_rpy_updates_wxyz():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0))
    g.update_quaternion_from_rpy((math.pi / 2, 0.0, 0.0))
    assert g.local_rpy == (math.pi / 2, 0.0, 0.0)
    w, x, y, z = g.local_wxyz
    assert w == pytest.approx(math.cos(math.pi / 4), abs=1e-12)
    assert x == pytest.approx(math.sin(math.pi / 4), abs=1e-12)
    assert y == pytest.approx(0.0, abs=1e-12)
    assert z == pytest.approx(0.0, abs=1e-12)


def test_update_rpy_from_quaternion_updates_rpy():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0))
    c = math.cos(math.pi / 4)
    s = math.sin(math.pi / 4)
    g.update_rpy_from_quaternion((c, 0.0, 0.0, s))
    roll, pitch, yaw = g.local_rpy
    assert roll == pytest.approx(0.0, abs=1e-12)
    assert pitch == pytest.approx(0.0, abs=1e-12)
    assert yaw == pytest.approx(math.pi / 2, abs=1e-12)
