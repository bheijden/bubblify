"""Bubblify - Interactive URDF spherization tool using Viser.

This package provides tools for creating and editing sphere-based collision
representations of robot URDFs using an interactive Viser-based GUI.
"""

from .core import EnhancedViserUrdf, Geometry, GeometryStore
from .gui import BubblifyApp


__all__ = ["Geometry", "GeometryStore", "EnhancedViserUrdf", "BubblifyApp"]
__version__ = "0.1.0"
