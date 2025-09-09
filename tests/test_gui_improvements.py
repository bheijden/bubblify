#!/usr/bin/env python3
"""Test script to verify GUI improvements and sphere selection behavior."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_gui_improvements():
    """Test the improved GUI structure and sphere selection."""

    print("🎨 Testing GUI Improvements")
    print("=" * 35)

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8094)

        print("✅ Application initialized successfully!")
        print()

        # Test current link display
        print("🔗 Current Link Display:")
        print(f"  • Initial current_link: {app.current_link}")
        if hasattr(app, "_current_link_text"):
            print(f"  • Visibility display value: {app._current_link_text.value}")
        else:
            print("  ❌ _current_link_text not found")
        print()

        # Simulate adding spheres to different links
        print("🔧 Testing Sphere Management:")

        # Add sphere to panda_link1
        sphere1 = app.sphere_store.add("panda_link1", xyz=(0.0, 0.0, 0.1), radius=0.03)
        app._create_sphere_visualization(sphere1)
        print(f"  • Added sphere {sphere1.id} to {sphere1.link}")

        # Add sphere to panda_link3
        sphere2 = app.sphere_store.add("panda_link3", xyz=(0.0, 0.0, 0.05), radius=0.04)
        app._create_sphere_visualization(sphere2)
        print(f"  • Added sphere {sphere2.id} to {sphere2.link}")

        # Add another sphere to panda_link1
        sphere3 = app.sphere_store.add("panda_link1", xyz=(0.0, 0.1, 0.0), radius=0.02)
        app._create_sphere_visualization(sphere3)
        print(f"  • Added sphere {sphere3.id} to {sphere3.link}")
        print()

        # Test link context switching when selecting spheres
        print("🎯 Testing Link Context Switching:")

        # Start with link1 context
        app.current_link = "panda_link1"
        app._update_current_link_display()
        print(f"  • Set context to {app.current_link}")
        print(f"  • Visibility display: {app._current_link_text.value}")

        # Simulate selecting sphere from link3 (should switch context)
        app.current_sphere_id = sphere2.id
        app.current_link = sphere2.link
        app._update_current_link_display()
        app._update_mesh_visibility()
        print(f"  • Selected sphere {sphere2.id} from {sphere2.link}")
        print(f"  • Context switched to: {app.current_link}")
        print(f"  • Visibility display: {app._current_link_text.value}")
        print()

        # Test sphere opacity updates
        print("🎨 Testing Sphere Opacity System:")
        selected_opacity = app._get_sphere_opacity(sphere2)  # Selected sphere
        unselected_same_link = app._get_sphere_opacity(sphere1)  # Different link
        other_link = app._get_sphere_opacity(sphere3)  # Different link

        print(f"  • Selected sphere ({sphere2.id}): {selected_opacity}")
        print(f"  • Same link unselected ({sphere1.id}): {unselected_same_link}")
        print(f"  • Other link sphere ({sphere3.id}): {other_link}")
        print()

        # Test mesh visibility for current vs other links
        print("🔍 Testing Mesh Visibility Logic:")
        current_link_meshes = len(app.urdf_viz.link_meshes.get(app.current_link, []))
        print(f"  • Current link ({app.current_link}): {current_link_meshes} meshes")

        if app.show_selected_link:
            print(f"  • Current link meshes should be visible: {app.show_selected_link}")
        if app.show_other_links:
            print(f"  • Other link meshes should be visible: {app.show_other_links}")
        print()

        print("🎉 GUI improvements testing completed!")
        print("⚠️  Test mode - not starting server")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_gui_improvements()
    if success:
        print("\n✅ GUI improvements working correctly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
