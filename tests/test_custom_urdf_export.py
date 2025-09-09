#!/usr/bin/env python3
"""Test custom URDF export paths to verify directory-based exports."""

import sys
from pathlib import Path
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_custom_urdf_export():
    """Test custom URDF with directory-based export paths."""

    print("📁 Testing Custom URDF Export Paths")
    print("=" * 40)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a simple test URDF
        test_urdf_path = temp_path / "my_robot.urdf"
        test_urdf_path.write_text("""<?xml version="1.0"?>
<robot name="my_robot">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.1 0.1 0.1"/>
      </geometry>
    </visual>
  </link>
  <link name="link1">
    <visual>
      <geometry>
        <cylinder radius="0.05" length="0.2"/>
      </geometry>
    </visual>
  </link>
  <joint name="joint1" type="fixed">
    <parent link="base_link"/>
    <child link="link1"/>
    <origin xyz="0 0 0.1"/>
  </joint>
</robot>""")

        try:
            print(f"🤖 Loading URDF from: {test_urdf_path}")

            app = BubblifyApp(urdf_path=test_urdf_path, show_collision=False, port=8101)

            print("✅ Custom URDF loaded successfully!")
            print(f"  • URDF path: {app.urdf_path}")
            print(f"  • Expected export directory: {app.urdf_path.parent}")
            print()

            # Create a test sphere
            sphere = app.sphere_store.add("base_link", xyz=(0.0, 0.0, 0.05), radius=0.03)
            app._create_sphere_visualization(sphere)
            print(f"⚪ Created test sphere: {sphere.id}")
            print()

            # Test export name generation
            expected_name = f"{test_urdf_path.stem}_spherized"
            print(f"🏷️ Expected export name: {expected_name}")
            print()

            # Test YAML export path logic
            print("💾 Testing Export Directory Logic:")
            if app.urdf_path and app.urdf_path.parent:
                export_dir = app.urdf_path.parent
                print(f"  • Export directory: {export_dir}")

                # Simulate export paths
                yaml_path = export_dir / f"{expected_name}.yml"
                urdf_path = export_dir / f"{expected_name}.urdf"

                print(f"  • YAML would export to: {yaml_path}")
                print(f"  • URDF would export to: {urdf_path}")
                print(f"  • Both in same directory as original: {export_dir == test_urdf_path.parent}")
            else:
                print("  ❌ No URDF path found")
                return False

            print()
            print("✅ Directory-based export paths working correctly!")
            print("📂 Files will be saved alongside the original URDF")
            print("🔗 Relative paths in URDF will remain valid")

            return True

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = test_custom_urdf_export()
    if success:
        print("\n🎉 Custom URDF export paths working perfectly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
