#!/usr/bin/env python3
"""Command-line interface for Bubblify - Interactive URDF spherization tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .gui import BubblifyApp


def main():
    """Main entry point for the Bubblify CLI."""
    parser = argparse.ArgumentParser(
        description="Bubblify - Interactive URDF spherization tool using Viser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  bubblify --urdf_path /path/to/robot.urdf
  bubblify --urdf_path /path/to/robot.urdf --spherization_yml spheres.yml
  bubblify --urdf_path /path/to/robot.urdf --show_collision --port 8081
        """,
    )

    parser.add_argument("--urdf_path", type=Path, required=True, help="Path to URDF file (required)")

    parser.add_argument("--spherization_yml", type=Path, help="Path to existing spherization YAML file to load (optional)")

    parser.add_argument("--port", type=int, default=8080, help="Viser server port (default: 8080)")

    parser.add_argument("--show_collision", action="store_true", help="Show collision meshes in addition to visual meshes")

    args = parser.parse_args()

    # Validate arguments
    if not args.urdf_path.exists():
        print(f"❌ Error: URDF file not found: {args.urdf_path}")
        sys.exit(1)

    if args.spherization_yml is not None and not args.spherization_yml.exists():
        print(f"❌ Error: Spherization YAML file not found: {args.spherization_yml}")
        sys.exit(1)

    # Welcome message
    print("🔮 Welcome to Bubblify - Interactive URDF Spherization Tool!")
    print("=" * 60)
    print(f"📄 Loading URDF: {args.urdf_path}")

    if args.spherization_yml is not None:
        print(f"⚙️  Loading spherization: {args.spherization_yml}")

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
            spherization_yml=args.spherization_yml,
        )

        print("🎮 GUI Controls:")
        print("  • Use 'Robot Controls' to configure joints and visibility")
        print("  • Use 'Sphere Editor' to add and edit collision spheres")
        print("  • Use 'Export' to save your spherization")
        print()
        print("💡 Tips:")
        print("  • Select a link, then add spheres to it")
        print("  • Use the 3D transform gizmo to position spheres")
        print("  • Click on spheres in the 3D view to select them")
        print("  • Toggle mesh visibility and adjust sphere opacity for focus")
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
