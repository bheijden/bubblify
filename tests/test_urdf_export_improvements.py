#!/usr/bin/env python3
"""Test script to verify URDF export improvements: XML declaration and collision cleanup."""

import sys
from pathlib import Path
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp
from bubblify.core import inject_spheres_into_urdf_xml


def test_urdf_export_improvements():
    """Test the improved URDF export functionality."""

    print("📋 Testing URDF Export Improvements")
    print("=" * 40)

    # Create a test URDF with existing collision elements
    test_urdf_content = """<?xml version="1.0"?>
<robot name="test_robot">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.1 0.1 0.1"/>
      </geometry>
    </visual>
    <collision>
      <geometry>
        <box size="0.1 0.1 0.1"/>
      </geometry>
    </collision>
  </link>
  <link name="link1">
    <visual>
      <geometry>
        <cylinder radius="0.05" length="0.2"/>
      </geometry>
    </visual>
    <collision name="old_collision">
      <geometry>
        <cylinder radius="0.05" length="0.2"/>
      </geometry>
    </collision>
    <collision name="another_old_collision">
      <geometry>
        <cylinder radius="0.06" length="0.2"/>
      </geometry>
    </collision>
  </link>
  <joint name="joint1" type="fixed">
    <parent link="base_link"/>
    <child link="link1"/>
    <origin xyz="0 0 0.1"/>
  </joint>
</robot>"""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_urdf_path = temp_path / "test_robot.urdf"
        test_urdf_path.write_text(test_urdf_content)

        try:
            print(f"🤖 Loading test URDF with existing collision elements")

            app = BubblifyApp(urdf_path=test_urdf_path, show_collision=False, port=8103)

            # Create test spheres
            sphere1 = app.sphere_store.add("base_link", xyz=(0.0, 0.0, 0.05), radius=0.03)
            sphere2 = app.sphere_store.add("link1", xyz=(0.0, 0.0, 0.1), radius=0.025)
            sphere3 = app.sphere_store.add("link1", xyz=(0.0, 0.0, -0.1), radius=0.02)

            print(f"⚪ Created {len(app.sphere_store.by_id)} test spheres")
            print()

            # Test URDF export
            print("📋 Testing URDF Export:")
            urdf_xml = inject_spheres_into_urdf_xml(test_urdf_path, app.urdf, app.sphere_store)

            # Verify XML declaration
            has_xml_declaration = urdf_xml.startswith('<?xml version="1.0" encoding="utf-8"?>')
            print(f"  ✅ XML declaration: {has_xml_declaration}")

            # Verify old collision elements are removed
            has_old_box_collision = '<box size="0.1 0.1 0.1"/>' in urdf_xml
            has_old_cylinder_collision = '<cylinder radius="0.05" length="0.2"/>' in urdf_xml
            has_old_collision_names = 'name="old_collision"' in urdf_xml

            print(f"  ✅ Old box collision removed: {not has_old_box_collision}")
            print(f"  ✅ Old cylinder collision removed: {not has_old_cylinder_collision}")
            print(f"  ✅ Old collision names removed: {not has_old_collision_names}")

            # Verify new sphere collisions are added
            sphere_count = urdf_xml.count("<sphere")
            collision_count = urdf_xml.count('<collision name="sphere_')

            print(f"  ✅ Sphere elements added: {sphere_count} (expected: {len(app.sphere_store.by_id)})")
            print(f"  ✅ Sphere collisions added: {collision_count} (expected: {len(app.sphere_store.by_id)})")

            # Verify proper formatting
            has_proper_indentation = "\n  <link" in urdf_xml
            has_collision_structure = '<collision name="sphere_' in urdf_xml and "<origin xyz=" in urdf_xml

            print(f"  ✅ Proper indentation: {has_proper_indentation}")
            print(f"  ✅ Complete collision structure: {has_collision_structure}")
            print()

            # Show sample of the cleaned URDF
            print("🔍 Sample of exported URDF:")
            lines = urdf_xml.split("\n")

            # Find first collision element
            collision_start = None
            for i, line in enumerate(lines):
                if 'collision name="sphere_' in line:
                    collision_start = i
                    break

            if collision_start:
                print("First sphere collision element:")
                for i in range(collision_start, min(collision_start + 7, len(lines))):
                    print(f"  {lines[i]}")
            print()

            # Show first few lines including XML declaration
            print("First 10 lines of export:")
            for i, line in enumerate(lines[:10]):
                print(f"  {i + 1:2d}: {line}")
            print()

            # Verify all requirements
            all_tests_passed = (
                has_xml_declaration
                and not has_old_box_collision
                and not has_old_cylinder_collision
                and not has_old_collision_names
                and sphere_count == len(app.sphere_store.by_id)
                and collision_count == len(app.sphere_store.by_id)
                and has_proper_indentation
                and has_collision_structure
            )

            if all_tests_passed:
                print("🎉 All URDF export improvements working correctly!")

                # Save test output for inspection
                output_path = temp_path / "cleaned_export.urdf"
                output_path.write_text(urdf_xml)
                print(f"📁 Test export saved to: {output_path}")

                return True
            else:
                print("❌ Some tests failed!")
                return False

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_urdf_export_improvements()
    if success:
        print("\n✅ URDF export improvements working perfectly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
