"""Tests for GeometryStore CRUD + index consistency."""

from __future__ import annotations

from bubblify.core import GeometryStore


def test_add_returns_geometry_with_matching_by_id():
    store = GeometryStore()
    g = store.add("link1", xyz=(0.1, 0, 0), geometry_type="sphere", radius=0.05)
    assert store.by_id[g.id] is g
    assert g.link == "link1"
    assert g.local_xyz == (0.1, 0, 0)
    assert g.radius == 0.05


def test_ids_are_monotonically_increasing():
    store = GeometryStore()
    ids = [store.add("l", xyz=(0, 0, 0), radius=0.05).id for _ in range(5)]
    assert ids == sorted(ids)
    assert len(set(ids)) == 5


def test_ids_by_link_tracks_membership():
    store = GeometryStore()
    a = store.add("l1", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l1", xyz=(0.1, 0, 0), radius=0.05)
    c = store.add("l2", xyz=(0, 0, 0), radius=0.05)
    assert store.ids_by_link["l1"] == [a.id, b.id]
    assert store.ids_by_link["l2"] == [c.id]


def test_remove_clears_indexes():
    store = GeometryStore()
    a = store.add("l1", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l1", xyz=(0.1, 0, 0), radius=0.05)
    removed = store.remove(a.id)
    assert removed is a
    assert a.id not in store.by_id
    assert store.ids_by_link["l1"] == [b.id]


def test_remove_last_in_link_drops_link_key():
    store = GeometryStore()
    g = store.add("lonely", xyz=(0, 0, 0), radius=0.05)
    store.remove(g.id)
    assert "lonely" not in store.ids_by_link


def test_remove_unknown_id_returns_none():
    store = GeometryStore()
    assert store.remove(9999) is None


def test_clear_empties_everything():
    store = GeometryStore()
    store.add("l1", xyz=(0, 0, 0), radius=0.05)
    store.add("l2", xyz=(0, 0, 0), radius=0.05)
    store.clear()
    assert store.by_id == {}
    assert store.ids_by_link == {}


def test_get_geometries_for_link_preserves_insertion_order():
    store = GeometryStore()
    a = store.add("l", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l", xyz=(0.1, 0, 0), radius=0.06)
    c = store.add("l", xyz=(0.2, 0, 0), radius=0.07)
    result = store.get_geometries_for_link("l")
    assert [g.id for g in result] == [a.id, b.id, c.id]


def test_get_geometries_for_unknown_link_returns_empty_list():
    store = GeometryStore()
    assert store.get_geometries_for_link("nope") == []
