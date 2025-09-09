
# Bubblify: Interactive URDF Spherization Tool

<p align="center">
  <img src="https://github.com/bheijden/bubblify/tree/master/public/spherization_xarm6.png" width="45%"/>
  <img src="https://github.com/bheijden/bubblify/tree/master/public/spherization_openarm.png" width="35.9%"/>
</p>



## Overview

Bubblify is an interactive tool for creating spherical approximations of robot geometries directly from Universal Robot Description Format (URDF) specifications. It provides an intuitive 3D interface for placing collision spheres on robot links, enabling efficient collision checking for motion planning applications.

Spherized meshes can significantly reduce the computational load of collision detection, have better support across simulators, and maintain accurate approximations of the source robot model while fixing mesh defects.

## Installation
<p align="left">
<a href="https://pypi.org/project/viser/">
    <img alt="codecov" src="https://img.shields.io/pypi/pyversions/viser" />
</a>
</p>

Install Bubblify directly from PyPI:

```bash
pip install bubblify
```

## Usage

### Basic Usage

Launch Bubblify with a URDF file:

```bash
bubblify --urdf_path path/to/your/robot.urdf
```

### Command Line Options

- `--urdf_path` (required): Path to the URDF file to spherize
- `--spherization_yml` (optional): Load an existing spherization configuration
- `--port` (optional): Port for the web interface (default: 8080)
- `--show_collision` (optional): Display collision meshes (default: False)

### Example Commands

```bash
# Basic usage
bubblify --urdf_path ./assets/xarm6/xarm6_rs.urdf

# Load with existing spherization
bubblify --urdf_path ./assets/xarm6/xarm6_rs.urdf --spherization_yml ./config/xarm6_spheres.yml

# Custom port and show collision meshes
bubblify --urdf_path ./robot.urdf --port 8081 --show_collision
```

## Interactive Features

### Demo Video
<p align="center">
  <video width="80%" controls onloadedmetadata="this.defaultPlaybackRate=2; this.playbackRate=2;">
    <source src="https://github.com/bheijden/bubblify/tree/master/public/bubblify_demo.mp4" type="video/mp4">
    Your browser does not support the video tag.
  </video>
</p>

## Benefits for Motion Planning

Spherical approximations offer several key advantages for robotics applications:

### Computational Efficiency
- **Fast Collision Detection**: Sphere-sphere and sphere-primitive collision checks are computationally simple
- **Reduced Query Time**: Orders of magnitude faster than mesh-based collision detection
- **Real-time Planning**: Enables real-time motion planning for complex robots

### Robustness
- **Numerical Stability**: Spheres eliminate mesh artifacts and numerical precision issues
- **Consistent Geometry**: Uniform collision representation across different simulators
- **Simplified Physics**: More stable physics simulation with primitive shapes

### Motion Planning Integration
- **Sampling-based Planners**: Faster collision checking enables more thorough space exploration
- **Optimization-based Methods**: Smooth distance gradients improve trajectory optimization
- **Multi-robot Systems**: Efficient collision checking scales better with robot count

### Compatible Motion Planning Libraries
Bubblify's spherized URDFs and YAMLs work with modern motion planning frameworks:
- **[cuRobo](https://curobo.org/)**: NVIDIA's CUDA-accelerated motion planning library
- **[VAMP](https://github.com/KavrakiLab/vamp)**: Vectorized Approximate Motion Planning

## File Formats

### Input
- **URDF Files**: Standard Robot Description Format with visual and collision meshes

### Output
- **Spherized URDF**: New URDF file with collision geometries replaced by spheres
- **Configuration YAML**: Spherization parameters for reproducible results

### Example Configuration
```yaml
spheres:
  - link: "base_link"
    position: [0.0, 0.0, 0.1]
    radius: 0.08
  - link: "link1"
    position: [0.0, 0.0, 0.15]
    radius: 0.06
```

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.