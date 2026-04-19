"""Tests for inject_geometries_into_urdf_xml."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
import yourdfpy

from bubblify.core import GeometryStore, inject_geometries_into_urdf_xml


@pytest.fixture
def loaded_urdf(sample_urdf_path):
    return yourdfpy.URDF.load(
        str(sample_urdf_path),
        build_scene_graph=False,
        load_meshes=False,
    )


def _inject(sample_urdf_path, urdf, store):
    return inject_geometries_into_urdf_xml(sample_urdf_path, urdf, store)


def test_output_is_parseable_urdf(sample_urdf_path, loaded_urdf, mixed_store, tmp_path):
    xml = _inject(sample_urdf_path, loaded_urdf, mixed_store)
    out = tmp_path / "out.urdf"
    out.write_text(xml)
    reloaded = yourdfpy.URDF.load(str(out), build_scene_graph=False, load_meshes=False)
    assert reloaded is not None


def test_all_existing_collisions_replaced(sample_urdf_path, loaded_urdf, mixed_store):
    xml = _inject(sample_urdf_path, loaded_urdf, mixed_store)
    root = ET.fromstring(xml)
    collision_count = sum(len(link.findall("collision")) for link in root.findall("link"))
    link_names = {link.get("name") for link in root.findall("link")}
    expected = sum(1 for g in mixed_store.by_id.values() if g.link in link_names)
    assert collision_count == expected


def test_sphere_rpy_is_zero_even_if_store_has_nonzero(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    store.add(
        "link2",
        xyz=(0.0, 0.0, 0.05),
        geometry_type="sphere",
        radius=0.03,
        rpy=(0.5, 0.6, 0.7),
    )
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    root = ET.fromstring(xml)
    link2 = next(link for link in root.findall("link") if link.get("name") == "link2")
    origin = link2.find("collision/origin")
    assert origin is not None
    assert origin.get("rpy") == "0 0 0"


def test_box_and_cylinder_rpy_passthrough(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    store.add(
        "link2",
        xyz=(0, 0, 0),
        geometry_type="box",
        size=(0.1, 0.1, 0.1),
        rpy=(0.1, 0.2, 0.3),
    )
    store.add(
        "link3",
        xyz=(0, 0, 0),
        geometry_type="cylinder",
        cylinder_radius=0.05,
        cylinder_height=0.1,
        rpy=(0.4, 0.5, 0.6),
    )
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    root = ET.fromstring(xml)
    link2 = next(link for link in root.findall("link") if link.get("name") == "link2")
    link3 = next(link for link in root.findall("link") if link.get("name") == "link3")
    assert link2.find("collision/origin").get("rpy") == "0.1 0.2 0.3"
    assert link3.find("collision/origin").get("rpy") == "0.4 0.5 0.6"


def test_unknown_link_is_skipped_silently(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    store.add("totally_not_a_link", xyz=(0, 0, 0), radius=0.05)
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    root = ET.fromstring(xml)
    total_collisions = sum(len(link.findall("collision")) for link in root.findall("link"))
    assert total_collisions == 0
