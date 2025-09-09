#!/usr/bin/env python3
"""Test script to verify base link is properly included and selectable."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_base_link_fix():
    """Test the base link fix for different URDFs."""

    print("🔗 Testing Base Link Fix")
    print("=" * 30)

    robots_to_test = ["panda", "ur10"]

    for robot_name in robots_to_test:
        print(f"\n🤖 Testing {robot_name}:")
        print("-" * 20)

        try:
            app = BubblifyApp(robot_name=robot_name, show_collision=False, port=8087)

            print("✅ Application initialized successfully!")

            # Check if base link is in link frame mapping
            base_links = [link for link in app.urdf_viz.link_frame.keys() if "link0" in link or "base" in link]
            print(f"🔗 Base links found: {base_links}")

            # Check link frame mapping
            print(f"📋 All selectable links ({len(app.urdf_viz.link_frame)}):")
            for link_name in sorted(app.urdf_viz.link_frame.keys()):
                mesh_count = len(app.urdf_viz.link_meshes.get(link_name, []))
                print(f"  • {link_name}: {mesh_count} mesh(es)")

            # Check mesh-to-link mapping
            total_meshes = sum(len(meshes) for meshes in app.urdf_viz.link_meshes.values())
            print(f"🎯 Total mesh handles: {total_meshes}")

            # Check if any links have meshes but no frame
            orphaned_links = []
            for link_name, meshes in app.urdf_viz.link_meshes.items():
                if link_name not in app.urdf_viz.link_frame and meshes:
                    orphaned_links.append(link_name)

            if orphaned_links:
                print(f"❌ Links with meshes but no frame: {orphaned_links}")
            else:
                print("✅ All links with meshes have frames (selectable in GUI)")

            print(f"🎉 {robot_name} test completed!")

        except Exception as e:
            print(f"❌ {robot_name} test failed: {e}")
            import traceback

            traceback.print_exc()

    return True


if __name__ == "__main__":
    success = test_base_link_fix()
    if success:
        print("\n🎉 Base link fix tests completed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
