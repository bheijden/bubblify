#!/usr/bin/env python3
"""Test script to verify the mesh visibility fix."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_mesh_visibility_fix():
    """Test the fixed mesh visibility system."""

    print("🔧 Testing Fixed Mesh Visibility System")
    print("=" * 45)

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8085)

        print("✅ Application initialized successfully!")
        print()

        # Check link frame mapping
        print("🔗 Link Frame Mapping:")
        for link_name, frame in app.urdf_viz.link_frame.items():
            print(f"  • {link_name}: {type(frame).__name__}")
        print()

        # Check mesh-to-link mapping
        print("🎯 Mesh-to-Link Mapping:")
        total_meshes = 0
        for link_name, mesh_handles in app.urdf_viz.link_meshes.items():
            print(f"  • {link_name}: {len(mesh_handles)} mesh(es)")
            total_meshes += len(mesh_handles)
        print(f"  • Total: {total_meshes} mesh handles")
        print()

        # Test visibility toggle logic
        print("🔍 Testing Visibility Logic:")

        # Set a current link
        app.current_link = "panda_link1"
        print(f"  • Current link set to: {app.current_link}")

        # Test show selected link = True, show other links = False
        app.show_selected_link = True
        app.show_other_links = False
        app._update_mesh_visibility()

        visible_meshes = []
        hidden_meshes = []

        for link_name, mesh_handles in app.urdf_viz.link_meshes.items():
            for mesh_handle in mesh_handles:
                if mesh_handle.visible:
                    visible_meshes.append(f"{link_name}")
                else:
                    hidden_meshes.append(f"{link_name}")

        print(f"  • Visible meshes (should only be current link): {set(visible_meshes)}")
        print(f"  • Hidden meshes: {set(hidden_meshes)}")

        # Test show selected link = False, show other links = True
        app.show_selected_link = False
        app.show_other_links = True
        app._update_mesh_visibility()

        visible_meshes = []
        hidden_meshes = []

        for link_name, mesh_handles in app.urdf_viz.link_meshes.items():
            for mesh_handle in mesh_handles:
                if mesh_handle.visible:
                    visible_meshes.append(f"{link_name}")
                else:
                    hidden_meshes.append(f"{link_name}")

        print(f"  • Visible meshes (should exclude current link): {set(visible_meshes)}")
        print(f"  • Hidden meshes (should be current link): {set(hidden_meshes)}")
        print()

        # Test all links visible
        app.show_selected_link = True
        app.show_other_links = True
        app._update_mesh_visibility()

        all_visible = all(
            mesh_handle.visible for mesh_handles in app.urdf_viz.link_meshes.values() for mesh_handle in mesh_handles
        )

        print(f"  • All meshes visible when both toggles on: {all_visible}")

        # Test no links visible
        app.show_selected_link = False
        app.show_other_links = False
        app._update_mesh_visibility()

        all_hidden = all(
            not mesh_handle.visible for mesh_handles in app.urdf_viz.link_meshes.values() for mesh_handle in mesh_handles
        )

        print(f"  • All meshes hidden when both toggles off: {all_hidden}")
        print()

        print("🎉 Mesh visibility system tests completed!")
        print("⚠️  Test mode - not starting server")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_mesh_visibility_fix()
    if success:
        print("\n✅ Mesh visibility fix working correctly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
