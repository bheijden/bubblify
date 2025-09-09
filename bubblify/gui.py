"""Interactive GUI application for URDF spherization using Viser."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import viser
import yourdfpy
from robot_descriptions.loaders.yourdfpy import load_robot_description

from .core import EnhancedViserUrdf, Sphere, SphereStore, inject_spheres_into_urdf_xml


class BubblifyApp:
    """Main application class for interactive URDF spherization."""

    def __init__(
        self,
        robot_name: str = "panda",
        urdf_path: Optional[Path] = None,
        show_collision: bool = False,
        port: int = 8080,
        spherization_yml: Optional[Path] = None,
    ):
        """Initialize the Bubblify application.

        Args:
            robot_name: Name of robot from robot_descriptions (used if urdf_path is None)
            urdf_path: Path to custom URDF file
            show_collision: Whether to show collision meshes
            port: Viser server port
            spherization_yml: Path to existing spherization YAML file to load
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

        # Sphere management
        self.sphere_store = SphereStore()

        # GUI state
        self.current_sphere_id: Optional[int] = None
        self.current_link: str = ""
        self.joint_sliders: List[viser.GuiInputHandle[float]] = []
        self.transform_control: Optional[viser.TransformControlsHandle] = None
        self.radius_gizmo: Optional[viser.TransformControlsHandle] = None

        # GUI control references for syncing
        self._link_dropdown = None
        self._current_link_dropdown = None
        self._sphere_dropdown = None
        self._sphere_radius_slider = None
        self._sphere_color_input = None

        # Flag to prevent recursive updates
        self._updating_sphere_ui = False

        # Visibility settings
        self.show_selected_link: bool = True
        self.show_other_links: bool = True

        # Sphere opacity settings
        self.selected_sphere_opacity: float = 1.0
        self.unselected_spheres_opacity: float = 0.5
        self.other_links_spheres_opacity: float = 0.2

        # Create sphere root frame
        self.spheres_root = self.server.scene.add_frame("/spheres", show_axes=False)

        # Setup GUI
        self._setup_robot_controls()
        self._setup_visibility_controls()
        self._setup_sphere_controls()
        self._setup_export_controls()

        # Add a grid for reference
        self._add_reference_grid()

        # Initialize visibility states
        self._update_mesh_visibility()

        # Load spherization YAML if provided
        if spherization_yml is not None:
            self._load_spherization_yaml(spherization_yml)

        print(f"🎯 Bubblify server running at http://localhost:{port}")
        print("Use the GUI controls to add and edit collision spheres!")

    def _setup_robot_controls(self):
        """Setup robot configuration and visibility controls."""
        with self.server.gui.add_folder("🤖 Robot Controls"):
            # Joint sliders
            initial_config = []

            for joint_name, (lower, upper) in self.urdf_viz.get_actuated_joint_limits().items():
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

            # Sphere opacity controls with clearer names
            selected_sphere_opacity = self.server.gui.add_slider(
                "Current Sphere", min=0.0, max=1.0, step=0.1, initial_value=self.selected_sphere_opacity
            )
            unselected_spheres_opacity = self.server.gui.add_slider(
                "Other Spheres (Same Link)", min=0.0, max=1.0, step=0.1, initial_value=self.unselected_spheres_opacity
            )
            other_links_spheres_opacity = self.server.gui.add_slider(
                "Spheres (Other Links)", min=0.0, max=1.0, step=0.1, initial_value=self.other_links_spheres_opacity
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

            @selected_sphere_opacity.on_update
            def _(_):
                self.selected_sphere_opacity = selected_sphere_opacity.value
                self._update_sphere_opacities()

            @unselected_spheres_opacity.on_update
            def _(_):
                self.unselected_spheres_opacity = unselected_spheres_opacity.value
                self._update_sphere_opacities()

            @other_links_spheres_opacity.on_update
            def _(_):
                self.other_links_spheres_opacity = other_links_spheres_opacity.value
                self._update_sphere_opacities()

    def _setup_sphere_controls(self):
        """Setup simplified sphere creation and editing controls."""
        with self.server.gui.add_folder("⚪ Sphere Editor"):
            # Get links for dropdown
            all_links = self.urdf_viz.get_all_link_names()
            if not all_links:
                all_links = ["base_link"]

            # Link selection
            link_dropdown = self.server.gui.add_dropdown("Link", options=all_links, initial_value=all_links[0])
            self.current_link = link_dropdown.value
            self._link_dropdown = link_dropdown  # Store reference for syncing

            # Sphere selection dropdown (will be populated based on selected link)
            sphere_dropdown = self.server.gui.add_dropdown("Sphere", options=["None"], initial_value="None")
            self._sphere_dropdown = sphere_dropdown  # Store reference

            # Sphere creation and deletion
            add_sphere_btn = self.server.gui.add_button("➕ Add Sphere")
            delete_sphere_btn = self.server.gui.add_button("🗑️ Delete Selected")

            # Sphere statistics
            total_sphere_count = self.server.gui.add_text("Total Spheres", initial_value="0")
            link_sphere_count = self.server.gui.add_text("Spheres on Current Link", initial_value="0")

            # Sphere properties
            # Adjust range so 0.05 is at 33% of the slider range
            # If 0.05 should be at 33%, then: 0.05 = min + 0.33 * (max - min)
            # Solving: max = (0.05 - min) / 0.33 + min
            # With min=0.005: max = (0.05 - 0.005) / 0.33 + 0.005 = 0.14
            sphere_radius = self.server.gui.add_slider("Radius", min=0.005, max=0.14, step=0.001, initial_value=0.05)
            sphere_color = self.server.gui.add_rgb("Color", initial_value=(255, 180, 60))
            self._sphere_radius_slider = sphere_radius  # Store reference
            self._sphere_color_input = sphere_color  # Store reference

            def update_sphere_dropdown():
                """Update sphere dropdown based on selected link."""
                link_name = link_dropdown.value
                self.current_link = link_name
                spheres = self.sphere_store.get_spheres_for_link(link_name)

                if spheres:
                    options = [f"Sphere {s.id}" for s in spheres]
                    sphere_dropdown.options = options

                    # Determine which sphere to select
                    sphere_to_select = None
                    if self.current_sphere_id is not None:
                        # Try to keep current selection if it's still valid for this link
                        current_sphere = self.sphere_store.by_id.get(self.current_sphere_id)
                        if current_sphere and current_sphere.link == link_name:
                            sphere_to_select = current_sphere

                    # If no valid current selection, select the first sphere
                    if sphere_to_select is None:
                        sphere_to_select = spheres[0]

                    # Update both dropdown and current_sphere_id
                    sphere_dropdown.value = f"Sphere {sphere_to_select.id}"
                    self.current_sphere_id = sphere_to_select.id
                else:
                    sphere_dropdown.options = ["None"]
                    sphere_dropdown.value = "None"
                    self.current_sphere_id = None

                self._update_transform_control()
                self._update_sphere_properties_ui()
                self._update_sphere_opacities()
                self._update_mesh_visibility()

                # Update counts
                total_sphere_count.value = str(len(self.sphere_store.by_id))
                link_sphere_count.value = str(len(spheres))

            def update_selected_sphere():
                """Update selected sphere ID from dropdown and switch link context."""
                if sphere_dropdown.value != "None":
                    sphere_id = int(sphere_dropdown.value.split()[-1])
                    self.current_sphere_id = sphere_id

                    # Get the sphere and switch to its link
                    if sphere_id in self.sphere_store.by_id:
                        sphere = self.sphere_store.by_id[sphere_id]
                        # Update the link context and sync dropdowns
                        if sphere.link != self.current_link:
                            self.current_link = sphere.link
                            link_dropdown.value = sphere.link
                            self._sync_link_selection()
                            self._update_mesh_visibility()

                    self._update_transform_control()
                    self._update_sphere_properties_ui()
                    self._update_sphere_opacities()
                else:
                    self.current_sphere_id = None
                    self._remove_transform_control()

            @link_dropdown.on_update
            def _(_):
                self.current_link = link_dropdown.value
                self._sync_link_selection()
                self._update_mesh_visibility()
                update_sphere_dropdown()

            @sphere_dropdown.on_update
            def _(_):
                update_selected_sphere()

            @add_sphere_btn.on_click
            def _(_):
                """Add a new sphere to the selected link using current radius."""
                link_name = link_dropdown.value
                current_radius = sphere_radius.value  # Use radius from slider

                # Add sphere at origin (revert to original single-sphere behavior)
                sphere = self.sphere_store.add(link_name, xyz=(0.0, 0.0, 0.0), radius=current_radius)
                self._create_sphere_visualization(sphere)

                # Select the new sphere as current
                self.current_sphere_id = sphere.id

                # Update dropdown and controls immediately
                update_sphere_dropdown()

                # Directly call the control update methods to show gizmo immediately
                self._update_transform_control()
                self._update_radius_gizmo()
                self._update_sphere_properties_ui()
                self._update_sphere_opacities()

            @delete_sphere_btn.on_click
            def _(_):
                """Delete the selected sphere."""
                if self.current_sphere_id is not None:
                    self.sphere_store.remove(self.current_sphere_id)
                    self.current_sphere_id = None
                    self._remove_transform_control()
                    update_sphere_dropdown()

            def update_sphere_properties():
                """Update sphere properties from UI."""
                # Skip update if we're currently updating the UI to prevent recursive changes
                if self._updating_sphere_ui:
                    return

                if self.current_sphere_id is not None and self.current_sphere_id in self.sphere_store.by_id:
                    sphere = self.sphere_store.by_id[self.current_sphere_id]
                    sphere.radius = float(sphere_radius.value)
                    sphere.color = tuple(int(c) for c in sphere_color.value)
                    self._update_sphere_visualization(sphere)
                    self._update_radius_gizmo()

            sphere_radius.on_update(lambda _: update_sphere_properties())
            sphere_color.on_update(lambda _: update_sphere_properties())

            # Initialize
            update_sphere_dropdown()

            # Set up initial opacity state
            self._update_sphere_opacities()

    def _setup_export_controls(self):
        """Setup export functionality."""
        with self.server.gui.add_folder("💾 Export"):
            # Get default export names based on URDF
            default_name = "spherized"
            if self.urdf_path and self.urdf_path.stem:
                default_name = f"{self.urdf_path.stem}_spherized"

            # Export name configuration (no paths, just filenames)
            export_name_input = self.server.gui.add_text("Export Name", initial_value=default_name)

            # Export options
            export_yml_btn = self.server.gui.add_button("Export Spheres (YAML)")
            export_urdf_btn = self.server.gui.add_button("Export URDF with Spheres")

            # Status with error details (read-only)
            export_status = self.server.gui.add_markdown("Ready to export")
            export_details = self.server.gui.add_markdown("")

            @export_yml_btn.on_click
            def _(_):
                """Export sphere configuration to YAML."""
                try:
                    import yaml

                    # Create data structure matching the xarm format
                    collision_spheres = {}
                    for sphere in self.sphere_store.by_id.values():
                        if sphere.link not in collision_spheres:
                            collision_spheres[sphere.link] = []

                        # Ensure clean conversion to Python primitives
                        center = sphere.local_xyz
                        if hasattr(center, "tolist"):
                            center = center.tolist()
                        else:
                            center = [float(x) for x in center]

                        collision_spheres[sphere.link].append({"center": center, "radius": float(sphere.radius)})

                    # Add metadata for import (ensure clean Python types)
                    data = {
                        "collision_spheres": collision_spheres,
                        "metadata": {
                            "total_spheres": int(len(self.sphere_store.by_id)),
                            "links": list(collision_spheres.keys()),
                            "export_timestamp": float(time.time()),
                        },
                    }

                    # Determine output directory (same as URDF or current working directory)
                    if self.urdf_path and self.urdf_path.parent:
                        output_dir = self.urdf_path.parent
                    else:
                        output_dir = Path.cwd()

                    output_path = output_dir / f"{export_name_input.value}.yml"
                    output_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
                    export_status.content = f"✅ Exported {len(self.sphere_store.by_id)} spheres"
                    export_details.content = f"Saved to: {output_path.name}"
                    print(f"Exported spherization to {output_path.absolute()}")

                except ImportError:
                    error_msg = "PyYAML not installed. Run: pip install PyYAML"
                    export_status.content = "❌ Missing dependency"
                    export_details.content = error_msg
                    print(f"Export failed: {error_msg}")
                except Exception as e:
                    export_status.content = f"❌ Export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"Export failed: {e}")

            @export_urdf_btn.on_click
            def _(_):
                """Export URDF with collision spheres."""
                try:
                    urdf_xml = inject_spheres_into_urdf_xml(self.urdf_path, self.urdf, self.sphere_store)

                    # Determine output directory (same as URDF or current working directory)
                    if self.urdf_path and self.urdf_path.parent:
                        output_dir = self.urdf_path.parent
                    else:
                        output_dir = Path.cwd()

                    output_path = output_dir / f"{export_name_input.value}.urdf"
                    output_path.write_text(urdf_xml)
                    export_status.content = f"✅ Exported URDF with {len(self.sphere_store.by_id)} spheres"
                    export_details.content = f"Saved to: {output_path.name}"
                    print(f"Exported spherized URDF to {output_path.absolute()}")

                except Exception as e:
                    export_status.content = f"❌ URDF export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"URDF export failed: {e}")

    def _create_sphere_visualization(self, sphere: Sphere):
        """Create or update the 3D visualization for a sphere."""
        # Ensure link group exists
        if sphere.link not in self.sphere_store.group_nodes:
            # Get the link frame from enhanced URDF
            link_frame = self.urdf_viz.link_frame.get(sphere.link)
            if link_frame is not None:
                self.sphere_store.group_nodes[sphere.link] = self.server.scene.add_frame(
                    f"{link_frame.name}/spheres", show_axes=False
                )
            else:
                # Fallback: create under spheres root
                self.sphere_store.group_nodes[sphere.link] = self.server.scene.add_frame(
                    f"/spheres/{sphere.link}", show_axes=False
                )

        parent_frame = self.sphere_store.group_nodes[sphere.link]

        # Create sphere visualization with appropriate opacity
        opacity = self._get_sphere_opacity(sphere)
        sphere.node = self.server.scene.add_icosphere(
            f"{parent_frame.name}/sphere_{sphere.id}",
            radius=sphere.radius,
            color=sphere.color,
            position=sphere.local_xyz,
            opacity=opacity,
            visible=True,
        )

        # Make sphere clickable for selection
        @sphere.node.on_click
        def _(_):
            # Set sphere ID FIRST, before any other updates
            self.current_sphere_id = sphere.id
            old_link = self.current_link
            self.current_link = sphere.link

            # If we switched links, we need to update dropdowns carefully
            if old_link != self.current_link:
                self._sync_link_selection()
                # IMPORTANT: Don't call update_sphere_dropdown here as it will override our selection
                # Instead, manually update the sphere dropdown after link sync
                if self._sphere_dropdown:
                    spheres = self.sphere_store.get_spheres_for_link(self.current_link)
                    if spheres:
                        options = [f"Sphere {s.id}" for s in spheres]
                        self._sphere_dropdown.options = options
                    self._sync_sphere_selection()
            else:
                # Same link, just update sphere selection
                self._sync_sphere_selection()

            # Update visuals and UI
            self._update_transform_control()
            self._update_radius_gizmo()
            self._update_sphere_opacities()
            self._update_mesh_visibility()
            self._update_sphere_properties_ui()

    def _update_sphere_visualization(self, sphere: Sphere):
        """Update existing sphere visualization."""
        if sphere.node is not None:
            # Remove old node
            sphere.node.remove()

        # Recreate with new properties
        self._create_sphere_visualization(sphere)

    def _update_transform_control(self):
        """Update transform control for the currently selected sphere."""
        if self.current_sphere_id is not None and self.current_sphere_id in self.sphere_store.by_id:
            sphere = self.sphere_store.by_id[self.current_sphere_id]

            # Remove existing transform control
            self._remove_transform_control()

            # Get the parent frame for this sphere
            parent_frame = self.sphere_store.group_nodes.get(sphere.link)
            if parent_frame is not None:
                control_name = f"{parent_frame.name}/transform_control_{sphere.id}"

                self.transform_control = self.server.scene.add_transform_controls(
                    control_name,
                    scale=0.7,
                    disable_rotations=True,  # Spheres don't need rotation
                    position=sphere.local_xyz,
                )

                # Set up callback for transform updates
                @self.transform_control.on_update
                def _(_):
                    if self.current_sphere_id is not None and self.current_sphere_id in self.sphere_store.by_id:
                        current_sphere = self.sphere_store.by_id[self.current_sphere_id]
                        current_sphere.local_xyz = tuple(self.transform_control.position)
                        self._update_sphere_visualization(current_sphere)
                        self._update_radius_gizmo()

    def _remove_transform_control(self):
        """Remove the current transform control."""
        if self.transform_control is not None:
            self.transform_control.remove()
            self.transform_control = None
        self._remove_radius_gizmo()

    def _remove_radius_gizmo(self):
        """Remove the current radius gizmo."""
        if self.radius_gizmo is not None:
            self.radius_gizmo.remove()
            self.radius_gizmo = None

    def _update_radius_gizmo(self):
        """Update radius gizmo for the currently selected sphere."""
        # Remove any previous gizmo
        self._remove_radius_gizmo()

        if self.current_sphere_id is None or self.current_sphere_id not in self.sphere_store.by_id:
            return

        s = self.sphere_store.by_id[self.current_sphere_id]
        parent_frame = self.sphere_store.group_nodes.get(s.link)
        if parent_frame is None:
            return

        # Position gizmo at 135 degrees around Z-axis for better visibility
        import math

        angle = 3 * math.pi / 4  # 135 degrees
        gizmo_pos = (
            s.local_xyz[0] + s.radius * math.cos(angle),  # X component at 45°
            s.local_xyz[1] + s.radius * math.sin(angle),  # Y component at 45°
            s.local_xyz[2],  # Same Z as center
        )

        gizmo_name = f"{parent_frame.name}/radius_gizmo_{s.id}"

        # Create rotation quaternion for 135 degrees around Z-axis
        # This rotates the gizmo's X-axis by 135 degrees, making it point diagonally
        from viser import transforms as tf

        rotation_135deg = tf.SO3.from_z_radians(angle)  # 135° rotation around Z

        # Create a single-axis gizmo that allows full bidirectional movement along the rotated X axis
        # This allows both increasing and decreasing radius, including going to zero
        self.radius_gizmo = self.server.scene.add_transform_controls(
            gizmo_name,
            scale=0.4,  # Reduce size to be less prominent
            active_axes=(True, False, False),  # Only X axis active (but now rotated)
            disable_sliders=True,
            disable_rotations=True,
            # Allow full range movement - no translation limits to enable zero radius
            wxyz=rotation_135deg.wxyz,  # Rotate the gizmo 135 degrees
            position=gizmo_pos,
        )

        @self.radius_gizmo.on_update
        def _(_):
            if self.current_sphere_id not in self.sphere_store.by_id:
                return

            s2 = self.sphere_store.by_id[self.current_sphere_id]
            gizmo_pos_current = self.radius_gizmo.position

            # Calculate new radius as distance from sphere center to gizmo position
            # This is the fundamental relationship: radius = distance from center to gizmo
            center_to_gizmo = (
                gizmo_pos_current[0] - s2.local_xyz[0],
                gizmo_pos_current[1] - s2.local_xyz[1],
                gizmo_pos_current[2] - s2.local_xyz[2],
            )
            new_radius = math.sqrt(center_to_gizmo[0] ** 2 + center_to_gizmo[1] ** 2 + center_to_gizmo[2] ** 2)
            new_radius = max(0.0, new_radius)  # Allow zero radius

            # Update sphere radius
            s2.radius = new_radius
            self._update_sphere_visualization(s2)

            # Don't reposition the gizmo here! Let the user drag it freely.
            # The gizmo position directly controls the radius - no secondary positioning logic needed.

            # Update UI slider without triggering callbacks
            if self._sphere_radius_slider:
                self._updating_sphere_ui = True
                self._sphere_radius_slider.value = new_radius
                self._updating_sphere_ui = False

    def _update_sphere_properties_ui(self):
        """Update the sphere property UI controls to reflect the currently selected sphere."""
        # Set flag to prevent recursive updates
        self._updating_sphere_ui = True

        if self.current_sphere_id is not None and self.current_sphere_id in self.sphere_store.by_id:
            sphere = self.sphere_store.by_id[self.current_sphere_id]

            # Update radius slider
            if self._sphere_radius_slider:
                self._sphere_radius_slider.value = sphere.radius

            # Update color input
            if self._sphere_color_input:
                self._sphere_color_input.value = sphere.color
        else:
            # Reset to default values when no sphere selected
            if self._sphere_radius_slider:
                self._sphere_radius_slider.value = 0.05
            if self._sphere_color_input:
                self._sphere_color_input.value = (255, 180, 60)

        # Clear flag after UI update
        self._updating_sphere_ui = False

    def _sync_link_selection(self):
        """Sync link selection between visibility controls and sphere editor."""
        # Sync visibility dropdown if different
        if self._current_link_dropdown and self._current_link_dropdown.value != self.current_link:
            self._current_link_dropdown.value = self.current_link
        # Sync sphere editor dropdown if different
        if self._link_dropdown and self._link_dropdown.value != self.current_link:
            self._link_dropdown.value = self.current_link

    def _sync_sphere_selection(self):
        """Sync sphere dropdown to reflect the currently selected sphere."""
        if self._sphere_dropdown and self.current_sphere_id is not None:
            # Find the correct dropdown option for this sphere
            if self.current_sphere_id in self.sphere_store.by_id:
                sphere = self.sphere_store.by_id[self.current_sphere_id]
                expected_value = f"Sphere {sphere.id}"

                # Check if this value exists in the dropdown options
                if expected_value in self._sphere_dropdown.options:
                    self._sphere_dropdown.value = expected_value

    def _get_sphere_opacity(self, sphere: Sphere) -> float:
        """Get the appropriate opacity for a sphere based on current selection state."""
        if sphere.id == self.current_sphere_id:
            return self.selected_sphere_opacity
        elif sphere.link == self.current_link:
            return self.unselected_spheres_opacity
        else:
            return self.other_links_spheres_opacity

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

    def _update_sphere_opacities(self):
        """Update opacity of all spheres based on current selection state."""
        for sphere in self.sphere_store.by_id.values():
            if sphere.node is not None:
                new_opacity = self._get_sphere_opacity(sphere)
                # Update sphere opacity
                sphere.node.opacity = new_opacity
                # Handle visibility (0.0 opacity = invisible)
                sphere.node.visible = new_opacity > 0.0

    def _load_spherization_yaml(self, yaml_path: Path):
        """Load sphere configuration from YAML file at startup."""
        try:
            import yaml

            if not yaml_path.exists():
                print(f"⚠️  Spherization YAML file not found: {yaml_path}")
                return

            print(f"📥 Loading spherization from: {yaml_path}")
            data = yaml.safe_load(yaml_path.read_text())
            collision_spheres = data.get("collision_spheres", {})

            # Import spheres
            total_loaded = 0
            for link_name, spheres_data in collision_spheres.items():
                for sphere_data in spheres_data:
                    sphere = self.sphere_store.add(link_name, xyz=tuple(sphere_data["center"]), radius=sphere_data["radius"])
                    self._create_sphere_visualization(sphere)
                    total_loaded += 1

            print(f"✅ Loaded {total_loaded} spheres from {yaml_path.name}")

        except ImportError:
            print("⚠️  PyYAML not installed. Cannot load spherization YAML.")
            print("   Install with: pip install PyYAML")
        except Exception as e:
            print(f"❌ Failed to load spherization YAML: {e}")

    def _add_reference_grid(self):
        """Add a reference grid to the scene."""
        # Get scene bounds to position grid appropriately
        try:
            trimesh_scene = self.urdf_viz._urdf.scene or self.urdf_viz._urdf.collision_scene
            z_pos = trimesh_scene.bounds[0, 2] if trimesh_scene is not None else 0.0
        except:
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
            self.urdf_viz.remove()
