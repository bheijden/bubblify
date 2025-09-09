#!/usr/bin/env python3
"""Quick test script for the simplified Bubblify interface."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_bubblify():
    """Test the simplified Bubblify application with a simple robot."""

    print("🧪 Testing simplified Bubblify interface...")

    try:
        app = BubblifyApp(robot_name="panda", show_collision=False, port=8081)

        print("✅ Bubblify app created successfully!")
        print("📋 Simplified GUI features:")
        print("  • Clean robot controls with joint sliders")
        print("  • Simple link/sphere selection dropdowns")
        print("  • Interactive transform controls for sphere positioning")
        print("  • Streamlined visibility controls")
        print("  • Simplified export options")
        print()
        print("🎮 Usage:")
        print("  1. Select a link from the dropdown")
        print("  2. Click 'Add Sphere' to create a new sphere")
        print("  3. Use the 3D transform gizmo to position the sphere")
        print("  4. Adjust radius and color with sliders")
        print("  5. Export to JSON or URDF when done")
        print()
        print("💡 Improvements made:")
        print("  • Removed bloated position controls")
        print("  • Single transform control (not multiple)")
        print("  • User-friendly sphere ID dropdown")
        print("  • Consolidated visibility controls")
        print("  • Clickable spheres for selection")

        # Don't actually run the server in test mode
        print("\n⚠️  Test mode - not starting server")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_bubblify()
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
