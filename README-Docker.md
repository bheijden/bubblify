# Docker Usage

## Quick Start

### Docker Compose (Recommended)
```bash
docker compose up
```

### Direct Docker
```bash
docker run -p 8080:8080 bubblify:latest
```

Access at `http://localhost:8080`

## Docker Compose Options

### Custom port
```bash
BUBBLIFY_PORT=8081 docker compose up
```

### Different URDF
```bash
BUBBLIFY_URDF_PATH=./assets/xarm6/xarm6_dual_rs.urdf docker compose up
```

### With spherization
```bash
BUBBLIFY_SPHERIZATION_YML=./assets/xarm6/xarm6_rs_spherized.yml docker compose up
```

### Show collision
```bash
BUBBLIFY_SHOW_COLLISION=1 docker compose up
```

### All options
```bash
BUBBLIFY_URDF_PATH=./assets/xarm6/xarm6_dual_rs.urdf BUBBLIFY_PORT=8081 BUBBLIFY_SPHERIZATION_YML=./assets/xarm6/xarm6_dual_rs_spherized.yml BUBBLIFY_SHOW_COLLISION=1 docker compose up
```

## Direct Docker Commands

### Basic usage
```bash
# Default settings
docker run -p 8080:8080 bubblify:latest

# Custom port
docker run -p 8081:8081 bubblify:latest --port 8081

# Different URDF file
docker run -p 8080:8080 -v $(pwd)/assets:/home/bubblify/app/assets:ro bubblify:latest --urdf_path ./assets/xarm6/xarm6_dual_rs.urdf --port 8080
```

### Advanced usage
```bash
# With spherization file
docker run -p 8080:8080 \
  -v $(pwd)/assets:/home/bubblify/app/assets:ro \
  -v $(pwd)/config:/home/bubblify/app/config:ro \
  bubblify:latest \
  --urdf_path ./assets/xarm6/xarm6_rs.urdf \
  --spherization_yml ./config/spheres.yml \
  --port 8080

# Show collision meshes
docker run -p 8080:8080 \
  -v $(pwd)/assets:/home/bubblify/app/assets:ro \
  bubblify:latest \
  --urdf_path ./assets/xarm6/xarm6_rs.urdf \
  --port 8080 \
  --show_collision

# All options
docker run -p 8081:8081 \
  -v $(pwd)/assets:/home/bubblify/app/assets:ro \
  -v $(pwd)/config:/home/bubblify/app/config:ro \
  -v $(pwd)/output:/home/bubblify/app/output \
  bubblify:latest \
  --urdf_path ./assets/xarm6/xarm6_dual_rs.urdf \
  --spherization_yml ./config/spheres.yml \
  --port 8081 \
  --show_collision
```

### Container management
```bash
# Run in background
docker run -d --name bubblify -p 8080:8080 bubblify:latest

# View logs
docker logs bubblify

# Stop container
docker stop bubblify

# Remove container
docker rm bubblify

# Access container shell
docker exec -it bubblify bash
```

## Build

### Docker Compose
```bash
docker compose build
```

### Direct Docker
```bash
docker build -t bubblify:latest .
```
