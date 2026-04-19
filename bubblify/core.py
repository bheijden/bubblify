"""Core data structures and enhanced URDF visualizer for Bubblify."""

from __future__ import annotations

import dataclasses
import itertools
import warnings
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
import viser
import yourdfpy
from trimesh.scene import Scene
from viser import transforms as tf


# Type definitions for geometry types
GeometryType = Literal["sphere", "box", "cylinder"]

YAML_SCHEMA_VERSION = 1


@dataclasses.dataclass
class GeometrySpec:
    """YAML 解析后的一条几何配置，尚未分配 id / 挂接 viser node。

    Used on the load path: YAML -> List[GeometrySpec] -> caller turns each
    spec into a Geometry via store.add(spec.link, **spec.to_store_kwargs())
    and builds the viser visualization.

    Note: Geometry.display_as_capsule is not serialized (runtime-only
    display state), so GeometrySpec does not carry that field.
    """

    link: str
    xyz: Tuple[float, float, float]
    geometry_type: GeometryType
    rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    radius: Optional[float] = None
    size: Optional[Tuple[float, float, float]] = None
    cylinder_radius: Optional[float] = None
    cylinder_height: Optional[float] = None

    def to_store_kwargs(self) -> Dict[str, Any]:
        """Return kwargs suitable for GeometryStore.add (None values omitted)."""
        kwargs: Dict[str, Any] = {
            "xyz": self.xyz,
            "geometry_type": self.geometry_type,
            "rpy": self.rpy,
        }
        if self.radius is not None:
            kwargs["radius"] = self.radius
        if self.size is not None:
            kwargs["size"] = self.size
        if self.cylinder_radius is not None:
            kwargs["cylinder_radius"] = self.cylinder_radius
        if self.cylinder_height is not None:
            kwargs["cylinder_height"] = self.cylinder_height
        return kwargs


@dataclasses.dataclass
class Geometry:
    """Represents a collision geometry attached to a URDF link."""

    id: int
    link: str
    local_xyz: Tuple[float, float, float]
    geometry_type: GeometryType = "sphere"

    # Pose parameters (position and orientation)
    local_rpy: Tuple[float, float, float] = (
        0.0,
        0.0,
        0.0,
    )  # Roll, Pitch, Yaw in radians
    local_wxyz: Tuple[float, float, float, float] = (
        1.0,
        0.0,
        0.0,
        0.0,
    )  # Quaternion (w, x, y, z)

    # Sphere parameters
    radius: float = 0.05

    # Box parameters (length, width, height)
    size: Tuple[float, float, float] = (0.1, 0.1, 0.1)

    # Cylinder parameters
    cylinder_radius: float = 0.05
    cylinder_height: float = 0.1
    display_as_capsule: bool = False  # Whether to display cylinder as capsule

    # Visualization
    color: Tuple[int, int, int] = (255, 180, 60)
    node: Optional[viser.SceneNodeHandle] = dataclasses.field(default=None, repr=False)

    def get_effective_radius(self) -> float:
        """Get the effective radius for this geometry type (for compatibility)."""
        if self.geometry_type == "sphere":
            return self.radius
        elif self.geometry_type == "box":
            # Use half the diagonal of the box as effective radius
            return 0.5 * np.sqrt(self.size[0] ** 2 + self.size[1] ** 2 + self.size[2] ** 2)
        elif self.geometry_type == "cylinder":
            return self.cylinder_radius
        return self.radius

    def update_rpy_from_quaternion(self, wxyz: Tuple[float, float, float, float]):
        """Update RPY angles from quaternion."""
        self.local_wxyz = wxyz
        self.local_rpy = quaternion_to_rpy(wxyz)

    def update_quaternion_from_rpy(self, rpy: Tuple[float, float, float]):
        """Update quaternion from RPY angles."""
        self.local_rpy = rpy
        self.local_wxyz = rpy_to_quaternion(rpy)


# Rotation conversion utilities
def rpy_to_quaternion(
    rpy: Tuple[float, float, float],
) -> Tuple[float, float, float, float]:
    """Convert Roll-Pitch-Yaw angles to quaternion (w, x, y, z)."""
    roll, pitch, yaw = rpy

    # Convert to half angles
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)

    # Compute quaternion components
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return (w, x, y, z)


