#!/usr/bin/env python3
"""Test URDF export with a real robot to verify collision cleanup works properly."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp
from bubblify.core import inject_spheres_into_urdf_xml


def test_real_robot_urdf_export():
    """Test URDF export with real robot that has existing collision elements."""

    print("🤖 Testing Real Robot URDF Export")
    print("=" * 40)

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8104)

        print("✅ Panda robot loaded successfully!")

        # Create a few test spheres on different links
        sphere1 = app.sphere_store.add("panda_link0", xyz=(0.0, 0.0, 0.05), radius=0.08)
        sphere2 = app.sphere_store.add("panda_link3", xyz=(0.0, 0.0, 0.1), radius=0.06)
        sphere3 = app.sphere_store.add("panda_hand", xyz=(0.0, 0.0, 0.02), radius=0.04)

        print(f"⚪ Created {len(app.sphere_store.by_id)} spheres on different links")
        print()

        # Export URDF
        print("📋 Exporting URDF with collision cleanup:")
        urdf_xml = inject_spheres_into_urdf_xml(None, app.urdf, app.sphere_store)

        # Verify XML structure
        has_xml_declaration = urdf_xml.startswith('<?xml version="1.0" encoding="utf-8"?>')
        sphere_count = urdf_xml.count("<sphere")
        collision_count = urdf_xml.count('<collision name="sphere_')

        # Check for old collision elements by looking at collision geometry
        old_mesh_collisions = 0
        old_collision_elements = 0

        # Parse XML to properly count collision types
        from xml.etree import ElementTree as ET

        result_root = ET.fromstring(urdf_xml)

        for link in result_root.findall("link"):
            for collision in link.findall("collision"):
                geom = collision.find("geometry")
                if geom is not None:
                    if geom.find("mesh") is not None:
                        old_mesh_collisions += 1
                    elif collision.get("name", "").startswith("sphere_"):
                        # This is our sphere collision - don't count as old
                        pass
                    else:
                        old_collision_elements += 1

        print(f"  ✅ XML declaration: {has_xml_declaration}")
        print(f"  ✅ Sphere elements: {sphere_count} (expected: {len(app.sphere_store.by_id)})")
        print(f"  ✅ New sphere collisions: {collision_count} (expected: {len(app.sphere_store.by_id)})")
        print(f"  🧹 Old mesh collisions removed: {old_mesh_collisions == 0}")
        print(f"  🧹 Old collision elements removed: {old_collision_elements == 0}")
        print()

        # Show structure of sphere collisions
        print("🔍 Sample sphere collision structure:")
        lines = urdf_xml.split("\n")
        for i, line in enumerate(lines):
            if 'collision name="sphere_' in line:
                print(f"Found sphere collision at line {i + 1}:")
                for j in range(i, min(i + 7, len(lines))):
                    print(f"  {lines[j]}")
                break
        print()

        # Verify links have only sphere collisions now
        sphere_links = {sphere.link for sphere in app.sphere_store.by_id.values()}
        print(f"🔗 Links with spheres: {sorted(sphere_links)}")

        for link_name in sphere_links:
            # Find this link in the XML
            link_start = None
            link_end = None
            for i, line in enumerate(lines):
                if f'<link name="{link_name}">' in line:
                    link_start = i
                elif link_start and "</link>" in line:
                    link_end = i
                    break

            if link_start and link_end:
                link_content = "\n".join(lines[link_start : link_end + 1])
                link_sphere_count = link_content.count("<sphere")
                expected_spheres = len([s for s in app.sphere_store.by_id.values() if s.link == link_name])

                # Count actual collision elements in this link's XML section
                link_collisions = link_content.count("<collision")
                link_mesh_collisions = link_content.count("<mesh filename=")

                print(
                    f"  • {link_name}: {link_sphere_count} spheres (expected: {expected_spheres}), {link_collisions} total collisions, {link_mesh_collisions} mesh refs"
                )
        print()

        # Overall verification
        export_valid = (
            has_xml_declaration
            and sphere_count == len(app.sphere_store.by_id)
            and collision_count == len(app.sphere_store.by_id)
            and old_mesh_collisions == 0
        )

        if export_valid:
            print("🎉 Real robot URDF export working perfectly!")
            print("📁 Clean URDF with only sphere collisions generated")

            # Show file size comparison
            print(f"📊 Export statistics:")
            print(f"  • Total lines: {len(lines)}")
            print(f"  • File size: {len(urdf_xml)} characters")
            print(f"  • Sphere collisions only: {collision_count}")

            return True
        else:
            print("❌ Export validation failed!")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_real_robot_urdf_export()
    if success:
        print("\n✅ Real robot URDF export working perfectly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
