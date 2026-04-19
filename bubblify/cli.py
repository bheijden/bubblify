#!/usr/bin/env python3
"""Command-line interface for Bubblify - Interactive URDF geometry configuration tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .gui import BubblifyApp


def main():
    """Main entry point for the Bubblify CLI."""
    parser = argparse.ArgumentParser(
        description="Bubblify - Interactive URDF geometry configuration tool using Viser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  bubblify --urdf_path /path/to/robot.urdf
  bubblify --urdf_path /path/to/robot.urdf --geometry_config geometries.yml
  bubblify --urdf_path /path/to/robot.urdf --show_collision --port 8081
        """,
    )

    parser.add_argument("--urdf_path", type=Path, required=True, help="Path to URDF file (required)")

    parser.add_argument(
        "--geometry_config",
        type=Path,
        help="Path to existing geometry configuration YAML file to load (optional)",
    )

    parser.add_argument("--port", type=int, default=8080, help="Viser server port (default: 8080)")

    parser.add_argument(
        "--show_collision",
        action="store_true",
        help="Show collision meshes in addition to visual meshes",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.urdf_path.exists():
        print(f"❌ Error: URDF file not found: {args.urdf_path}")
        sys.exit(1)

    if args.geometry_config is not None and not args.geometry_config.exists():
        print(f"❌ Error: Geometry configuration YAML file not found: {args.geometry_config}")
        sys.exit(1)

    # Welcome message
    print("🔮 Welcome to Bubblify - Interactive URDF Spherization Tool!")
    print("=" * 60)
    print(f"📄 Loading URDF: {args.urdf_path}")

    if args.geometry_config is not None:
        print(f"⚙️  Loading geometry configuration: {args.geometry_config}")

    print(f"🌐 Server will start on port {args.port}")
    print(f"🔍 Show collision meshes: {'Yes' if args.show_collision else 'No'}")
    print()

    try:
        # Create and run the application
        app = BubblifyApp(
            robot_name="custom",
            urdf_path=args.urdf_path,
            show_collision=args.show_collision,
            port=args.port,
            geometry_config=args.geometry_config,
        )

        print("🎮 GUI Controls:")
        print("  • Use 'Robot Controls' to configure joints and visibility")
        print("  • Use 'Geometry Editor' to add and edit collision geometries")
        print("  • Use 'Export' to save your geometry configuration")
        print()
        print("💡 Tips:")
        print("  • Select a link, then add geometries to it")
        print("  • Use the 3D transform gizmo to position geometries")
        print("  • Click on geometries in the 3D view to select them")
        print("  • Toggle mesh visibility and adjust geometry opacity for focus")
        print("  • Export YAML for quick save/load, URDF for final use")
        print()

        # Run the application
        app.run()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you have installed bubblify and its dependencies:")
        print("   pip install bubblify")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("💡 Check your URDF path and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()