def quaternion_to_rpy(
    wxyz: Tuple[float, float, float, float],
) -> Tuple[float, float, float]:
    """Convert quaternion (w, x, y, z) to Roll-Pitch-Yaw angles."""
    w, x, y, z = wxyz

    # Roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if np.abs(sinp) >= 1:
        pitch = np.copysign(np.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        pitch = np.arcsin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    return (roll, pitch, yaw)


class GeometryStore:
    """Manages collection of collision geometries and their relationships to URDF links."""

    def __init__(self):
        self._next_id = itertools.count(0)
        self.by_id: Dict[int, Geometry] = {}
        self.ids_by_link: Dict[str, List[int]] = {}
        self.group_nodes: Dict[str, viser.FrameHandle] = {}  # /geometries/<link> parents

    def add(
        self,
        link: str,
        xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        geometry_type: GeometryType = "sphere",
        radius: float = 0.05,
        size: Tuple[float, float, float] = (0.1, 0.1, 0.1),
        cylinder_radius: float = 0.05,
        cylinder_height: float = 0.1,
        display_as_capsule: bool = False,
        rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        wxyz: Optional[Tuple[float, float, float, float]] = None,
    ) -> Geometry:
        """Add a new collision geometry to the specified link."""
        # Handle rotation parameters
        if wxyz is not None:
            # Use provided quaternion
            final_wxyz = wxyz
            final_rpy = quaternion_to_rpy(wxyz)
        else:
            # Use provided RPY or default
            final_rpy = rpy
            final_wxyz = rpy_to_quaternion(rpy)

        g = Geometry(
            id=next(self._next_id),
            link=link,
            local_xyz=xyz,
            geometry_type=geometry_type,
            local_rpy=final_rpy,
            local_wxyz=final_wxyz,
            radius=radius,
            size=size,
            cylinder_radius=cylinder_radius,
            cylinder_height=cylinder_height,
            display_as_capsule=display_as_capsule,
        )
        self.by_id[g.id] = g
        self.ids_by_link.setdefault(link, []).append(g.id)
        return g

    def remove(self, geometry_id: int) -> Optional[Geometry]:
        """Remove a geometry by ID."""
        if geometry_id not in self.by_id:
            return None

        geometry = self.by_id.pop(geometry_id)
        self.ids_by_link[geometry.link].remove(geometry_id)

        # Clean up empty link lists
        if not self.ids_by_link[geometry.link]:
            del self.ids_by_link[geometry.link]

        # Remove from scene
        if geometry.node is not None:
            try:
                geometry.node.remove()
            except Exception:
                # Node might already be removed, ignore the error
                pass
            finally:
                # Clear the reference
                geometry.node = None

        return geometry

    def get_geometries_for_link(self, link: str) -> List[Geometry]:
        """Get all geometries attached to a specific link."""
        return [self.by_id[gid] for gid in self.ids_by_link.get(link, [])]

    def clear(self):
        """Remove all geometries."""
        for geometry in list(self.by_id.values()):
            self.remove(geometry.id)


class EnhancedViserUrdf:
    """Enhanced URDF visualizer with per-link control capabilities.

    Extends the basic ViserUrdf functionality to provide:
    - Individual link visibility control
    - Direct access to link frames
    - Mesh node handles for fine-grained control
    """

    def __init__(
        self,
        target: viser.ViserServer | viser.ClientHandle,
        urdf_or_path: yourdfpy.URDF | Path,
        scale: float = 1.0,
        root_node_name: str = "/",
        mesh_color_override: (Tuple[float, float, float] | Tuple[float, float, float, float] | None) = None,
        collision_mesh_color_override: (Tuple[float, float, float] | Tuple[float, float, float, float] | None) = None,
        load_meshes: bool = True,
        load_collision_meshes: bool = False,
    ) -> None:
        """Initialize enhanced URDF visualizer."""
        assert root_node_name.startswith("/")
        assert len(root_node_name) == 1 or not root_node_name.endswith("/")

        if isinstance(urdf_or_path, Path):
            urdf = yourdfpy.URDF.load(
                urdf_or_path,
                build_scene_graph=load_meshes,
                build_collision_scene_graph=load_collision_meshes,
                load_meshes=load_meshes,
                load_collision_meshes=load_collision_meshes,
                filename_handler=partial(
                    yourdfpy.filename_handler_magic,
                    dir=urdf_or_path.parent,
                ),
            )
        else:
            urdf = urdf_or_path
        assert isinstance(urdf, yourdfpy.URDF)

        self._target = target
        self._urdf = urdf
        self._scale = scale
        self._root_node_name = root_node_name
        self._load_meshes = load_meshes
        self._collision_root_frame: viser.FrameHandle | None = None
        self._visual_root_frame: viser.FrameHandle | None = None
        self._joint_frames: List[viser.SceneNodeHandle] = []
        self._meshes: List[viser.SceneNodeHandle] = []

        # Enhanced functionality: per-link control
        self.link_frame: Dict[str, viser.FrameHandle] = {}
        self.link_meshes: Dict[str, List[viser.SceneNodeHandle]] = {}

        num_joints_to_repeat = 0
        if load_meshes:
            if urdf.scene is not None:
                num_joints_to_repeat += 1
                self._visual_root_frame = self._add_joint_frames_and_meshes(
                    urdf.scene,
                    root_node_name,
                    collision_geometry=False,
                    mesh_color_override=mesh_color_override,
                )
                self._index_scene(urdf.scene, collision=False)
            else:
                warnings.warn(
                    "load_meshes is enabled but the URDF model does not have a visual scene configured. Not displaying."
                )
        if load_collision_meshes:
            if urdf.collision_scene is not None:
                num_joints_to_repeat += 1
                self._collision_root_frame = self._add_joint_frames_and_meshes(
                    urdf.collision_scene,
                    root_node_name,
                    collision_geometry=True,
                    mesh_color_override=collision_mesh_color_override,
                )
                self._index_scene(urdf.collision_scene, collision=True)
            else:
                warnings.warn(
                    "load_collision_meshes is enabled but the URDF model does not have a collision scene configured. Not displaying."
                )

        self._joint_map_values = [*self._urdf.joint_map.values()] * num_joints_to_repeat

    def _index_scene(self, scene: Scene, collision: bool) -> None:
        """Index link frames and meshes for per-link control."""
        # Add the base frame explicitly (it's not a joint child, so gets missed otherwise)
        if not collision and self._visual_root_frame is not None:
            # The base link is the scene's base frame
            base_link = scene.graph.base_frame
            self.link_frame[base_link] = self._visual_root_frame
        elif collision and self._collision_root_frame is not None:
            base_link = scene.graph.base_frame
            self.link_frame[base_link] = self._collision_root_frame

        # Index joint frames (link frames) by matching joint child names
        joint_offset = len(self._joint_frames) - len(self._urdf.joint_map)
        for i, joint in enumerate(self._urdf.joint_map.values()):
            child = joint.child
            frame_index = joint_offset + i
            if frame_index < len(self._joint_frames):
                frame_handle = self._joint_frames[frame_index]
                if isinstance(frame_handle, viser.FrameHandle):
                    self.link_frame[child] = frame_handle

    @property
    def show_visual(self) -> bool:
        """Returns whether the visual meshes are currently visible."""
        return self._visual_root_frame is not None and self._visual_root_frame.visible

    @show_visual.setter
    def show_visual(self, visible: bool) -> None:
        """Set whether the visual meshes are currently visible."""
        if self._visual_root_frame is not None:
            self._visual_root_frame.visible = visible
        else:
            warnings.warn("Cannot set `.show_visual`, since no visual meshes were loaded.")

    @property
    def show_collision(self) -> bool:
        """Returns whether the collision meshes are currently visible."""
        return self._collision_root_frame is not None and self._collision_root_frame.visible

    @show_collision.setter
    def show_collision(self, visible: bool) -> None:
        """Set whether the collision meshes are currently visible."""
        if self._collision_root_frame is not None:
            self._collision_root_frame.visible = visible
        else:
            warnings.warn("Cannot set `.show_collision`, since no collision meshes were loaded.")

    def set_link_visible(self, link_name: str, visible: bool, which: str = "visual"):
        """Set visibility of a specific link's meshes."""
        if which in ("visual", "both") and self._load_meshes:
            for mesh_handle in self.link_meshes.get(link_name, []):
                mesh_handle.visible = visible
        if which in ("collision", "both") and self._collision_root_frame is not None:
            # Handle collision meshes if needed
            pass

    def remove(self) -> None:
        """Remove URDF from scene."""
        for frame in self._joint_frames:
            frame.remove()
        for mesh in self._meshes:
            mesh.remove()

    def update_cfg(self, configuration: np.ndarray) -> None:
        """Update the joint angles of the visualized URDF."""
        self._urdf.update_cfg(configuration)
        for joint, frame_handle in zip(self._joint_map_values, self._joint_frames):
            assert isinstance(joint, yourdfpy.Joint)
            T_parent_child = self._urdf.get_transform(joint.child, joint.parent, collision_geometry=not self._load_meshes)
            frame_handle.wxyz = tf.SO3.from_matrix(T_parent_child[:3, :3]).wxyz
            frame_handle.position = T_parent_child[:3, 3] * self._scale

    def get_actuated_joint_limits(self) -> dict[str, tuple[float | None, float | None]]:
        """Returns an ordered mapping from actuated joint names to position limits."""
        out: dict[str, tuple[float | None, float | None]] = {}
        for joint_name, joint in zip(self._urdf.actuated_joint_names, self._urdf.actuated_joints):
            assert isinstance(joint_name, str)
            assert isinstance(joint, yourdfpy.Joint)
            if joint.limit is None:
                out[joint_name] = (-np.pi, np.pi)
            else:
                out[joint_name] = (joint.limit.lower, joint.limit.upper)
        return out

    def get_actuated_joint_names(self) -> Tuple[str, ...]:
        """Returns a tuple of actuated joint names, in order."""
        return tuple(self._urdf.actuated_joint_names)

    def get_all_link_names(self) -> List[str]:
        """Get all link names in the URDF."""
        return list(self.link_frame.keys())

    def _add_joint_frames_and_meshes(
        self,
        scene: Scene,
        root_node_name: str,
        collision_geometry: bool,
        mesh_color_override: (Tuple[float, float, float] | Tuple[float, float, float, float] | None),
    ) -> viser.FrameHandle:
        """Helper function to add joint frames and meshes to the ViserUrdf object."""
        prefix = "collision" if collision_geometry else "visual"
        prefixed_root_node_name = (f"{root_node_name}/{prefix}").replace("//", "/")
        root_frame = self._target.scene.add_frame(prefixed_root_node_name, show_axes=False)

        # Add coordinate frame for each joint.
        for joint in self._urdf.joint_map.values():
            assert isinstance(joint, yourdfpy.Joint)
            self._joint_frames.append(
                self._target.scene.add_frame(
                    _viser_name_from_frame(
                        scene,
                        joint.child,
                        prefixed_root_node_name,
                    ),
                    show_axes=False,
                )
            )

        # Add the URDF's meshes/geometry to viser.
        for mesh_name, mesh in scene.geometry.items():
            assert isinstance(mesh, trimesh.Trimesh)
            T_parent_child = self._urdf.get_transform(
                mesh_name,
                scene.graph.transforms.parents[mesh_name],
                collision_geometry=collision_geometry,
            )
            name = _viser_name_from_frame(scene, mesh_name, prefixed_root_node_name)

            # Scale + transform the mesh. (these will mutate it!)
            mesh = mesh.copy()
            mesh.apply_scale(self._scale)
            mesh.apply_transform(T_parent_child)

            # Create the mesh handle and store it with the corresponding link
            mesh_handle = None
            if mesh_color_override is None:
                mesh_handle = self._target.scene.add_mesh_trimesh(name, mesh)
            elif len(mesh_color_override) == 3:
                mesh_handle = self._target.scene.add_mesh_simple(
                    name,
                    mesh.vertices,
                    mesh.faces,
                    color=mesh_color_override,
                )
            elif len(mesh_color_override) == 4:
                mesh_handle = self._target.scene.add_mesh_simple(
                    name,
                    mesh.vertices,
                    mesh.faces,
                    color=mesh_color_override[:3],
                    opacity=mesh_color_override[3],
                )
            else:
                raise ValueError("Invalid mesh_color_override format")

            # Store mesh handle and map it to the correct URDF link
            if mesh_handle is not None:
                self._meshes.append(mesh_handle)
                # Get the actual URDF link name that this mesh belongs to
                urdf_link_name = scene.graph.transforms.parents[mesh_name]
                self.link_meshes.setdefault(urdf_link_name, []).append(mesh_handle)
        return root_frame


def _viser_name_from_frame(
    scene: Scene,
    frame_name: str,
    root_node_name: str = "/",
) -> str:
    """Given the name of a frame in our URDF's kinematic tree, return a scene node name for viser."""
    assert root_node_name.startswith("/")
    assert len(root_node_name) == 1 or not root_node_name.endswith("/")

    frames = []
    while frame_name != scene.graph.base_frame:
        frames.append(frame_name)
        frame_name = scene.graph.transforms.parents[frame_name]
    if root_node_name != "/":
        frames.append(root_node_name)
    return "/".join(frames[::-1])


def inject_geometries_into_urdf_xml(original_urdf_path: Optional[Path], urdf_obj: yourdfpy.URDF, store: GeometryStore) -> str:
    """Inject collision geometries into URDF XML, replacing all existing collision elements."""
    if original_urdf_path is not None:
        root = ET.parse(original_urdf_path).getroot()
    else:
        # Reconstruct from urdf_obj using correct method
        root = ET.fromstring(urdf_obj.write_xml_string())

    # Map link name to element
    link_elems = {e.get("name"): e for e in root.findall("link")}

    # Remove ALL existing collision elements from ALL links (not just geometry links)
    for link_elem in link_elems.values():
        # Find and remove all collision elements
        collision_elems = link_elem.findall("collision")
        for collision_elem in collision_elems:
            link_elem.remove(collision_elem)

    # Add geometry collision elements
    for link_name, geometry_ids in store.ids_by_link.items():
        link_elem = link_elems.get(link_name)
        if link_elem is None:
            continue

        for geometry_id in geometry_ids:
            geometry = store.by_id[geometry_id]
            coll = ET.SubElement(
                link_elem,
                "collision",
                {"name": f"{geometry.geometry_type}_{geometry.id}"},
            )
            # Include RPY rotation in the origin element (spheres always have zero rotation)
            if geometry.geometry_type == "sphere":
                rpy_str = "0 0 0"
            else:
                rpy_str = f"{geometry.local_rpy[0]} {geometry.local_rpy[1]} {geometry.local_rpy[2]}"
            ET.SubElement(
                coll,
                "origin",
                {
                    "xyz": f"{geometry.local_xyz[0]} {geometry.local_xyz[1]} {geometry.local_xyz[2]}",
                    "rpy": rpy_str,
                },
            )
            geom = ET.SubElement(coll, "geometry")

            # Create appropriate geometry element based on type
            if geometry.geometry_type == "sphere":
                ET.SubElement(geom, "sphere", {"radius": f"{geometry.radius}"})
            elif geometry.geometry_type == "box":
                size_str = f"{geometry.size[0]} {geometry.size[1]} {geometry.size[2]}"
                ET.SubElement(geom, "box", {"size": size_str})
            elif geometry.geometry_type == "cylinder":
                ET.SubElement(
                    geom,
                    "cylinder",
                    {
                        "radius": f"{geometry.cylinder_radius}",
                        "length": f"{geometry.cylinder_height}",
                    },
                )

    # Pretty format the XML with proper indentation (Python 3.8 compatible)
    def indent_xml(elem, level=0, indent="  "):
        """Indent XML for pretty printing (Python 3.8 compatible)."""
        i = "\n" + level * indent
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + indent
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                indent_xml(child, level + 1, indent)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent_xml(root)

    # Add XML declaration and return
    xml_content = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + xml_content


def load_geometry_specs_from_yaml(path: Path) -> List[GeometrySpec]:
    """Read a YAML file and return a list of GeometrySpec.

    Only the new format (top-level `collision_geometries` key) is accepted.

    Raises:
        FileNotFoundError: file does not exist
        ValueError: missing `collision_geometries`, missing required fields,
                    or unknown `type`
    """
    import yaml

    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    if "collision_geometries" not in data:
        raise ValueError(f"YAML missing required top-level key 'collision_geometries': {path}")

    specs: List[GeometrySpec] = []
    for link_name, entries in (data["collision_geometries"] or {}).items():
        for entry in entries or []:
            specs.append(_parse_geometry_entry(link_name, entry))
    return specs


def _parse_geometry_entry(link: str, entry: Dict[str, Any]) -> GeometrySpec:
    """Parse a single YAML entry under collision_geometries into GeometrySpec."""
    if "center" not in entry:
        raise ValueError(f"link={link}: entry missing 'center'")
    if "type" not in entry:
        raise ValueError(f"link={link}: entry missing 'type'")

    geom_type = entry["type"]
    if geom_type not in ("sphere", "box", "cylinder"):
        raise ValueError(f"link={link}: unknown geometry type '{geom_type}'")

    xyz = tuple(entry["center"])
    rpy = tuple(entry.get("rpy", [0.0, 0.0, 0.0]))

    if geom_type == "sphere":
        if "radius" not in entry:
            raise ValueError(f"link={link}: sphere entry missing 'radius'")
        return GeometrySpec(
            link=link,
            xyz=xyz,
            geometry_type="sphere",
            rpy=rpy,
            radius=float(entry["radius"]),
        )
    if geom_type == "box":
        if "size" not in entry:
            raise ValueError(f"link={link}: box entry missing 'size'")
        return GeometrySpec(
            link=link,
            xyz=xyz,
            geometry_type="box",
            rpy=rpy,
            size=tuple(entry["size"]),
        )
    # cylinder
    if "radius" not in entry or "height" not in entry:
        raise ValueError(f"link={link}: cylinder entry missing 'radius' or 'height'")
    return GeometrySpec(
        link=link,
        xyz=xyz,
        geometry_type="cylinder",
        rpy=rpy,
        cylinder_radius=float(entry["radius"]),
        cylinder_height=float(entry["height"]),
    )


def dump_geometries_to_yaml(
    store: "GeometryStore",
    path: Path,
    *,
    include_metadata: bool = True,
) -> None:
    """Serialize a GeometryStore to YAML.

    Writes only the new-format `collision_geometries` key plus optional
    metadata. Old-format files that used only a legacy mirror key are no
    longer supported; re-export through the GUI to upgrade.
    """
    import time

    import yaml

    collision_geometries: Dict[str, List[Dict[str, Any]]] = {}
    for geometry in store.by_id.values():
        collision_geometries.setdefault(geometry.link, []).append(_geometry_to_yaml_entry(geometry))

    data: Dict[str, Any] = {
        "collision_geometries": collision_geometries,
    }

    if include_metadata:
        data["metadata"] = {
            "total_geometries": int(len(store.by_id)),
            "links": list(collision_geometries.keys()),
            "export_timestamp": float(time.time()),
            "schema_version": YAML_SCHEMA_VERSION,
        }

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _geometry_to_yaml_entry(geometry: Geometry) -> Dict[str, Any]:
    """Convert a single Geometry to a YAML entry dict."""
    center = geometry.local_xyz
    if hasattr(center, "tolist"):
        center = center.tolist()
    else:
        center = [float(x) for x in center]

    entry: Dict[str, Any] = {
        "center": center,
        "type": geometry.geometry_type,
    }
    if geometry.geometry_type != "sphere":
        entry["rpy"] = [float(r) for r in geometry.local_rpy]

    if geometry.geometry_type == "sphere":
        entry["radius"] = float(geometry.radius)
    elif geometry.geometry_type == "box":
        entry["size"] = [float(s) for s in geometry.size]
    elif geometry.geometry_type == "cylinder":
        entry["radius"] = float(geometry.cylinder_radius)
        entry["height"] = float(geometry.cylinder_height)
    return entry
