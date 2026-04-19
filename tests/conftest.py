"""Shared pytest fixtures for bubblify core tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bubblify.core import GeometryStore


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_urdf_path() -> Path:
    """Path to a real xarm6 URDF bundled in the repo."""
    path = REPO_ROOT / "assets" / "xarm6" / "xarm6_rs.urdf"
    assert path.exists(), f"fixture URDF missing: {path}"
    return path


@pytest.fixture
def mixed_store() -> GeometryStore:
    """GeometryStore pre-populated with 3 links, 3 geometry types, 6 entries."""
    store = GeometryStore()
    # link2: two spheres
    store.add("link2", xyz=(0.0, 0.0, 0.1), geometry_type="sphere", radius=0.06)
    store.add("link2", xyz=(0.0, -0.07, 0.1), geometry_type="sphere", radius=0.06)
    # link3: one box (with non-zero rpy), one cylinder
    store.add(
        "link3",
        xyz=(0.1, 0.0, 0.0),
        geometry_type="box",
        size=(0.1, 0.1, 0.1),
        rpy=(0.2, 0.3, 0.4),
    )
    store.add(
        "link3",
        xyz=(0.0, 0.0, 0.2),
        geometry_type="cylinder",
        cylinder_radius=0.03,
        cylinder_height=0.15,
        rpy=(0.0, 0.0, 0.5),
    )
    # link_base: one sphere, one box
    store.add("link_base", xyz=(0.0, 0.0, 0.0), geometry_type="sphere", radius=0.05)
    store.add(
        "link_base",
        xyz=(0.1, 0.1, 0.0),
        geometry_type="box",
        size=(0.05, 0.05, 0.05),
    )
    return store
