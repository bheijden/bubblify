#!/usr/bin/env python3
"""Test script to verify base link fix works across different robot types."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bubblify import BubblifyApp


def test_multiple_robots():
    """Test the base link fix across different robot types."""

    print("🤖 Testing Multiple Robot Types")
    print("=" * 35)

    # Test common robots with different base link naming conventions
    robots_to_test = [
        "panda",  # base link: panda_link0
        "ur10",  # base link: base_link
        "kuka_iiwa",  # base link: iiwa_link_0
    ]

    results = {}

    for robot_name in robots_to_test:
        print(f"\n🔧 Testing {robot_name}:")
        print("-" * 25)

        try:
            app = BubblifyApp(robot_name=robot_name, show_collision=False, port=8089 + len(results))

            # Find base-like links (typically have numbers or "base" in name)
            base_candidates = [
                link
                for link in app.urdf_viz.link_frame.keys()
                if any(keyword in link.lower() for keyword in ["base", "link0", "_0", "world"])
            ]

            # Count links with meshes
            links_with_meshes = [link for link, meshes in app.urdf_viz.link_meshes.items() if len(meshes) > 0]

            total_links = len(app.urdf_viz.link_frame)
            total_meshes = sum(len(meshes) for meshes in app.urdf_viz.link_meshes.values())

            results[robot_name] = {
                "success": True,
                "base_candidates": base_candidates,
                "total_links": total_links,
                "links_with_meshes": len(links_with_meshes),
                "total_meshes": total_meshes,
            }

            print(f"✅ Initialized successfully")
            print(f"🔗 Base link candidates: {base_candidates}")
            print(f"📊 Links: {total_links} total, {len(links_with_meshes)} with meshes")
            print(f"🎯 Total meshes: {total_meshes}")

            # Verify no orphaned meshes
            orphaned = [
                link for link, meshes in app.urdf_viz.link_meshes.items() if meshes and link not in app.urdf_viz.link_frame
            ]

            if orphaned:
                print(f"❌ Orphaned mesh links: {orphaned}")
                results[robot_name]["success"] = False
            else:
                print("✅ All mesh links are selectable")

        except Exception as e:
            print(f"❌ Failed: {e}")
            results[robot_name] = {"success": False, "error": str(e)}

    print(f"\n📊 Summary:")
    print("=" * 20)
    for robot, result in results.items():
        if result["success"]:
            print(f"✅ {robot}: {result['total_links']} links, {result['total_meshes']} meshes")
        else:
            print(f"❌ {robot}: Failed - {result.get('error', 'Unknown error')}")

    successful_tests = sum(1 for r in results.values() if r["success"])
    print(f"\n🎉 {successful_tests}/{len(robots_to_test)} robots tested successfully!")

    return successful_tests == len(robots_to_test)


if __name__ == "__main__":
    success = test_multiple_robots()
    sys.exit(0 if success else 1)
