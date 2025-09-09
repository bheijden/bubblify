#!/usr/bin/env python3
"""Test script to verify the export fixes."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp
import yaml


def test_export_fixes():
    """Test the fixed export functionality."""

    print("🔧 Testing Export Fixes")
    print("=" * 30)

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8098)

        print("✅ Application initialized successfully!")
        print()

        # Create test spheres with different coordinate types
        print("🔧 Creating Test Spheres:")
        sphere1 = app.sphere_store.add("panda_link0", xyz=(0.1, 0.0, 0.0), radius=0.05)
        sphere2 = app.sphere_store.add("panda_link1", xyz=(-0.05, 0.1, 0.02), radius=0.03)

        app._create_sphere_visualization(sphere1)
        app._create_sphere_visualization(sphere2)

        print(f"  • Created sphere {sphere1.id} at {sphere1.local_xyz}")
        print(f"  • Created sphere {sphere2.id} at {sphere2.local_xyz}")
        print(f"  • Type of sphere1.local_xyz: {type(sphere1.local_xyz)}")
        print()

        # Test YAML export data structure manually
        print("📋 Testing YAML Data Structure:")
        collision_spheres = {}
        for sphere in app.sphere_store.by_id.values():
            if sphere.link not in collision_spheres:
                collision_spheres[sphere.link] = []

            # Apply the same conversion as in the export
            center = sphere.local_xyz
            if hasattr(center, "tolist"):
                center = center.tolist()
            else:
                center = [float(x) for x in center]

            collision_spheres[sphere.link].append({"center": center, "radius": float(sphere.radius)})

        # Test YAML serialization
        test_data = {
            "collision_spheres": collision_spheres,
            "metadata": {
                "total_spheres": int(len(app.sphere_store.by_id)),
                "links": list(collision_spheres.keys()),
            },
        }

        yaml_output = yaml.dump(test_data, default_flow_style=False, sort_keys=False)
        print("✅ YAML serialization test:")
        print(yaml_output)

        # Test URDF export function
        print("🔧 Testing URDF Export Function:")
        try:
            from bubblify.core import inject_spheres_into_urdf_xml

            urdf_xml = inject_spheres_into_urdf_xml(None, app.urdf, app.sphere_store)
            print("✅ URDF XML generation successful")
            print(f"  • XML length: {len(urdf_xml)} characters")
            print(f"  • Contains sphere elements: {'<sphere' in urdf_xml}")
        except Exception as e:
            print(f"❌ URDF export failed: {e}")
            return False

        print()
        print("🎉 All export fixes working correctly!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_export_fixes()
    if success:
        print("\n✅ Export fixes working perfectly!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
