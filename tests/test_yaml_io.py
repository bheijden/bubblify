"""Tests for load_geometry_specs_from_yaml / dump_geometries_to_yaml round-trip."""

from __future__ import annotations

import pytest
import yaml

from bubblify.core import (
    dump_geometries_to_yaml,
    GeometrySpec,
    GeometryStore,
    load_geometry_specs_from_yaml,
)


def _specs_by_link(specs):
    out = {}
    for s in specs:
        out.setdefault(s.link, []).append(s)
    return out


def test_roundtrip_preserves_all_fields(mixed_store, tmp_path):
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    specs = load_geometry_specs_from_yaml(path)

    assert len(specs) == len(mixed_store.by_id)
    by_link = _specs_by_link(specs)
    for g in mixed_store.by_id.values():
        matches = [s for s in by_link[g.link] if s.geometry_type == g.geometry_type and tuple(s.xyz) == tuple(g.local_xyz)]
        assert matches, f"no matching spec for geometry {g}"
        s = matches[0]
        if g.geometry_type == "sphere":
            assert s.radius == pytest.approx(g.radius)
            # sphere rpy is not written to YAML, spec defaults to (0,0,0)
            assert s.rpy == (0.0, 0.0, 0.0)
        elif g.geometry_type == "box":
            assert tuple(s.size) == tuple(g.size)
            assert tuple(s.rpy) == pytest.approx(tuple(g.local_rpy))
        elif g.geometry_type == "cylinder":
            assert s.cylinder_radius == pytest.approx(g.cylinder_radius)
            assert s.cylinder_height == pytest.approx(g.cylinder_height)
            assert tuple(s.rpy) == pytest.approx(tuple(g.local_rpy))


def test_empty_store_dumps_valid_yaml(tmp_path):
    path = tmp_path / "empty.yml"
    dump_geometries_to_yaml(GeometryStore(), path)
    specs = load_geometry_specs_from_yaml(path)
    assert specs == []


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_geometry_specs_from_yaml(tmp_path / "nope.yml")


def test_load_missing_top_level_key_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(yaml.safe_dump({"collision_spheres": {}}))
    with pytest.raises(ValueError, match="collision_geometries"):
        load_geometry_specs_from_yaml(path)


def test_load_unknown_type_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        yaml.safe_dump({"collision_geometries": {"l1": [{"center": [0, 0, 0], "type": "pyramid", "radius": 0.05}]}})
    )
    with pytest.raises(ValueError, match="pyramid"):
        load_geometry_specs_from_yaml(path)


def test_load_sphere_missing_radius_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(yaml.safe_dump({"collision_geometries": {"l1": [{"center": [0, 0, 0], "type": "sphere"}]}}))
    with pytest.raises(ValueError, match="radius"):
        load_geometry_specs_from_yaml(path)


def test_geometryspec_to_store_kwargs_omits_none():
    spec = GeometrySpec(link="l", xyz=(0, 0, 0), geometry_type="sphere", radius=0.1)
    kw = spec.to_store_kwargs()
    assert "radius" in kw
    assert "size" not in kw
    assert "cylinder_radius" not in kw
    assert "cylinder_height" not in kw


def test_dumped_yaml_has_no_legacy_collision_spheres_key(mixed_store, tmp_path):
    """Cleanup: collision_spheres double-write is gone; metadata drops total_spheres."""
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    raw = yaml.safe_load(path.read_text())
    assert "collision_geometries" in raw
    assert "collision_spheres" not in raw
    assert "total_spheres" not in raw["metadata"]
