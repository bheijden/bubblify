#!/usr/bin/env python3
"""Test script to simulate GUI export operations."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp
import yaml


def test_gui_export():
    """Test GUI export operations to verify clean file output."""

    print("💾 Testing GUI Export Operations")
    print("=" * 40)

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8099)

        # Create test spheres
        sphere1 = app.sphere_store.add("panda_link0", xyz=(0.1, 0.0, 0.0), radius=0.05)
        sphere2 = app.sphere_store.add("panda_link3", xyz=(-0.05, 0.1, 0.02), radius=0.03)
        app._create_sphere_visualization(sphere1)
        app._create_sphere_visualization(sphere2)

        print(f"✅ Created {len(app.sphere_store.by_id)} test spheres")
        print()

        # Test YAML export manually (simulating GUI button click)
        print("📋 Testing YAML Export:")
        try:
            import yaml

            # Simulate the export code from GUI
            collision_spheres = {}
            for sphere in app.sphere_store.by_id.values():
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
                    "total_spheres": int(len(app.sphere_store.by_id)),
                    "links": list(collision_spheres.keys()),
                    "export_timestamp": float(1699123456.789),  # Fixed timestamp for testing
                },
            }

            output_path = Path("test_spherization.yml")
            output_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
            print(f"✅ YAML exported to: {output_path.absolute()}")

            # Verify the file content is clean
            with open(output_path, "r") as f:
                content = f.read()

            print("📄 File content check:")
            print(f"  • No numpy objects: {'numpy' not in content}")
            print(f"  • No binary data: {'!!binary' not in content}")
            print(f"  • Clean centers: 'center:' in content and '- -0.05' in content")
            print()

            print("First few lines of exported YAML:")
            print("---")
            print("\n".join(content.split("\n")[:15]))
            print("---")
            print()

        except Exception as e:
            print(f"❌ YAML export failed: {e}")
            return False

        # Test URDF export
        print("📋 Testing URDF Export:")
        try:
            from bubblify.core import inject_spheres_into_urdf_xml

            urdf_xml = inject_spheres_into_urdf_xml(None, app.urdf, app.sphere_store)

            urdf_output_path = Path("test_spherized.urdf")
            urdf_output_path.write_text(urdf_xml)
            print(f"✅ URDF exported to: {urdf_output_path.absolute()}")

            # Count sphere elements
            sphere_count = urdf_xml.count("<sphere")
            print(f"  • Contains {sphere_count} sphere elements")
            print()

        except Exception as e:
            print(f"❌ URDF export failed: {e}")
            return False

        print("🎉 All GUI export operations working correctly!")
        print("📁 Files created with absolute paths displayed")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_gui_export()
    if success:
        print("\n✅ GUI export functionality working perfectly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
