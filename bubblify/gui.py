"""Interactive GUI application for URDF geometry configuration using Viser."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import viser
import yourdfpy
from robot_descriptions.loaders.yourdfpy import load_robot_description

from .core import (
    EnhancedViserUrdf,
    Geometry,
    GeometryStore,
    inject_geometries_into_urdf_xml,
)


class BubblifyApp:
    """Main application class for interactive URDF geometry configuration."""

    def __init__(
        self,
        robot_name: str = "panda",
        urdf_path: Optional[Path] = None,
        show_collision: bool = False,
        port: int = 8080,
        geometry_config: Optional[Path] = None,
    ):
        """Initialize the Bubblify application.

        Args:
            robot_name: Name of robot from robot_descriptions (used if urdf_path is None)
            urdf_path: Path to custom URDF file
            show_collision: Whether to show collision meshes
            port: Viser server port
            geometry_config: Path to existing geometry configuration YAML file to load
        """
        self.server = viser.ViserServer(port=port)
        self.show_collision = show_collision

        # Load URDF
        if urdf_path is not None:
            self.urdf = yourdfpy.URDF.load(
                str(urdf_path),  # urdf_path,
                build_scene_graph=True,
                load_meshes=True,
                build_collision_scene_graph=show_collision,
                load_collision_meshes=show_collision,
            )
            self.urdf_path = urdf_path
        else:
            self.urdf = load_robot_description(
                robot_name + "_description",
                load_meshes=True,
                build_scene_graph=True,
                load_collision_meshes=show_collision,
                build_collision_scene_graph=show_collision,
            )
            self.urdf_path = None

        # Enhanced URDF visualizer with per-link control
        self.urdf_viz = EnhancedViserUrdf(
            self.server,
            urdf_or_path=self.urdf,
            load_meshes=True,
            load_collision_meshes=show_collision,
            collision_mesh_color_override=(1.0, 0.0, 0.0, 0.4),
        )

        # Geometry management
        self.geometry_store = GeometryStore()

        # GUI state
        self.current_geometry_id: Optional[int] = None
        self.current_link: str = ""
        self.joint_sliders: List[viser.GuiInputHandle[float]] = []
        self.transform_control: Optional[viser.TransformControlsHandle] = None
        self.radius_gizmo: Optional[viser.TransformControlsHandle] = None

        # Box resize gizmos (one for each axis: X, Y, Z)
        self.box_resize_gizmos: Dict[str, viser.TransformControlsHandle] = {}
        # Cylinder height gizmos (for Z-axis height adjustment)
        self.cylinder_height_gizmos: Dict[str, viser.TransformControlsHandle] = {}

        # GUI control references for syncing
        self._link_dropdown = None
        self._current_link_dropdown = None
        self._geometry_dropdown = None
        self._geometry_type_dropdown = None
        self._sphere_radius_slider = None
        self._box_size_sliders = None
        self._cylinder_radius_slider = None
        self._cylinder_height_slider = None
        self._geometry_color_input = None

        # Flag to prevent recursive updates
        self._updating_geometry_ui = False

        # Visibility settings
        self.show_selected_link: bool = True
        self.show_other_links: bool = True

        # Geometry opacity settings for visual focus system
        self.selected_geometry_opacity: float = 1.0
        self.unselected_geometries_opacity: float = 0.5
        self.other_links_geometries_opacity: float = 0.2

        # Create geometry root frame
        self.geometries_root = self.server.scene.add_frame("/geometries", show_axes=False)

        # Setup GUI
        self._setup_robot_controls()
        self._setup_visibility_controls()
        self._setup_geometry_controls()
        self._setup_export_controls()

        # Add a grid for reference
        self._add_reference_grid()

        # Initialize visibility states
        self._update_mesh_visibility()

        # Load geometry configuration YAML if provided
        if geometry_config is not None:
            self._load_geometry_config_yaml(geometry_config)

        print(f"🎯 Bubblify server running at http://localhost:{port}")
        print("Use the GUI controls to add and edit collision geometries!")

    def _setup_robot_controls(self):
        """Setup robot configuration and visibility controls."""
        with self.server.gui.add_folder("🤖 Robot Controls"):
            # Joint sliders
            initial_config = []

            for joint_name, (
                lower,
                upper,
            ) in self.urdf_viz.get_actuated_joint_limits().items():
                lower = lower if lower is not None else -np.pi
                upper = upper if upper is not None else np.pi
                initial_pos = 0.0 if lower < -0.1 and upper > 0.1 else (lower + upper) / 2.0

                slider = self.server.gui.add_slider(
                    label=joint_name,
                    min=lower,
                    max=upper,
                    step=1e-3,
                    initial_value=initial_pos,
                )
                self.joint_sliders.append(slider)
                initial_config.append(initial_pos)

            # Connect sliders to URDF update
            def update_robot_config():
                config = np.array([s.value for s in self.joint_sliders])
                self.urdf_viz.update_cfg(config)

            for slider in self.joint_sliders:
                slider.on_update(lambda _: update_robot_config())

            # Apply initial configuration
            update_robot_config()

            # Reset button
            reset_joints_btn = self.server.gui.add_button("🏠 Reset to Home")

            @reset_joints_btn.on_click
            def _(_):
                for slider, init_val in zip(self.joint_sliders, initial_config):
                    slider.value = init_val

    def _setup_visibility_controls(self):
        """Setup visibility controls in separate section."""
        with self.server.gui.add_folder("👁️ Visibility Controls"):
            # Current link dropdown
            all_links = self.urdf_viz.get_all_link_names()
            if not all_links:
                all_links = ["base_link"]
            current_link_dropdown = self.server.gui.add_dropdown("Current Link", options=all_links, initial_value=all_links[0])

            # Mesh visibility toggles
            show_selected_link_cb = self.server.gui.add_checkbox("Show Selected Link", initial_value=self.show_selected_link)
            show_other_links_cb = self.server.gui.add_checkbox("Show Other Links", initial_value=self.show_other_links)

            # Geometry opacity controls for visual focus system
            selected_geometry_opacity = self.server.gui.add_slider(
                "Current Geometry",
                min=0.0,
                max=1.0,
                step=0.1,
                initial_value=self.selected_geometry_opacity,
            )
            unselected_geometries_opacity = self.server.gui.add_slider(
                "Other Geometries (Same Link)",
                min=0.0,
                max=1.0,
                step=0.1,
                initial_value=self.unselected_geometries_opacity,
            )
            other_links_geometries_opacity = self.server.gui.add_slider(
                "Geometries (Other Links)",
                min=0.0,
                max=1.0,
                step=0.1,
                initial_value=self.other_links_geometries_opacity,
            )

            # Store references for updates
            self._current_link_dropdown = current_link_dropdown

            # Set initial current link from dropdown
            self.current_link = current_link_dropdown.value

            @current_link_dropdown.on_update
            def _(_):
                self.current_link = current_link_dropdown.value
                self._sync_link_selection()
                self._update_mesh_visibility()

            @show_selected_link_cb.on_update
            def _(_):
                self.show_selected_link = show_selected_link_cb.value
                self._update_mesh_visibility()

            @show_other_links_cb.on_update
            def _(_):
                self.show_other_links = show_other_links_cb.value
                self._update_mesh_visibility()

            @selected_geometry_opacity.on_update
            def _(_):
                self.selected_geometry_opacity = selected_geometry_opacity.value
                self._update_geometry_opacities()

            @unselected_geometries_opacity.on_update
            def _(_):
                self.unselected_geometries_opacity = unselected_geometries_opacity.value
                self._update_geometry_opacities()

            @other_links_geometries_opacity.on_update
            def _(_):
                self.other_links_geometries_opacity = other_links_geometries_opacity.value
                self._update_geometry_opacities()

    def _setup_geometry_controls(self):
        """Setup geometry creation and editing controls."""
        with self.server.gui.add_folder("🔶 Geometry Editor"):
            # Get links for dropdown
            all_links = self.urdf_viz.get_all_link_names()
            if not all_links:
                all_links = ["base_link"]

            # Link selection
            link_dropdown = self.server.gui.add_dropdown("Link", options=all_links, initial_value=all_links[0])
            self.current_link = link_dropdown.value
            self._link_dropdown = link_dropdown  # Store reference for syncing

            # Geometry type selection
            geometry_type_dropdown = self.server.gui.add_dropdown(
                "Geometry Type",
                options=["sphere", "box", "cylinder"],
                initial_value="sphere",
            )
            self._geometry_type_dropdown = geometry_type_dropdown

            # Geometry selection dropdown (will be populated based on selected link)
            geometry_dropdown = self.server.gui.add_dropdown("Geometry", options=["None"], initial_value="None")
            self._geometry_dropdown = geometry_dropdown  # Store reference

            # Geometry creation and deletion
            add_geometry_btn = self.server.gui.add_button("➕ Add Geometry")
            delete_geometry_btn = self.server.gui.add_button("🗑️ Delete Selected")

            # Geometry statistics
            self.server.gui.add_text("Total Geometries", initial_value="0")
            self.server.gui.add_text("Geometries on Current Link", initial_value="0")

            # Geometry properties - Sphere
            with self.server.gui.add_folder("⚪ Sphere Properties", expand_by_default=True):
                sphere_radius = self.server.gui.add_slider("Radius", min=0.005, max=0.14, step=0.001, initial_value=0.05)
                self._sphere_radius_slider = sphere_radius

            # Geometry properties - Box
            with self.server.gui.add_folder("📦 Box Properties", expand_by_default=False):
                box_length = self.server.gui.add_slider("Length", min=0.01, max=0.5, step=0.001, initial_value=0.1)
                box_width = self.server.gui.add_slider("Width", min=0.01, max=0.5, step=0.001, initial_value=0.1)
                box_height = self.server.gui.add_slider("Height", min=0.01, max=0.5, step=0.001, initial_value=0.1)
                self._box_size_sliders = (box_length, box_width, box_height)

            # Geometry properties - Cylinder
            with self.server.gui.add_folder("🥫 Cylinder Properties", expand_by_default=False):
                cylinder_radius = self.server.gui.add_slider("Radius", min=0.005, max=0.14, step=0.001, initial_value=0.05)
                cylinder_height = self.server.gui.add_slider("Height", min=0.01, max=0.5, step=0.001, initial_value=0.1)
                # Capsule display option
                cylinder_as_capsule = self.server.gui.add_checkbox("Display as Capsule", initial_value=False)
                self.server.gui.add_markdown("⚠️ Capsule 仅用于显示，导出 URDF 时按 cylinder 处理")
                self._cylinder_radius_slider = cylinder_radius
                self._cylinder_height_slider = cylinder_height
                self._cylinder_as_capsule_checkbox = cylinder_as_capsule

            # Common properties
            geometry_color = self.server.gui.add_rgb("Color", initial_value=(255, 180, 60))
            self._geometry_color_input = geometry_color

            # Rotation properties
            with self.server.gui.add_folder("🔄 Rotation Properties", expand_by_default=False):
                roll_slider = self.server.gui.add_slider("Roll (X)", min=-3.14159, max=3.14159, step=0.01, initial_value=0.0)
                pitch_slider = self.server.gui.add_slider("Pitch (Y)", min=-3.14159, max=3.14159, step=0.01, initial_value=0.0)
                yaw_slider = self.server.gui.add_slider("Yaw (Z)", min=-3.14159, max=3.14159, step=0.01, initial_value=0.0)
                self._rpy_sliders = (roll_slider, pitch_slider, yaw_slider)

            def update_geometry_dropdown():
                """Update geometry dropdown based on selected link."""
                link_name = link_dropdown.value
                self.current_link = link_name
                geometries = self.geometry_store.get_geometries_for_link(link_name)

                if geometries:
                    options = [f"{g.geometry_type.title()} {g.id}" for g in geometries]
                    geometry_dropdown.options = options

                    # Determine which geometry to select
                    geometry_to_select = None
                    if self.current_geometry_id is not None:
                        # Try to keep current selection if it's still valid for this link
                        current_geometry = self.geometry_store.by_id.get(self.current_geometry_id)
                        if current_geometry and current_geometry.link == link_name:
                            geometry_to_select = current_geometry

                    # If no valid current selection, select the first geometry
                    if geometry_to_select is None:
                        geometry_to_select = geometries[0]

                    # Update both dropdown and current_geometry_id
                    geometry_dropdown.value = f"{geometry_to_select.geometry_type.title()} {geometry_to_select.id}"
                    self.current_geometry_id = geometry_to_select.id
                else:
                    geometry_dropdown.options = ["None"]
                    geometry_dropdown.value = "None"
                    self.current_geometry_id = None

                self._update_transform_control()
                self._update_radius_gizmo()
                self._update_box_resize_gizmos()
                self._update_cylinder_height_gizmos()
                self._update_geometry_properties_ui()
                self._update_geometry_opacities()
                self._update_mesh_visibility()

            def update_selected_geometry():
                """Update selected geometry ID from dropdown and switch link context."""
                if geometry_dropdown.value != "None":
                    geometry_id = int(geometry_dropdown.value.split()[-1])
                    self.current_geometry_id = geometry_id

                    # Get the geometry and switch to its link
                    if geometry_id in self.geometry_store.by_id:
                        geometry = self.geometry_store.by_id[geometry_id]
                        # Update the link context and sync dropdowns
                        if geometry.link != self.current_link:
                            self.current_link = geometry.link
                            link_dropdown.value = geometry.link
                            self._sync_link_selection()
                            self._update_mesh_visibility()

                    self._update_transform_control()
                    self._update_radius_gizmo()
                    self._update_box_resize_gizmos()
                    self._update_cylinder_height_gizmos()
                    self._update_geometry_properties_ui()
                    self._update_geometry_opacities()
                else:
                    self.current_geometry_id = None
                    self._remove_transform_control()

            @link_dropdown.on_update
            def _(_):
                self.current_link = link_dropdown.value
                self._sync_link_selection()
                self._update_mesh_visibility()
                update_geometry_dropdown()

            @geometry_dropdown.on_update
            def _(_):
                update_selected_geometry()

            @add_geometry_btn.on_click
            def _(_):
                """Add a new geometry to the selected link using current parameters."""
                link_name = link_dropdown.value
                geometry_type = geometry_type_dropdown.value

                # Get current parameters based on geometry type
                # For new geometries, use default values instead of current slider values
                # to avoid inheriting properties from previously selected geometry
                if geometry_type == "sphere":
                    geometry = self.geometry_store.add(
                        link_name,
                        xyz=(0.0, 0.0, 0.0),
                        geometry_type="sphere",
                        radius=sphere_radius.value,
                    )
                elif geometry_type == "box":
                    geometry = self.geometry_store.add(
                        link_name,
                        xyz=(0.0, 0.0, 0.0),
                        geometry_type="box",
                        size=(0.1, 0.1, 0.1),  # Default size instead of slider values
                    )
                elif geometry_type == "cylinder":
                    geometry = self.geometry_store.add(
                        link_name,
                        xyz=(0.0, 0.0, 0.0),
                        geometry_type="cylinder",
                        cylinder_radius=0.05,  # Default radius
                        cylinder_height=0.1,  # Default height
                    )

                self._create_geometry_visualization(geometry)

                # Select the new geometry as current
                self.current_geometry_id = geometry.id

                # Update dropdown and controls immediately
                update_geometry_dropdown()

                # Directly call the control update methods to show gizmo immediately
                self._update_transform_control()
                self._update_radius_gizmo()
                self._update_box_resize_gizmos()
                self._update_cylinder_height_gizmos()
                self._update_geometry_properties_ui()
                self._update_geometry_opacities()

            @delete_geometry_btn.on_click
            def _(_):
                """Delete the selected geometry."""
                if self.current_geometry_id is not None:
                    self.geometry_store.remove(self.current_geometry_id)
                    self.current_geometry_id = None
                    self._remove_transform_control()
                    update_geometry_dropdown()

            def update_geometry_properties():
                """Update geometry properties from UI."""
                # Skip update if we're currently updating the UI to prevent recursive changes
                if self._updating_geometry_ui:
                    return

                if self.current_geometry_id is not None and self.current_geometry_id in self.geometry_store.by_id:
                    geometry = self.geometry_store.by_id[self.current_geometry_id]

                    # Update properties based on geometry type
                    if geometry.geometry_type == "sphere":
                        geometry.radius = float(sphere_radius.value)
                    elif geometry.geometry_type == "box":
                        geometry.size = (
                            box_length.value,
                            box_width.value,
                            box_height.value,
                        )
                    elif geometry.geometry_type == "cylinder":
                        geometry.cylinder_radius = float(cylinder_radius.value)
                        geometry.cylinder_height = float(cylinder_height.value)
                        geometry.display_as_capsule = bool(cylinder_as_capsule.value)

                    # Update rotation properties only for non-sphere geometries
                    if geometry.geometry_type != "sphere":
                        new_rpy = (
                            self._rpy_sliders[0].value,  # roll
                            self._rpy_sliders[1].value,  # pitch
                            self._rpy_sliders[2].value,  # yaw
                        )
                        geometry.update_quaternion_from_rpy(new_rpy)

                        # Update transform control if active
                        if self.transform_control is not None:
                            self.transform_control.wxyz = geometry.local_wxyz

                    # Update common properties
                    geometry.color = tuple(int(c) for c in geometry_color.value)
                    self._update_geometry_visualization(geometry)
                    self._update_radius_gizmo()
                    self._update_box_resize_gizmos()
                    self._update_cylinder_height_gizmos()

            # Connect all property sliders to update function
            sphere_radius.on_update(lambda _: update_geometry_properties())
            box_length.on_update(lambda _: update_geometry_properties())
            box_width.on_update(lambda _: update_geometry_properties())
            box_height.on_update(lambda _: update_geometry_properties())
            cylinder_radius.on_update(lambda _: update_geometry_properties())
            cylinder_height.on_update(lambda _: update_geometry_properties())
            cylinder_as_capsule.on_update(lambda _: update_geometry_properties())
            geometry_color.on_update(lambda _: update_geometry_properties())
            # Connect rotation sliders (will only affect non-sphere geometries)
            roll_slider.on_update(lambda _: update_geometry_properties())
            pitch_slider.on_update(lambda _: update_geometry_properties())
            yaw_slider.on_update(lambda _: update_geometry_properties())

            # Initialize
            update_geometry_dropdown()

            # Set up initial opacity state
            self._update_geometry_opacities()

    def _setup_export_controls(self):
        """Setup export functionality."""
        with self.server.gui.add_folder("💾 Export"):
            # Get default export names based on URDF
            default_name = "geometries"
            if self.urdf_path and self.urdf_path.stem:
                default_name = f"{self.urdf_path.stem}_geometries"

            # Export name configuration (no paths, just filenames)
            export_name_input = self.server.gui.add_text("Export Name", initial_value=default_name)

            # Export options
            export_yml_btn = self.server.gui.add_button("Export Geometries (YAML)")
            export_urdf_btn = self.server.gui.add_button("Export URDF with Geometries")

            # Status with error details (read-only)
            export_status = self.server.gui.add_markdown("Ready to export")
            export_details = self.server.gui.add_markdown("")

            @export_yml_btn.on_click
            def _(_):
                """Export geometry configuration to YAML."""
                try:
                    # Determine output directory (same as URDF or cwd)
                    if self.urdf_path and self.urdf_path.parent:
                        output_dir = self.urdf_path.parent
                    else:
                        output_dir = Path.cwd()
                    output_path = output_dir / f"{export_name_input.value}.yml"

                    from .core import dump_geometries_to_yaml

                    dump_geometries_to_yaml(self.geometry_store, output_path)

                    export_status.content = f"✅ Exported {len(self.geometry_store.by_id)} geometries"
                    export_details.content = f"Saved to: {output_path.name}"
                    print(f"Exported geometry configuration to {output_path.absolute()}")
                except Exception as e:
                    export_status.content = f"❌ Export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"Export failed: {e}")

            @export_urdf_btn.on_click
            def _(_):
                """Export URDF with collision geometries."""
                try:
                    urdf_xml = inject_geometries_into_urdf_xml(self.urdf_path, self.urdf, self.geometry_store)

                    # Determine output directory (same as URDF or current working directory)
                    if self.urdf_path and self.urdf_path.parent:
                        output_dir = self.urdf_path.parent
                    else:
                        output_dir = Path.cwd()

                    output_path = output_dir / f"{export_name_input.value}.urdf"
                    output_path.write_text(urdf_xml)
                    export_status.content = f"✅ Exported URDF with {len(self.geometry_store.by_id)} geometries"
                    export_details.content = f"Saved to: {output_path.name}"
                    print(f"Exported URDF with geometries to {output_path.absolute()}")

                except Exception as e:
                    export_status.content = f"❌ URDF export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"URDF export failed: {e}")

    def _create_geometry_visualization(self, geometry: Geometry):
        """Create or update the 3D visualization for a geometry."""
        # Ensure link group exists
        if geometry.link not in self.geometry_store.group_nodes:
            # Get the link frame from enhanced URDF
            link_frame = self.urdf_viz.link_frame.get(geometry.link)
            if link_frame is not None:
                self.geometry_store.group_nodes[geometry.link] = self.server.scene.add_frame(
                    f"{link_frame.name}/geometries", show_axes=False
                )
            else:
                # Fallback: create under geometries root
                self.geometry_store.group_nodes[geometry.link] = self.server.scene.add_frame(
                    f"/geometries/{geometry.link}", show_axes=False
                )

        parent_frame = self.geometry_store.group_nodes[geometry.link]

        # Create geometry visualization with appropriate opacity
        opacity = self._get_geometry_opacity(geometry)

        # Create different geometry types
        if geometry.geometry_type == "sphere":
            # Spheres don't need rotation (they are symmetric)
            geometry.node = self.server.scene.add_icosphere(
                f"{parent_frame.name}/sphere_{geometry.id}",
                radius=geometry.radius,
                color=geometry.color,
                position=geometry.local_xyz,
                opacity=opacity,
                visible=True,
            )
        elif geometry.geometry_type == "box":
            geometry.node = self.server.scene.add_box(
                f"{parent_frame.name}/box_{geometry.id}",
                dimensions=geometry.size,
                color=geometry.color,
                position=geometry.local_xyz,
                wxyz=geometry.local_wxyz,  # Add rotation
                opacity=opacity,
                visible=True,
            )
        elif geometry.geometry_type == "cylinder":
            # Viser doesn't have add_cylinder, so we'll create a cylinder mesh using trimesh
            import trimesh

            if geometry.display_as_capsule:
                # Create a capsule using Trimesh's built-in capsule method
                # This is more efficient and creates a proper capsule mesh
                final_mesh = trimesh.creation.capsule(
                    height=geometry.cylinder_height,
                    radius=geometry.cylinder_radius,
                    count=[32, 32],  # [latitude, longitude] sections for smooth surface
                )
            else:
                # Create a regular cylinder mesh with more sections for smoother appearance
                final_mesh = trimesh.creation.cylinder(
                    radius=geometry.cylinder_radius,
                    height=geometry.cylinder_height,
                    sections=32,  # More sections for smoother cylinder surface
                )

            # Use add_mesh_simple to support opacity parameter
            geometry.node = self.server.scene.add_mesh_simple(
                f"{parent_frame.name}/{'capsule' if geometry.display_as_capsule else 'cylinder'}_{geometry.id}",
                vertices=final_mesh.vertices,
                faces=final_mesh.faces,
                color=geometry.color,  # RGB tuple (0-255)
                opacity=opacity,
                position=geometry.local_xyz,
                wxyz=geometry.local_wxyz,  # Add rotation
                visible=True,
            )

        # Make geometry clickable for selection
        @geometry.node.on_click
        def _(_):
            # Set geometry ID FIRST, before any other updates
            self.current_geometry_id = geometry.id
            old_link = self.current_link
            self.current_link = geometry.link

            # If we switched links, we need to update dropdowns carefully
            if old_link != self.current_link:
                self._sync_link_selection()
                # IMPORTANT: Don't call update_geometry_dropdown here as it will override our selection
                # Instead, manually update the geometry dropdown after link sync
                if self._geometry_dropdown:
                    geometries = self.geometry_store.get_geometries_for_link(self.current_link)
                    if geometries:
                        options = [f"{g.geometry_type.title()} {g.id}" for g in geometries]
                        self._geometry_dropdown.options = options
                    self._sync_geometry_selection()
            else:
                # Same link, just update geometry selection
                self._sync_geometry_selection()

            # Update visuals and UI
            self._update_transform_control()
            self._update_radius_gizmo()
            self._update_box_resize_gizmos()
            self._update_cylinder_height_gizmos()
            self._update_geometry_opacities()
            self._update_mesh_visibility()
            self._update_geometry_properties_ui()

    def _update_geometry_visualization(self, geometry: Geometry):
        """Update existing geometry visualization."""
        if geometry.node is not None:
            try:
                # Remove old node
                geometry.node.remove()
            except Exception:
                # Node might already be removed, ignore the error
                pass
            finally:
                # Clear the reference regardless
                geometry.node = None

        # Recreate with new properties
        self._create_geometry_visualization(geometry)

    def _update_transform_control(self):
        """Update transform control for the currently selected geometry."""
        if self.current_geometry_id is not None and self.current_geometry_id in self.geometry_store.by_id:
            geometry = self.geometry_store.by_id[self.current_geometry_id]

            # Remove existing transform control
            self._remove_transform_control()

            # Get the parent frame for this geometry
            parent_frame = self.geometry_store.group_nodes.get(geometry.link)
            if parent_frame is not None:
                control_name = f"{parent_frame.name}/transform_control_{geometry.id}"

                # Disable rotation for spheres (they are symmetric), enable for boxes and cylinders
                disable_rotations = geometry.geometry_type == "sphere"

                self.transform_control = self.server.scene.add_transform_controls(
                    control_name,
                    scale=0.7,
                    disable_rotations=disable_rotations,
                    position=geometry.local_xyz,
                    wxyz=(geometry.local_wxyz if not disable_rotations else (1.0, 0.0, 0.0, 0.0)),
                    depth_test=True,  # 主控制器保持深度测试
                    opacity=1.0,  # 主控制器保持完全不透明
                )

                # Set up callback for transform updates
                @self.transform_control.on_update
                def _(_):
                    if self.current_geometry_id is not None and self.current_geometry_id in self.geometry_store.by_id:
                        current_geometry = self.geometry_store.by_id[self.current_geometry_id]
                        # Update position
                        current_geometry.local_xyz = tuple(self.transform_control.position)
                        # Update rotation only for non-sphere geometries
                        if current_geometry.geometry_type != "sphere":
                            current_geometry.update_rpy_from_quaternion(tuple(self.transform_control.wxyz))
                        self._update_geometry_visualization(current_geometry)
                        self._update_radius_gizmo()
                        self._update_box_resize_gizmos()
                        self._update_cylinder_height_gizmos()
                        # Update UI to show current rotation
                        self._update_geometry_properties_ui()

    def _remove_transform_control(self):
        """Remove the current transform control."""
        if self.transform_control is not None:
            try:
                self.transform_control.remove()
            except Exception:
                # Ignore errors if control is already removed
                pass
            finally:
                self.transform_control = None
        self._remove_radius_gizmo()
        self._remove_box_resize_gizmos()
        self._remove_cylinder_height_gizmos()

    def _remove_radius_gizmo(self):
        """Remove the current radius gizmo."""
        if self.radius_gizmo is not None:
            try:
                self.radius_gizmo.remove()
            except Exception:
                # Ignore errors if gizmo is already removed
                pass
            finally:
                self.radius_gizmo = None

    def _remove_box_resize_gizmos(self):
        """Remove all box resize gizmos."""
        # Create a copy of the values to avoid modifying dict during iteration
        gizmos_to_remove = list(self.box_resize_gizmos.values())
        for gizmo in gizmos_to_remove:
            if gizmo is not None:
                try:
                    gizmo.remove()
                except Exception:
                    pass
        self.box_resize_gizmos.clear()

    def _remove_cylinder_height_gizmos(self):
        """Remove all cylinder height gizmos."""
        # Create a copy of the values to avoid modifying dict during iteration
        gizmos_to_remove = list(self.cylinder_height_gizmos.values())
        for gizmo in gizmos_to_remove:
            if gizmo is not None:
                try:
                    gizmo.remove()
                except Exception:
                    pass
        self.cylinder_height_gizmos.clear()

    def _update_cylinder_height_gizmos(self):
        """Update cylinder height gizmos for the currently selected cylinder geometry."""
        # Remove any previous gizmos
        self._remove_cylinder_height_gizmos()

        if self.current_geometry_id is None or self.current_geometry_id not in self.geometry_store.by_id:
            return

        geometry = self.geometry_store.by_id[self.current_geometry_id]

        # Only create gizmos for cylinder geometry
        if geometry.geometry_type != "cylinder":
            return

        parent_frame = self.geometry_store.group_nodes.get(geometry.link)
        if parent_frame is None:
            return

        import numpy as np
        from viser import transforms as tf

        # Cylinder dimensions
        cylinder_height = geometry.cylinder_height
        center_x, center_y, center_z = geometry.local_xyz

        # Get the cylinder's rotation
        try:
            wxyz = geometry.local_wxyz
            if isinstance(wxyz, tuple):
                wxyz = np.array(wxyz)
            cylinder_rotation = tf.SO3(wxyz)
        except Exception as e:
            print(f"Error creating cylinder rotation: {e}")
            cylinder_rotation = tf.SO3.identity()

        # Create gizmo for Z-axis (height adjustment) - 只创建负方向的gizmo

        axis_info = {
            "name": "z_neg",
            "axis": (0, 0, -1),
            "color": (80, 80, 200),
            "local_position": np.array([0, 0, -cylinder_height / 2]),  # 底部
            "active_axes": (False, False, True),  # 只允许Z轴移动
            "base_rotation": tf.SO3.from_x_radians(math.pi),  # 负方向：箭头指向相反方向
            "translation_limits": (
                (-10.0, 10.0),  # X轴无限制
                (-10.0, 10.0),  # Y轴无限制
                (
                    -0.05,
                    10.0,
                ),  # Z轴：能向中心移动但不能穿过，能向外无限移动
            ),
        }

        # 计算gizmo在世界坐标系中的位置
        local_pos = axis_info["local_position"]

        # 确保local_pos是numpy数组
        if not isinstance(local_pos, np.ndarray):
            local_pos = np.array(local_pos)

        world_pos_offset = cylinder_rotation @ local_pos
        world_position = (
            center_x + world_pos_offset[0],
            center_y + world_pos_offset[1],
            center_z + world_pos_offset[2],
        )

        # 计算gizmo的旋转：cylinder旋转 @ 基础旋转
        try:
            gizmo_rotation = cylinder_rotation @ axis_info["base_rotation"]
        except Exception as e:
            print(f"Error computing cylinder gizmo rotation: {e}")
            gizmo_rotation = axis_info["base_rotation"]

        gizmo_name = f"{parent_frame.name}/cylinder_height_{geometry.id}_{axis_info['name']}"

        # 获取translation_limits参数
        translation_limits = axis_info.get(
            "translation_limits",
            ((-1000.0, 1000.0), (-1000.0, 1000.0), (-1000.0, 1000.0)),
        )

        gizmo = self.server.scene.add_transform_controls(
            gizmo_name,
            scale=0.2,
            line_width=15.0,  # 稍细一些，区别于box的gizmo
            active_axes=axis_info["active_axes"],
            disable_sliders=True,
            disable_rotations=True,
            wxyz=gizmo_rotation.wxyz,
            position=world_position,
            opacity=0.8,
            # depth_test=False,
            translation_limits=translation_limits,
        )

        # Store the gizmo and setup callback
        self.cylinder_height_gizmos[axis_info["name"]] = gizmo

        # Create callback for this specific gizmo
        self._setup_cylinder_height_callback(gizmo, axis_info["name"], axis_info["axis"])

    def _setup_cylinder_height_callback(self, gizmo, axis_name, axis_direction):
        """Setup callback for a specific cylinder height gizmo."""

        @gizmo.on_update
        def _(_):
            if self.current_geometry_id is None or self.current_geometry_id not in self.geometry_store.by_id:
                return

            geometry = self.geometry_store.by_id[self.current_geometry_id]

            # Only update if this is a cylinder geometry
            if geometry.geometry_type != "cylinder":
                return

            # Get current gizmo position
            gizmo_pos = gizmo.position
            center = geometry.local_xyz

            # 计算考虑旋转的新高度
            import numpy as np
            from viser import transforms as tf

            # 获取cylinder的旋转
            try:
                wxyz = geometry.local_wxyz
                if isinstance(wxyz, tuple):
                    wxyz = np.array(wxyz)
                cylinder_rotation = tf.SO3(wxyz)
                # 计算逆旋转，用于将世界坐标转换回cylinder局部坐标
                cylinder_rotation_inv = tf.SO3.from_matrix(np.linalg.inv(cylinder_rotation.as_matrix()))
            except Exception as e:
                print(f"Error computing cylinder rotation: {e}")
                cylinder_rotation = tf.SO3.identity()
                cylinder_rotation_inv = tf.SO3.identity()

            # 计算gizmo位置在cylinder局部坐标系中的位置
            gizmo_pos_local = np.array(gizmo_pos) - np.array(center)  # 相对于中心的位置
            try:
                # 将世界坐标转换回cylinder局部坐标
                gizmo_pos_local = cylinder_rotation_inv @ gizmo_pos_local
            except Exception as e:
                print(f"Error transforming coordinates: {e}")

            # 计算新高度
            # Z-axis resize - 使用局部坐标系中的Z轴距离
            distance = abs(gizmo_pos_local[2])
            new_height = max(0.01, distance * 2)  # Minimum height 1cm

            # Update geometry height
            geometry.cylinder_height = new_height

            # Update visualization
            self._update_geometry_visualization(geometry)

            # Update UI slider without triggering callbacks
            if self._cylinder_height_slider:
                self._updating_geometry_ui = True
                self._cylinder_height_slider.value = new_height
                self._updating_geometry_ui = False

    def _update_radius_gizmo(self):
        """Update radius gizmo for the currently selected geometry (sphere or cylinder)."""
        # Remove any previous gizmo
        self._remove_radius_gizmo()

        if self.current_geometry_id is None or self.current_geometry_id not in self.geometry_store.by_id:
            return

        s = self.geometry_store.by_id[self.current_geometry_id]

        # Only create radius gizmo for non-box geometries (sphere and cylinder)
        if s.geometry_type == "box":
            return

        parent_frame = self.geometry_store.group_nodes.get(s.link)
        if parent_frame is None:
            return

        # Position gizmo at 135 degrees around Z-axis for better visibility
        import numpy as np
        from viser import transforms as tf

        angle = 3 * math.pi / 4  # 135 degrees

        # Get the appropriate radius based on geometry type
        if s.geometry_type == "sphere":
            current_radius = s.radius
        elif s.geometry_type == "cylinder":
            current_radius = s.cylinder_radius
        else:
            current_radius = 0.05  # fallback

        # Calculate gizmo position and rotation based on geometry type
        if s.geometry_type == "sphere":
            # For spheres, use simple 135-degree positioning (no rotation consideration needed)
            gizmo_pos = (
                s.local_xyz[0] + current_radius * math.cos(angle),  # X component at 135°
                s.local_xyz[1] + current_radius * math.sin(angle),  # Y component at 135°
                s.local_xyz[2],  # Same Z as center
            )
            # Simple 135-degree rotation for sphere
            gizmo_rotation = tf.SO3.from_z_radians(angle)
        elif s.geometry_type == "cylinder":
            # For cylinders, consider the cylinder's rotation
            try:
                # Get cylinder's rotation
                wxyz = s.local_wxyz
                if isinstance(wxyz, tuple):
                    wxyz = np.array(wxyz)
                cylinder_rotation = tf.SO3(wxyz)
            except Exception as e:
                print(f"Error getting cylinder rotation: {e}")
                cylinder_rotation = tf.SO3.identity()

            # Create local position in cylinder's coordinate system (135° in XY plane)
            local_radius_offset = np.array(
                [
                    current_radius * math.cos(angle),  # X component at 135°
                    current_radius * math.sin(angle),  # Y component at 135°
                    0.0,  # Same Z as center in local coordinates
                ]
            )

            # Transform to world coordinates using cylinder's rotation
            world_radius_offset = cylinder_rotation @ local_radius_offset
            gizmo_pos = (
                s.local_xyz[0] + world_radius_offset[0],
                s.local_xyz[1] + world_radius_offset[1],
                s.local_xyz[2] + world_radius_offset[2],
            )

            # Combine cylinder rotation with 135-degree rotation
            base_rotation = tf.SO3.from_z_radians(angle)
            gizmo_rotation = cylinder_rotation @ base_rotation
        else:
            # Fallback for other geometry types
            gizmo_pos = (
                s.local_xyz[0] + current_radius * math.cos(angle),
                s.local_xyz[1] + current_radius * math.sin(angle),
                s.local_xyz[2],
            )
            gizmo_rotation = tf.SO3.from_z_radians(angle)

        gizmo_name = f"{parent_frame.name}/radius_gizmo_{s.id}"

        # Create a single-axis gizmo that allows bidirectional movement but prevents going through center
        self.radius_gizmo = self.server.scene.add_transform_controls(
            gizmo_name,
            scale=0.4,  # Reduce size to be less prominent
            active_axes=(True, False, False),  # Only X axis active (but now rotated)
            disable_sliders=True,
            disable_rotations=True,
            wxyz=gizmo_rotation.wxyz,  # Use the calculated rotation (considers cylinder rotation)
            position=gizmo_pos,
            translation_limits=(
                (
                    -0.05,
                    10.0,
                ),  # X轴（旋转后的）：能向中心移动但不穿过，能向外无限移动
                (-10.0, 10.0),  # Y轴无限制
                (-10.0, 10.0),  # Z轴无限制
            ),
        )

        @self.radius_gizmo.on_update
        def _(_):
            if self.current_geometry_id not in self.geometry_store.by_id:
                return

            s2 = self.geometry_store.by_id[self.current_geometry_id]

            # Only update if this is not a box geometry
            if s2.geometry_type == "box":
                return

            gizmo_pos_current = self.radius_gizmo.position

            # Calculate new radius as distance from geometry center to gizmo position
            # This is the fundamental relationship: radius = distance from center to gizmo
            center_to_gizmo = (
                gizmo_pos_current[0] - s2.local_xyz[0],
                gizmo_pos_current[1] - s2.local_xyz[1],
                gizmo_pos_current[2] - s2.local_xyz[2],
            )
            new_radius = math.sqrt(center_to_gizmo[0] ** 2 + center_to_gizmo[1] ** 2 + center_to_gizmo[2] ** 2)
            new_radius = max(0.005, new_radius)  # Minimum radius to avoid zero

            # Update radius based on geometry type
            if s2.geometry_type == "sphere":
                s2.radius = new_radius
                # Update UI slider without triggering callbacks
                if self._sphere_radius_slider:
                    self._updating_geometry_ui = True
                    self._sphere_radius_slider.value = new_radius
                    self._updating_geometry_ui = False
            elif s2.geometry_type == "cylinder":
                s2.cylinder_radius = new_radius
                # Update UI slider without triggering callbacks
                if self._cylinder_radius_slider:
                    self._updating_geometry_ui = True
                    self._cylinder_radius_slider.value = new_radius
                    self._updating_geometry_ui = False

            # Update visualization
            self._update_geometry_visualization(s2)

            # Don't reposition the gizmo here! Let the user drag it freely.
            # The gizmo position directly controls the radius - no secondary positioning logic needed.

    def _update_box_resize_gizmos(self):
        """Update box resize gizmos for the currently selected box geometry."""
        # Remove any previous gizmos
        self._remove_box_resize_gizmos()

        if self.current_geometry_id is None or self.current_geometry_id not in self.geometry_store.by_id:
            return

        geometry = self.geometry_store.by_id[self.current_geometry_id]

        # Only create gizmos for box geometry
        if geometry.geometry_type != "box":
            return

        parent_frame = self.geometry_store.group_nodes.get(geometry.link)
        if parent_frame is None:
            return

        import numpy as np
        from viser import transforms as tf

        # Box dimensions
        length, width, height = geometry.size
        center_x, center_y, center_z = geometry.local_xyz

        # Get the box's rotation
        try:
            # 确保quaternion是正确的格式
            wxyz = geometry.local_wxyz
            if isinstance(wxyz, tuple):
                wxyz = np.array(wxyz)
            box_rotation = tf.SO3(wxyz)
        except Exception as e:
            print(f"Error creating box rotation: {e}")
            box_rotation = tf.SO3.identity()

        axes_info = [
            {
                "name": "x_neg",
                "axis": (-1, 0, 0),
                "color": (200, 80, 80),
                "local_position": np.array([-length / 2, 0, 0]),  # box本地坐标系中的位置
                "active_axes": (True, False, False),  # 只允许X轴移动
                "base_rotation": tf.SO3.from_y_radians(math.pi),  # 基础旋转：箭头指向相反方向
                "translation_limits": (
                    (-0.05, 10.0),  # X轴：能向中心移动但不穿过，能向外无限移动
                    (-10.0, 10.0),  # Y轴无限制
                    (-10.0, 10.0),  # Z轴无限制
                ),
            },
            {
                "name": "y_neg",
                "axis": (0, -1, 0),
                "color": (80, 200, 80),
                "local_position": np.array([0, -width / 2, 0]),  # box本地坐标系中的位置
                "active_axes": (False, True, False),  # 只允许Y轴移动
                "base_rotation": tf.SO3.from_x_radians(math.pi),  # 基础旋转：箭头指向相反方向
                "translation_limits": (
                    (-10.0, 10.0),  # X轴无限制
                    (-0.05, 10.0),  # Y轴：能向中心移动但不穿过，能向外无限移动
                    (-10.0, 10.0),  # Z轴无限制
                ),
            },
            {
                "name": "z_neg",
                "axis": (0, 0, -1),
                "color": (80, 80, 200),
                "local_position": np.array([0, 0, -height / 2]),  # box本地坐标系中的位置
                "active_axes": (False, False, True),  # 只允许Z轴移动
                "base_rotation": tf.SO3.from_x_radians(math.pi),  # 修复：使用base_rotation并绕X轴旋转
                "translation_limits": (
                    (-10.0, 10.0),  # X轴无限制
                    (-10.0, 10.0),  # Y轴无限制
                    (-0.05, 10.0),  # Z轴：能向中心移动但不穿过，能向外无限移动
                ),
            },
        ]

        for axis_info in axes_info:
            # 计算gizmo在世界坐标系中的位置
            # 将本地位置通过box的旋转变换到世界坐标系
            local_pos = axis_info["local_position"]

            # 确保local_pos是numpy数组
            if not isinstance(local_pos, np.ndarray):
                local_pos = np.array(local_pos)

            world_pos_offset = box_rotation @ local_pos  # 使用 @ 操作符进行旋转变换
            world_position = (
                center_x + world_pos_offset[0],
                center_y + world_pos_offset[1],
                center_z + world_pos_offset[2],
            )

            # 计算gizmo的旋转：box旋转 @ 基础旋转
            try:
                gizmo_rotation = box_rotation @ axis_info["base_rotation"]
            except Exception as e:
                print(f"Error computing gizmo rotation: {e}")
                gizmo_rotation = axis_info["base_rotation"]

            gizmo_name = f"{parent_frame.name}/box_resize_{geometry.id}_{axis_info['name']}"

            # 获取translation_limits参数
            translation_limits = axis_info.get(
                "translation_limits",
                ((-1000.0, 1000.0), (-1000.0, 1000.0), (-1000.0, 1000.0)),
            )

            gizmo = self.server.scene.add_transform_controls(
                gizmo_name,
                scale=0.2,
                line_width=20.0,
                active_axes=axis_info["active_axes"],
                disable_sliders=True,
                disable_rotations=True,
                wxyz=gizmo_rotation.wxyz,
                position=world_position,
                opacity=0.8,
                # depth_test=False,
                translation_limits=translation_limits,  # 添加移动限制
            )

            # Store the gizmo and setup callback
            self.box_resize_gizmos[axis_info["name"]] = gizmo

            # Create callback for this specific gizmo
            self._setup_box_resize_callback(gizmo, axis_info["name"], axis_info["axis"])

    def _setup_box_resize_callback(self, gizmo, axis_name, axis_direction):
        """Setup callback for a specific box resize gizmo."""

        @gizmo.on_update
        def _(_):
            if self.current_geometry_id is None or self.current_geometry_id not in self.geometry_store.by_id:
                return

            geometry = self.geometry_store.by_id[self.current_geometry_id]

            # Only update if this is a box geometry
            if geometry.geometry_type != "box":
                return

            # Get current gizmo position
            gizmo_pos = gizmo.position
            center = geometry.local_xyz

            # 计算考虑旋转的新尺寸
            import numpy as np
            from viser import transforms as tf

            # 获取box的旋转
            try:
                wxyz = geometry.local_wxyz
                if isinstance(wxyz, tuple):
                    wxyz = np.array(wxyz)
                box_rotation = tf.SO3(wxyz)
                # 计算逆旋转，用于将世界坐标转换回box局部坐标
                box_rotation_inv = tf.SO3.from_matrix(np.linalg.inv(box_rotation.as_matrix()))
            except Exception as e:
                print(f"Error computing box rotation: {e}")
                box_rotation = tf.SO3.identity()
                box_rotation_inv = tf.SO3.identity()

            # 计算gizmo位置在box局部坐标系中的位置
            gizmo_pos_local = np.array(gizmo_pos) - np.array(center)  # 相对于中心的位置
            try:
                # 将世界坐标转换回box局部坐标
                gizmo_pos_local = box_rotation_inv @ gizmo_pos_local
            except Exception as e:
                print(f"Error transforming coordinates: {e}")

            # 计算新尺寸
            new_size = list(geometry.size)

            if "x" in axis_name:
                # X-axis resize - 使用局部坐标系中的X轴距离
                distance = abs(gizmo_pos_local[0])
                new_size[0] = max(0.01, distance * 2)  # Minimum size 1cm
            elif "y" in axis_name:
                # Y-axis resize - 使用局部坐标系中的Y轴距离
                distance = abs(gizmo_pos_local[1])
                new_size[1] = max(0.01, distance * 2)  # Minimum size 1cm
            elif "z" in axis_name:
                # Z-axis resize - 使用局部坐标系中的Z轴距离
                distance = abs(gizmo_pos_local[2])
                new_size[2] = max(0.01, distance * 2)  # Minimum size 1cm

            # Update geometry size
            geometry.size = tuple(new_size)

            # Update visualization
            self._update_geometry_visualization(geometry)

            # Update other gizmos positions (but avoid infinite recursion)
            self._update_other_box_gizmos(axis_name, geometry)

            # Update UI sliders without triggering callbacks
            if self._box_size_sliders:
                self._updating_geometry_ui = True
                self._box_size_sliders[0].value = new_size[0]  # length
                self._box_size_sliders[1].value = new_size[1]  # width
                self._box_size_sliders[2].value = new_size[2]  # height
                self._updating_geometry_ui = False

    def _update_other_box_gizmos(self, changed_axis_name, geometry):
        """Update positions of other box gizmos when one is moved."""

        # Only update if this is a box geometry
        if geometry.geometry_type != "box":
            return

        import numpy as np
        from viser import transforms as tf

        length, width, height = geometry.size
        center_x, center_y, center_z = geometry.local_xyz

        # Get the box's rotation
        try:
            # 确保quaternion是正确的格式
            wxyz = geometry.local_wxyz
            if isinstance(wxyz, tuple):
                wxyz = np.array(wxyz)
            box_rotation = tf.SO3(wxyz)
        except Exception as e:
            print(f"Error creating box rotation: {e}")
            box_rotation = tf.SO3.identity()

        # Update positions of gizmos that weren't just moved
        local_positions = {
            "x_neg": np.array([-length / 2, 0, 0]),
            "y_neg": np.array([0, -width / 2, 0]),
            "z_neg": np.array([0, 0, -height / 2]),
        }

        for axis_name, gizmo in self.box_resize_gizmos.items():
            if axis_name != changed_axis_name and gizmo is not None:
                try:
                    # 计算新的世界坐标位置，考虑box的旋转
                    local_pos = local_positions[axis_name]
                    world_pos_offset = box_rotation @ local_pos  # 使用 @ 操作符
                    world_position = (
                        center_x + world_pos_offset[0],
                        center_y + world_pos_offset[1],
                        center_z + world_pos_offset[2],
                    )
                    gizmo.position = world_position
                except Exception:
                    pass  # Ignore errors if gizmo is being removed

    def _update_geometry_properties_ui(self):
        """Update the geometry property UI controls to reflect the currently selected geometry."""
        # Set flag to prevent recursive updates
        self._updating_geometry_ui = True

        if self.current_geometry_id is not None and self.current_geometry_id in self.geometry_store.by_id:
            geometry = self.geometry_store.by_id[self.current_geometry_id]

            # Update properties based on geometry type
            if geometry.geometry_type == "sphere":
                if self._sphere_radius_slider:
                    self._sphere_radius_slider.value = geometry.radius
            elif geometry.geometry_type == "box":
                if self._box_size_sliders:
                    self._box_size_sliders[0].value = geometry.size[0]  # length
                    self._box_size_sliders[1].value = geometry.size[1]  # width
                    self._box_size_sliders[2].value = geometry.size[2]  # height
            elif geometry.geometry_type == "cylinder":
                if self._cylinder_radius_slider:
                    self._cylinder_radius_slider.value = geometry.cylinder_radius
                if self._cylinder_height_slider:
                    self._cylinder_height_slider.value = geometry.cylinder_height
                if self._cylinder_as_capsule_checkbox:
                    self._cylinder_as_capsule_checkbox.value = geometry.display_as_capsule

            # Update color input
            if self._geometry_color_input:
                self._geometry_color_input.value = geometry.color

            # Update rotation sliders only for non-sphere geometries
            if self._rpy_sliders:
                if geometry.geometry_type != "sphere":
                    self._rpy_sliders[0].value = geometry.local_rpy[0]  # roll
                    self._rpy_sliders[1].value = geometry.local_rpy[1]  # pitch
                    self._rpy_sliders[2].value = geometry.local_rpy[2]  # yaw
                    # Enable rotation sliders
                    self._rpy_sliders[0].disabled = False
                    self._rpy_sliders[1].disabled = False
                    self._rpy_sliders[2].disabled = False
                else:
                    # For spheres, reset to zero and disable sliders
                    self._rpy_sliders[0].value = 0.0
                    self._rpy_sliders[1].value = 0.0
                    self._rpy_sliders[2].value = 0.0
                    self._rpy_sliders[0].disabled = True
                    self._rpy_sliders[1].disabled = True
                    self._rpy_sliders[2].disabled = True
        else:
            # Reset to default values when no geometry selected
            if self._sphere_radius_slider:
                self._sphere_radius_slider.value = 0.05
            if self._box_size_sliders:
                self._box_size_sliders[0].value = 0.1
                self._box_size_sliders[1].value = 0.1
                self._box_size_sliders[2].value = 0.1
            if self._cylinder_radius_slider:
                self._cylinder_radius_slider.value = 0.05
            if self._cylinder_height_slider:
                self._cylinder_height_slider.value = 0.1
            if self._geometry_color_input:
                self._geometry_color_input.value = (255, 180, 60)
            if self._rpy_sliders:
                self._rpy_sliders[0].value = 0.0  # roll
                self._rpy_sliders[1].value = 0.0  # pitch
                self._rpy_sliders[2].value = 0.0  # yaw
                # Disable rotation sliders when no geometry is selected
                self._rpy_sliders[0].disabled = True
                self._rpy_sliders[1].disabled = True
                self._rpy_sliders[2].disabled = True

        # Clear flag after UI update
        self._updating_geometry_ui = False

    def _sync_link_selection(self):
        """Sync link selection between visibility controls and geometry editor."""
        # Sync visibility dropdown if different
        if self._current_link_dropdown and self._current_link_dropdown.value != self.current_link:
            self._current_link_dropdown.value = self.current_link
        # Sync geometry editor dropdown if different
        if self._link_dropdown and self._link_dropdown.value != self.current_link:
            self._link_dropdown.value = self.current_link

    def _sync_geometry_selection(self):
        """Sync geometry dropdown to reflect the currently selected geometry."""
        if self._geometry_dropdown and self.current_geometry_id is not None:
            # Find the correct dropdown option for this geometry
            if self.current_geometry_id in self.geometry_store.by_id:
                geometry = self.geometry_store.by_id[self.current_geometry_id]
                expected_value = f"{geometry.geometry_type.title()} {geometry.id}"

                # Check if this value exists in the dropdown options
                if expected_value in self._geometry_dropdown.options:
                    self._geometry_dropdown.value = expected_value

    def _get_geometry_opacity(self, geometry: Geometry) -> float:
        """Get the appropriate opacity for a geometry based on current selection state."""
        if geometry.id == self.current_geometry_id:
            return self.selected_geometry_opacity
        elif geometry.link == self.current_link:
            return self.unselected_geometries_opacity
        else:
            return self.other_links_geometries_opacity

    def _update_mesh_visibility(self):
        """Update visibility of robot meshes based on link selection."""
        for link_name, mesh_handles in self.urdf_viz.link_meshes.items():
            for mesh_handle in mesh_handles:
                # Determine if this link should be visible
                if link_name == self.current_link:
                    # This is the selected link
                    mesh_handle.visible = self.show_selected_link
                else:
                    # This is a non-selected link
                    mesh_handle.visible = self.show_other_links

    def _update_geometry_opacities(self):
        """Update opacity of all geometries based on current selection state."""
        for geometry in self.geometry_store.by_id.values():
            if geometry.node is not None:
                new_opacity = self._get_geometry_opacity(geometry)

                # All geometry types now support direct opacity setting
                geometry.node.opacity = new_opacity
                geometry.node.visible = new_opacity > 0.0

    def _load_geometry_config_yaml(self, yaml_path: Path):
        """Load geometry configuration from YAML file at startup."""
        from .core import load_geometry_specs_from_yaml

        if not yaml_path.exists():
            print(f"⚠️  Geometry configuration YAML file not found: {yaml_path}")
            return

        print(f"📥 Loading geometry configuration from: {yaml_path}")

        try:
            specs = load_geometry_specs_from_yaml(yaml_path)
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
            return

        total_loaded = 0
        for spec in specs:
            geometry = self.geometry_store.add(spec.link, **spec.to_store_kwargs())
            self._create_geometry_visualization(geometry)
            total_loaded += 1

        print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name}")

    def _add_reference_grid(self):
        """Add a reference grid to the scene."""
        # Get scene bounds to position grid appropriately
        try:
            trimesh_scene = self.urdf_viz._urdf.scene or self.urdf_viz._urdf.collision_scene
            z_pos = trimesh_scene.bounds[0, 2] if trimesh_scene is not None else 0.0
        except Exception:
            z_pos = 0.0

        self.server.scene.add_grid(
            "/reference_grid",
            width=2,
            height=2,
            position=(0.0, 0.0, z_pos),
            cell_color=(200, 200, 200),
            cell_thickness=1.0,
        )

    def run(self):
        """Run the application (blocking)."""
        print("🚀 Application running! Use Ctrl+C to exit.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down Bubblify...")
        finally:
            # Cleanup
            self._remove_transform_control()
            self._remove_radius_gizmo()
            self._remove_cylinder_height_gizmos()
            self.urdf_viz.remove()
