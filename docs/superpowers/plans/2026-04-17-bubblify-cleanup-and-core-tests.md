# Bubblify 清理 + Core 测试安全网 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清掉 Bubblify 为"upstream 合并"保留的向后兼容代码路径、修一处重复 import bug、把 YAML load/dump 的数据层从 `gui.py` 剥到 `core.py`、并为 `core.py` 建立 pytest 回归安全网。

**Architecture:** 9 个 Task 按顺序执行（Task 0 建分支，Task 1-8 对应 spec §执行步骤 的 8 步，Task 9 全局回归）。每个 Task 一次 commit。数据层重构采用"先迁移保行为、写测试、再清理兼容代码"的交错顺序，测试在清理前写好作为安全网。

**Tech Stack:** Python ≥ 3.8、`viser`、`yourdfpy`、`pyyaml`（运行时已经间接依赖）、`pytest` + `pytest-cov`（dev group）、`ruff`、`uv`。

**Spec reference:** `docs/superpowers/specs/2026-04-17-cleanup-and-core-tests-design.md`

**Branch:** `cleanup/core-tests`（从 `master` 切出）

---

## Task 0: 建 `cleanup/core-tests` 分支

**Files:** 无（git 操作）

- [ ] **Step 1: 确认当前在 `master` 且 working tree 干净**

Run: `git status && git branch --show-current`
Expected: `master`，working tree clean（spec commit 已推过）

- [ ] **Step 2: 创建并切到新分支**

Run: `git checkout -b cleanup/core-tests`
Expected: `Switched to a new branch 'cleanup/core-tests'`

- [ ] **Step 3: 确认分支**

Run: `git branch --show-current`
Expected: `cleanup/core-tests`

---

## Task 1: 修 `gui.py:15-21` 重复 import

**Files:**
- Modify: `bubblify/gui.py:15-21`

**Problem:** `inject_geometries_into_urdf_xml` 在 import 块里写了两次（第 19、20 行）。Python 不报错但属于显式冗余。

- [ ] **Step 1: 替换 import 块**

Edit `bubblify/gui.py` 第 15-21 行，把：

```python
from .core import (
    EnhancedViserUrdf,
    Geometry,
    GeometryStore,
    inject_geometries_into_urdf_xml,
    inject_geometries_into_urdf_xml,
)
```

改为：

```python
from .core import (
    EnhancedViserUrdf,
    Geometry,
    GeometryStore,
    inject_geometries_into_urdf_xml,
)
```

- [ ] **Step 2: 跑 ruff 确认**

Run: `uv run ruff check .`
Expected: `All checks passed!`（或至少不出现和 `gui.py:15-21` 相关的新错误）

- [ ] **Step 3: 跑 Python import 冒烟**

Run: `python -c "from bubblify import BubblifyApp; print('ok')"`
Expected: `ok`（无 ImportError）

- [ ] **Step 4: Commit**

```bash
git add bubblify/gui.py
git commit -m "fix(gui): remove duplicate inject_geometries_into_urdf_xml import"
```

---

## Task 2: 删 `Sphere` / `SphereStore` / `get_spheres_for_link` 向后兼容别名

**Files:**
- Modify: `bubblify/core.py:136-137, 226-229, 232-233`
- Modify: `bubblify/__init__.py:7, 10`

**Scope:** 纯 Python API 别名，维护者没要求保留。grep 确认无 `bubblify/` 内部引用这些名字（`gui.py:305` 只是字符串字面量 "Sphere Properties" 不相关）。

- [ ] **Step 1: 删 `core.py` 中的 `Sphere = Geometry`**

Edit `bubblify/core.py`，删除第 136-137 行两行：

```python
# For backward compatibility
Sphere = Geometry
```

保留上下文（第 135 行空行和第 138 行空行之间）。

- [ ] **Step 2: 删 `GeometryStore.get_spheres_for_link`**

Edit `bubblify/core.py`，删除第 226-229 行四行：

```python
    # Backward compatibility methods
    def get_spheres_for_link(self, link: str) -> List[Geometry]:
        """Get all geometries attached to a specific link (backward compatibility)."""
        return self.get_geometries_for_link(link)
```

- [ ] **Step 3: 删 `SphereStore = GeometryStore`**

Edit `bubblify/core.py`，删除第 232-233 行两行：

```python
# For backward compatibility
SphereStore = GeometryStore
```

- [ ] **Step 4: 同步 `__init__.py`**

Edit `bubblify/__init__.py`，第 7 行和第 10 行分别从：

```python
from .core import Sphere, SphereStore, EnhancedViserUrdf
```

改为：

```python
from .core import EnhancedViserUrdf, Geometry, GeometryStore
```

以及：

```python
__all__ = ["Sphere", "SphereStore", "EnhancedViserUrdf", "BubblifyApp"]
```

改为：

```python
__all__ = ["Geometry", "GeometryStore", "EnhancedViserUrdf", "BubblifyApp"]
```

- [ ] **Step 5: 跑 ruff**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: 跑 import 冒烟**

Run: `python -c "from bubblify import BubblifyApp, Geometry, GeometryStore, EnhancedViserUrdf; print('ok')"`
Expected: `ok`

Run: `python -c "from bubblify import Sphere" 2>&1 | head -5`
Expected: `ImportError: cannot import name 'Sphere'`（证明已删）

- [ ] **Step 7: Commit**

```bash
git add bubblify/core.py bubblify/__init__.py
git commit -m "refactor(core): remove Sphere/SphereStore/get_spheres_for_link aliases

These were backward-compat shims from the initial sphere-only API. The
project is 0.1.0 alpha and no external consumer depends on these names;
GeometryStore + Geometry is the single source of truth."
```

---

## Task 3: `display_as_capsule` 旁加 UI 警告 markdown

**Files:**
- Modify: `bubblify/gui.py:340-345`

**Goal:** capsule 仅影响 3D 渲染，导出 URDF 会按 cylinder 处理——在复选框下方明确提示，消除用户心智误导。

- [ ] **Step 1: 在 `add_checkbox` 之后插入一行 warning markdown**

Edit `bubblify/gui.py` 第 340-345 行，在 `cylinder_as_capsule` 添加和保存之间插入一行。原代码：

```python
                # Capsule display option
                cylinder_as_capsule = self.server.gui.add_checkbox(
                    "Display as Capsule", initial_value=False
                )
                self._cylinder_radius_slider = cylinder_radius
                self._cylinder_height_slider = cylinder_height
                self._cylinder_as_capsule_checkbox = cylinder_as_capsule
```

改为：

```python
                # Capsule display option
                cylinder_as_capsule = self.server.gui.add_checkbox(
                    "Display as Capsule", initial_value=False
                )
                self.server.gui.add_markdown(
                    "⚠️ Capsule 仅用于显示，导出 URDF 时按 cylinder 处理"
                )
                self._cylinder_radius_slider = cylinder_radius
                self._cylinder_height_slider = cylinder_height
                self._cylinder_as_capsule_checkbox = cylinder_as_capsule
```

- [ ] **Step 2: 跑 ruff**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: 手动 GUI 冒烟**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf`
手动在浏览器 `http://localhost:8080` 打开，展开 `🔶 Geometry Editor` → `🥫 Cylinder Properties` 文件夹，确认 "Display as Capsule" checkbox 下方显示警告文案。
Expected: 看到 `⚠️ Capsule 仅用于显示，导出 URDF 时按 cylinder 处理`
然后 Ctrl+C 退出。

- [ ] **Step 4: Commit**

```bash
git add bubblify/gui.py
git commit -m "feat(gui): warn that display_as_capsule does not affect URDF export"
```

---

## Task 4: 抽 YAML I/O 数据层到 `core.py`（保持外部行为不变）

**Files:**
- Modify: `bubblify/core.py`（新增 `GeometrySpec` + `load_geometry_specs_from_yaml` + `dump_geometries_to_yaml`）
- Modify: `bubblify/gui.py:589-678, 1692-1766`（薄包装）

**Strategy:** 数据层**只认新格式**（老格式由 `gui.py` 里的 fallback 负责）。`dump_geometries_to_yaml` 此 Task **仍写** `collision_spheres` 双写以保持行为，Task 7 再清理。

### Sub-task 4a: 在 `core.py` 添加 `GeometrySpec` dataclass + `to_store_kwargs` 方法

- [ ] **Step 1: 在 `core.py` 顶部 import 区追加 Any / Dict（已有 Dict，只需 `Any`）**

Edit `bubblify/core.py:10`，原行：

```python
from typing import Dict, List, Optional, Tuple, Literal
```

改为：

```python
from typing import Any, Dict, List, Optional, Tuple, Literal
```

- [ ] **Step 2: 在 `core.py` 加 `YAML_SCHEMA_VERSION` 和 `GeometrySpec` dataclass**

位置：`core.py` 第 22-23 行（`GeometryType = Literal[...]` 之后，`@dataclasses.dataclass class Geometry` 之前）。

插入：

```python
YAML_SCHEMA_VERSION = 1


@dataclasses.dataclass
class GeometrySpec:
    """YAML 解析后的一条几何配置，尚未分配 id / 挂接 viser node。

    用于 load 路径：YAML -> GeometrySpec 列表 -> 调用方通过
    store.add(**spec.to_store_kwargs()) 转成 Geometry 并建立可视化。

    注：Geometry.display_as_capsule 不序列化到 YAML（仅运行时显示状态），
    因此 GeometrySpec 不包含该字段。
    """

    link: str
    xyz: Tuple[float, float, float]
    geometry_type: GeometryType
    rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    radius: Optional[float] = None
    size: Optional[Tuple[float, float, float]] = None
    cylinder_radius: Optional[float] = None
    cylinder_height: Optional[float] = None

    def to_store_kwargs(self) -> Dict[str, Any]:
        """转成 GeometryStore.add() 的 kwargs（略去 None 值）。"""
        kwargs: Dict[str, Any] = {
            "xyz": self.xyz,
            "geometry_type": self.geometry_type,
            "rpy": self.rpy,
        }
        if self.radius is not None:
            kwargs["radius"] = self.radius
        if self.size is not None:
            kwargs["size"] = self.size
        if self.cylinder_radius is not None:
            kwargs["cylinder_radius"] = self.cylinder_radius
        if self.cylinder_height is not None:
            kwargs["cylinder_height"] = self.cylinder_height
        return kwargs
```

- [ ] **Step 3: 冒烟 import**

Run: `python -c "from bubblify.core import GeometrySpec, YAML_SCHEMA_VERSION; s = GeometrySpec(link='l', xyz=(0,0,0), geometry_type='sphere', radius=0.1); print(s.to_store_kwargs())"`
Expected: `{'xyz': (0, 0, 0), 'geometry_type': 'sphere', 'rpy': (0.0, 0.0, 0.0), 'radius': 0.1}`

### Sub-task 4b: 实现 `load_geometry_specs_from_yaml`

- [ ] **Step 4: 在 `core.py` 末尾追加 `load_geometry_specs_from_yaml`**

在 `inject_geometries_into_urdf_xml` 函数末尾（文件最后）之后追加：

```python
def load_geometry_specs_from_yaml(path: Path) -> List[GeometrySpec]:
    """读 YAML，返回 GeometrySpec 列表。

    只认新格式（顶层有 collision_geometries 键）。

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 顶层缺 collision_geometries 键 / 条目缺必填字段 / 未知 type
    """
    import yaml

    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    if "collision_geometries" not in data:
        raise ValueError(
            f"YAML missing required top-level key 'collision_geometries': {path}"
        )

    specs: List[GeometrySpec] = []
    for link_name, entries in (data["collision_geometries"] or {}).items():
        for entry in entries or []:
            specs.append(_parse_geometry_entry(link_name, entry))
    return specs


def _parse_geometry_entry(link: str, entry: Dict[str, Any]) -> GeometrySpec:
    """解析 YAML 单条 geometry 条目为 GeometrySpec。"""
    if "center" not in entry:
        raise ValueError(f"link={link}: entry missing 'center'")
    if "type" not in entry:
        raise ValueError(f"link={link}: entry missing 'type'")

    geom_type = entry["type"]
    if geom_type not in ("sphere", "box", "cylinder"):
        raise ValueError(f"link={link}: unknown geometry type '{geom_type}'")

    xyz = tuple(entry["center"])
    rpy = tuple(entry.get("rpy", [0.0, 0.0, 0.0]))

    if geom_type == "sphere":
        if "radius" not in entry:
            raise ValueError(f"link={link}: sphere entry missing 'radius'")
        return GeometrySpec(
            link=link, xyz=xyz, geometry_type="sphere", rpy=rpy,
            radius=float(entry["radius"]),
        )
    if geom_type == "box":
        if "size" not in entry:
            raise ValueError(f"link={link}: box entry missing 'size'")
        return GeometrySpec(
            link=link, xyz=xyz, geometry_type="box", rpy=rpy,
            size=tuple(entry["size"]),
        )
    # cylinder
    if "radius" not in entry or "height" not in entry:
        raise ValueError(f"link={link}: cylinder entry missing 'radius' or 'height'")
    return GeometrySpec(
        link=link, xyz=xyz, geometry_type="cylinder", rpy=rpy,
        cylinder_radius=float(entry["radius"]),
        cylinder_height=float(entry["height"]),
    )
```

- [ ] **Step 5: 冒烟 import**

Run: `python -c "from bubblify.core import load_geometry_specs_from_yaml; print('ok')"`
Expected: `ok`

### Sub-task 4c: 实现 `dump_geometries_to_yaml`（此步保留 `collision_spheres` 双写）

- [ ] **Step 6: 在 `core.py` 末尾追加 `dump_geometries_to_yaml`**

追加：

```python
def dump_geometries_to_yaml(
    store: "GeometryStore",
    path: Path,
    *,
    include_metadata: bool = True,
) -> None:
    """序列化 store 到 YAML。

    本版本同时写 collision_geometries 和 collision_spheres 两个键，
    保留行为用于渐进清理；见 spec 的 Step 7 会移除 collision_spheres。

    metadata（可选）: total_geometries / total_spheres / links /
    export_timestamp / schema_version
    """
    import time

    import yaml

    collision_geometries: Dict[str, List[Dict[str, Any]]] = {}
    for geometry in store.by_id.values():
        collision_geometries.setdefault(geometry.link, []).append(
            _geometry_to_yaml_entry(geometry)
        )

    data: Dict[str, Any] = {
        "collision_geometries": collision_geometries,
        # Backward-compatible mirror; removed in cleanup Step 7.
        "collision_spheres": {
            link: [g for g in geometries if g["type"] == "sphere"]
            for link, geometries in collision_geometries.items()
        },
    }

    if include_metadata:
        total_spheres = sum(
            1 for g in store.by_id.values() if g.geometry_type == "sphere"
        )
        data["metadata"] = {
            "total_geometries": int(len(store.by_id)),
            "total_spheres": int(total_spheres),
            "links": list(collision_geometries.keys()),
            "export_timestamp": float(time.time()),
            "schema_version": YAML_SCHEMA_VERSION,
        }

    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _geometry_to_yaml_entry(geometry: Geometry) -> Dict[str, Any]:
    """把单个 Geometry 转成 YAML 条目 dict。"""
    center = geometry.local_xyz
    if hasattr(center, "tolist"):
        center = center.tolist()
    else:
        center = [float(x) for x in center]

    entry: Dict[str, Any] = {
        "center": center,
        "type": geometry.geometry_type,
    }
    if geometry.geometry_type != "sphere":
        entry["rpy"] = [float(r) for r in geometry.local_rpy]

    if geometry.geometry_type == "sphere":
        entry["radius"] = float(geometry.radius)
    elif geometry.geometry_type == "box":
        entry["size"] = [float(s) for s in geometry.size]
    elif geometry.geometry_type == "cylinder":
        entry["radius"] = float(geometry.cylinder_radius)
        entry["height"] = float(geometry.cylinder_height)
    return entry
```

- [ ] **Step 7: 冒烟 round-trip**

Run:
```bash
python -c "
from pathlib import Path
from bubblify.core import GeometryStore, dump_geometries_to_yaml, load_geometry_specs_from_yaml
store = GeometryStore()
store.add('link1', xyz=(0.1, 0, 0), geometry_type='sphere', radius=0.05)
store.add('link1', xyz=(0.2, 0, 0), geometry_type='box', size=(0.1, 0.1, 0.1), rpy=(0.1, 0.2, 0.3))
dump_geometries_to_yaml(store, Path('/tmp/_test.yml'))
specs = load_geometry_specs_from_yaml(Path('/tmp/_test.yml'))
print(len(specs), specs[0].geometry_type, specs[1].geometry_type)
"
```
Expected: `2 sphere box`

### Sub-task 4d: 改 `gui.py` YAML 导出 handler 调 `dump_geometries_to_yaml`

- [ ] **Step 8: 替换 `_setup_export_controls` 里 YAML 导出 handler 主体**

Edit `bubblify/gui.py:589-678`（`@export_yml_btn.on_click` 开始到 `except Exception as e:` 块结束）。

原代码片段（注意行号随上游可能有 ±1 行漂移）：

```python
            @export_yml_btn.on_click
            def _(_):
                """Export geometry configuration to YAML."""
                try:
                    import yaml

                    # ... 原始 ~90 行构造 data 的逻辑 ...

                    output_path = output_dir / f"{export_name_input.value}.yml"
                    output_path.write_text(
                        yaml.dump(data, default_flow_style=False, sort_keys=False)
                    )
                    export_status.content = (
                        f"✅ Exported {len(self.geometry_store.by_id)} geometries"
                    )
                    export_details.content = f"Saved to: {output_path.name}"
                    print(
                        f"Exported geometry configuration to {output_path.absolute()}"
                    )

                except ImportError:
                    error_msg = "PyYAML not installed. Run: pip install PyYAML"
                    export_status.content = "❌ Missing dependency"
                    export_details.content = error_msg
                    print(f"Export failed: {error_msg}")
                except Exception as e:
                    export_status.content = f"❌ Export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"Export failed: {e}")
```

替换为（**整段**替换从 `@export_yml_btn.on_click` 开始到第一个 `except Exception as e:` 的 `print(f"Export failed: {e}")` 结束）：

```python
            @export_yml_btn.on_click
            def _(_):
                """Export geometry configuration to YAML."""
                try:
                    # Determine output directory (same as URDF or cwd)
                    if self.urdf_path and self.urdf_path.parent:
                        output_dir = self.urdf_path.parent
                    else:
                        output_dir = Path.cwd()
                    output_path = output_dir / f"{export_name_input.value}.yml"

                    from .core import dump_geometries_to_yaml
                    dump_geometries_to_yaml(self.geometry_store, output_path)

                    export_status.content = (
                        f"✅ Exported {len(self.geometry_store.by_id)} geometries"
                    )
                    export_details.content = f"Saved to: {output_path.name}"
                    print(
                        f"Exported geometry configuration to {output_path.absolute()}"
                    )
                except Exception as e:
                    export_status.content = f"❌ Export failed: {type(e).__name__}"
                    export_details.content = str(e)
                    print(f"Export failed: {e}")
```

注：去掉了 `import yaml` 和 `ImportError` 分支（改由 `core.dump_geometries_to_yaml` 内部负责；PyYAML 作为 `yourdfpy`/`viser` 间接依赖实际必在环境里）。

- [ ] **Step 9: 验证 GUI YAML 导出（手动）**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf`
在浏览器 UI 里：
1. 点 `🤖 Robot Controls` → 选一个 link
2. 点 `🔶 Geometry Editor` → 加一个 sphere
3. 点 `💾 Export` → `Export Geometries (YAML)`
4. 确认底部 status 显示 `✅ Exported 1 geometries`
5. 确认 `assets/xarm6/geometries.yml`（或 `<urdf_stem>_geometries.yml`）已写入，且包含 `collision_geometries:` 和 `collision_spheres:` 两个顶层键
Ctrl+C 退出。

Run: `grep -E "^(collision_geometries|collision_spheres|metadata):" assets/xarm6/*_geometries.yml`
Expected: 三个键都在

### Sub-task 4e: 改 `gui.py` YAML 加载器为"先试新 API，ValueError 时 fallback 到旧格式"

- [ ] **Step 10: 改写 `_load_geometry_config_yaml`**

Edit `bubblify/gui.py:1692-1766`，原函数：

```python
    def _load_geometry_config_yaml(self, yaml_path: Path):
        """Load geometry configuration from YAML file at startup."""
        try:
            import yaml

            if not yaml_path.exists():
                print(f"⚠️  Geometry configuration YAML file not found: {yaml_path}")
                return

            print(f"📥 Loading geometry configuration from: {yaml_path}")
            data = yaml.safe_load(yaml_path.read_text())
            collision_spheres = data.get("collision_spheres", {})

            # Import spheres and geometries
            total_loaded = 0

            # Try to load new format with collision_geometries first
            collision_data = data.get("collision_geometries", {})
            if collision_data:
                # ... 新格式解析 ~35 行 ...
            else:
                # Fallback to old format with collision_spheres
                for link_name, spheres_data in collision_spheres.items():
                    for sphere_data in spheres_data:
                        # Old format - only spheres, no rotation
                        sphere = self.geometry_store.add(
                            link_name,
                            xyz=tuple(sphere_data["center"]),
                            radius=sphere_data["radius"],
                        )
                        self._create_geometry_visualization(sphere)
                        total_loaded += 1

            print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name}")

        except ImportError:
            print("⚠️  PyYAML not installed. Cannot load geometry configuration YAML.")
            print("   Install with: pip install PyYAML")
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
```

整体替换为：

```python
    def _load_geometry_config_yaml(self, yaml_path: Path):
        """Load geometry configuration from YAML file at startup.

        优先走 core 的 load_geometry_specs_from_yaml（新格式）；若顶层缺
        collision_geometries 键，ValueError 时 fallback 到旧 collision_spheres
        格式解析。该 fallback 分支会在 cleanup Step 7 被删除。
        """
        from .core import load_geometry_specs_from_yaml

        if not yaml_path.exists():
            print(f"⚠️  Geometry configuration YAML file not found: {yaml_path}")
            return

        print(f"📥 Loading geometry configuration from: {yaml_path}")
        total_loaded = 0

        try:
            specs = load_geometry_specs_from_yaml(yaml_path)
        except ValueError:
            # Fallback: old-format file with only collision_spheres key.
            # Removed in cleanup Step 7.
            import yaml

            data = yaml.safe_load(yaml_path.read_text()) or {}
            for link_name, spheres_data in (data.get("collision_spheres") or {}).items():
                for sphere_data in spheres_data:
                    geometry = self.geometry_store.add(
                        link_name,
                        xyz=tuple(sphere_data["center"]),
                        radius=sphere_data["radius"],
                    )
                    self._create_geometry_visualization(geometry)
                    total_loaded += 1
            print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name} (legacy format)")
            return
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
            return

        for spec in specs:
            geometry = self.geometry_store.add(spec.link, **spec.to_store_kwargs())
            self._create_geometry_visualization(geometry)
            total_loaded += 1

        print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name}")
```

- [ ] **Step 11: 跑 ruff**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 12: 手动验证（旧格式 yml 走 fallback）**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config assets/xarm6/xarm6_rs_spherized.yml`

注：`xarm6_rs_spherized.yml` 是旧格式（只有 `collision_spheres` 键，无 `collision_geometries`），本步应走 ValueError fallback 分支，终端应打印 `(legacy format)` 标记。

Expected 终端输出含：`✅ Loaded <N> geometries from xarm6_rs_spherized.yml (legacy format)`
浏览器里能看到加载的 spheres 在 xarm6 上。Ctrl+C 退出。

- [ ] **Step 13: 手动验证（新格式 yml 走 core API）**

使用 Step 9 导出的 `<urdf_stem>_geometries.yml`（新格式）：

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config assets/xarm6/<urdf_stem>_geometries.yml`

Expected 终端输出含：`✅ Loaded <N> geometries from <urdf_stem>_geometries.yml`（无 `legacy format` 后缀）。Ctrl+C 退出。

- [ ] **Step 14: Commit**

```bash
git add bubblify/core.py bubblify/gui.py
git commit -m "refactor(core): extract YAML load/dump data layer into core.py

- New: GeometrySpec dataclass, YAML_SCHEMA_VERSION,
  load_geometry_specs_from_yaml, dump_geometries_to_yaml
- gui.py now delegates to core; the legacy collision_spheres
  fallback path remains in gui._load_geometry_config_yaml and
  dump still writes collision_spheres — both to be removed in
  the cleanup commit."
```

---

## Task 5: 清空 `tests/` 并建测试骨架 + 加 `pytest-cov` 依赖

**Files:**
- Delete: `tests/test_base_link_fix.py`, `tests/test_bubblify.py`, `tests/test_custom_urdf_export.py`, `tests/test_export_fixes.py`, `tests/test_final_gui_improvements.py`, `tests/test_gui_export.py`, `tests/test_gui_final.py`, `tests/test_gui_improvements.py`, `tests/test_latest_improvements.py`, `tests/test_mesh_visibility_fix.py`, `tests/test_multiple_robots.py`, `tests/test_new_visibility_system.py`, `tests/test_opacity_system.py`, `tests/test_real_robot_urdf_export.py`, `tests/test_urdf_export_improvements.py`
- Create: `tests/conftest.py`
- Create: `tests/test_geometry.py`
- Create: `tests/test_rotation.py`
- Create: `tests/test_geometry_store.py`
- Create: `tests/test_urdf_injection.py`
- Create: `tests/test_yaml_io.py`
- Modify: `pyproject.toml`（dev group 加 `pytest-cov`；加 `[tool.coverage.*]` 配置）

- [ ] **Step 1: 删所有现有 `tests/*.py`**

Run:
```bash
git rm tests/test_base_link_fix.py tests/test_bubblify.py tests/test_custom_urdf_export.py \
       tests/test_export_fixes.py tests/test_final_gui_improvements.py tests/test_gui_export.py \
       tests/test_gui_final.py tests/test_gui_improvements.py tests/test_latest_improvements.py \
       tests/test_mesh_visibility_fix.py tests/test_multiple_robots.py tests/test_new_visibility_system.py \
       tests/test_opacity_system.py tests/test_real_robot_urdf_export.py tests/test_urdf_export_improvements.py
```

Run: `ls tests/`
Expected: 空目录或（若 git rm 不删目录）无输出

- [ ] **Step 2: 建 `tests/conftest.py`**

Create `tests/conftest.py`：

```python
"""Shared pytest fixtures for bubblify core tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bubblify.core import GeometryStore


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_urdf_path() -> Path:
    """Path to a real xarm6 URDF bundled in the repo."""
    path = REPO_ROOT / "assets" / "xarm6" / "xarm6_rs.urdf"
    assert path.exists(), f"fixture URDF missing: {path}"
    return path


@pytest.fixture
def mixed_store() -> GeometryStore:
    """GeometryStore pre-populated with 3 links, 3 geometry types, 6 entries."""
    store = GeometryStore()
    # link2: two spheres
    store.add("link2", xyz=(0.0, 0.0, 0.1), geometry_type="sphere", radius=0.06)
    store.add("link2", xyz=(0.0, -0.07, 0.1), geometry_type="sphere", radius=0.06)
    # link3: one box (with non-zero rpy), one cylinder
    store.add(
        "link3", xyz=(0.1, 0.0, 0.0), geometry_type="box",
        size=(0.1, 0.1, 0.1), rpy=(0.2, 0.3, 0.4),
    )
    store.add(
        "link3", xyz=(0.0, 0.0, 0.2), geometry_type="cylinder",
        cylinder_radius=0.03, cylinder_height=0.15, rpy=(0.0, 0.0, 0.5),
    )
    # link_base: one sphere, one box
    store.add("link_base", xyz=(0.0, 0.0, 0.0), geometry_type="sphere", radius=0.05)
    store.add(
        "link_base", xyz=(0.1, 0.1, 0.0), geometry_type="box",
        size=(0.05, 0.05, 0.05),
    )
    return store
```

- [ ] **Step 3: 建 5 个空测试骨架**

Create `tests/test_geometry.py`：

```python
"""Tests for Geometry dataclass and its methods."""
```

Create `tests/test_rotation.py`：

```python
"""Tests for rpy_to_quaternion / quaternion_to_rpy conversions."""
```

Create `tests/test_geometry_store.py`：

```python
"""Tests for GeometryStore CRUD + index consistency."""
```

Create `tests/test_urdf_injection.py`：

```python
"""Tests for inject_geometries_into_urdf_xml."""
```

Create `tests/test_yaml_io.py`：

```python
"""Tests for load_geometry_specs_from_yaml / dump_geometries_to_yaml round-trip."""
```

- [ ] **Step 4: 加 `pytest-cov` 到 dev group**

Edit `pyproject.toml`：找到 `[dependency-groups]` → `dev = [...]`，加入 `"pytest-cov>=4.0.0"`。

最终 `dev` 块类似：

```toml
[dependency-groups]
dev = [
    "ruff>=0.12.12",
    "setuptools>=75.3.2",
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]
```

- [ ] **Step 5: 加 coverage 配置**

在 `pyproject.toml` 末尾追加：

```toml
[tool.coverage.run]
source = ["bubblify.core"]

[tool.coverage.report]
exclude_also = [
    "class EnhancedViserUrdf",
    "def _viser_name_from_frame",
]
```

`_viser_name_from_frame` 是 `EnhancedViserUrdf` 专用 helper，同样不在测试范围。

- [ ] **Step 6: 同步依赖 lock**

Run: `uv sync`
Expected: pytest-cov 被安装进 `.venv`

- [ ] **Step 7: 跑 pytest 空骨架**

Run: `uv run pytest -v`
Expected: 退出码 0，报告 `no tests ran`（骨架文件只有 docstring）

- [ ] **Step 8: Commit**

```bash
git add tests/ pyproject.toml uv.lock
git commit -m "test: reset tests/ and add pytest-cov + coverage config

Removed 14 smoke-script files that constructed BubblifyApp with hardcoded
ports and printed feature summaries without assertions. Added empty test
skeletons and a conftest with sample_urdf_path / mixed_store fixtures;
next commit fills in the actual test cases."
```

---

## Task 6: 按测试矩阵填充单测

**Files:**
- Modify: `tests/test_geometry.py`
- Modify: `tests/test_rotation.py`
- Modify: `tests/test_geometry_store.py`
- Modify: `tests/test_urdf_injection.py`
- Modify: `tests/test_yaml_io.py`

**TDD 注：** 这些测试针对**已经实现**的 core API（Task 4 完成）+ 现存函数（`inject_geometries_into_urdf_xml` 等）。按"写测试 → 跑 → 确认 pass 或暴露 bug"执行；如发现真 bug（如 RPY 边界），按 spec 失败预案要求停下来讨论，不得"改测试凑过"。

### Sub-task 6a: `tests/test_geometry.py`

- [ ] **Step 1: 写 `tests/test_geometry.py` 全部用例**

```python
"""Tests for Geometry dataclass and its methods."""

from __future__ import annotations

import math

import pytest

from bubblify.core import Geometry


def test_geometry_defaults():
    g = Geometry(id=0, link="l", local_xyz=(0.0, 0.0, 0.0))
    assert g.geometry_type == "sphere"
    assert g.radius == 0.05
    assert g.size == (0.1, 0.1, 0.1)
    assert g.cylinder_radius == 0.05
    assert g.cylinder_height == 0.1
    assert g.display_as_capsule is False
    assert g.local_rpy == (0.0, 0.0, 0.0)
    assert g.local_wxyz == (1.0, 0.0, 0.0, 0.0)
    assert g.color == (255, 180, 60)
    assert g.node is None


def test_effective_radius_sphere():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0), geometry_type="sphere", radius=0.12)
    assert g.get_effective_radius() == pytest.approx(0.12)


def test_effective_radius_box_is_half_diagonal():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0), geometry_type="box", size=(0.2, 0.2, 0.2))
    expected = 0.5 * math.sqrt(0.2**2 * 3)
    assert g.get_effective_radius() == pytest.approx(expected)


def test_effective_radius_cylinder_uses_cylinder_radius():
    g = Geometry(
        id=0, link="l", local_xyz=(0, 0, 0),
        geometry_type="cylinder", cylinder_radius=0.08, cylinder_height=0.3,
    )
    assert g.get_effective_radius() == pytest.approx(0.08)


def test_update_quaternion_from_rpy_updates_wxyz():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0))
    g.update_quaternion_from_rpy((math.pi / 2, 0.0, 0.0))
    assert g.local_rpy == (math.pi / 2, 0.0, 0.0)
    w, x, y, z = g.local_wxyz
    # quaternion for 90° roll: w = cos(pi/4), x = sin(pi/4)
    assert w == pytest.approx(math.cos(math.pi / 4), abs=1e-12)
    assert x == pytest.approx(math.sin(math.pi / 4), abs=1e-12)
    assert y == pytest.approx(0.0, abs=1e-12)
    assert z == pytest.approx(0.0, abs=1e-12)


def test_update_rpy_from_quaternion_updates_rpy():
    g = Geometry(id=0, link="l", local_xyz=(0, 0, 0))
    # quaternion for 90° yaw
    c = math.cos(math.pi / 4)
    s = math.sin(math.pi / 4)
    g.update_rpy_from_quaternion((c, 0.0, 0.0, s))
    roll, pitch, yaw = g.local_rpy
    assert roll == pytest.approx(0.0, abs=1e-12)
    assert pitch == pytest.approx(0.0, abs=1e-12)
    assert yaw == pytest.approx(math.pi / 2, abs=1e-12)
```

- [ ] **Step 2: 跑该文件**

Run: `uv run pytest tests/test_geometry.py -v`
Expected: 6 passed

### Sub-task 6b: `tests/test_rotation.py`

- [ ] **Step 3: 写 `tests/test_rotation.py`**

```python
"""Tests for rpy_to_quaternion / quaternion_to_rpy conversions."""

from __future__ import annotations

import math

import pytest

from bubblify.core import rpy_to_quaternion, quaternion_to_rpy


def _roundtrip_rpy(rpy):
    return quaternion_to_rpy(rpy_to_quaternion(rpy))


def test_zero_rotation_roundtrip():
    w, x, y, z = rpy_to_quaternion((0.0, 0.0, 0.0))
    assert (w, x, y, z) == pytest.approx((1.0, 0.0, 0.0, 0.0), abs=1e-12)
    assert _roundtrip_rpy((0.0, 0.0, 0.0)) == pytest.approx(
        (0.0, 0.0, 0.0), abs=1e-12
    )


@pytest.mark.parametrize("angle", [-math.pi / 2, -math.pi / 4, math.pi / 4, math.pi / 2 - 1e-3])
def test_single_axis_roundtrip_roll(angle):
    assert _roundtrip_rpy((angle, 0.0, 0.0))[0] == pytest.approx(angle, abs=1e-9)


@pytest.mark.parametrize("angle", [-math.pi / 2 + 1e-3, -math.pi / 4, math.pi / 4, math.pi / 2 - 1e-3])
def test_single_axis_roundtrip_pitch(angle):
    assert _roundtrip_rpy((0.0, angle, 0.0))[1] == pytest.approx(angle, abs=1e-9)


@pytest.mark.parametrize("angle", [-math.pi / 2, -math.pi / 4, math.pi / 4, math.pi / 2])
def test_single_axis_roundtrip_yaw(angle):
    assert _roundtrip_rpy((0.0, 0.0, angle))[2] == pytest.approx(angle, abs=1e-9)


def test_compound_roundtrip():
    rpy = (0.3, -0.5, 1.1)
    out = _roundtrip_rpy(rpy)
    for a, b in zip(rpy, out):
        assert a == pytest.approx(b, abs=1e-9)


def test_quaternion_unit_norm():
    for rpy in [(0.1, 0.2, 0.3), (-1.0, 0.5, 2.0), (math.pi / 3, -math.pi / 4, 0.0)]:
        w, x, y, z = rpy_to_quaternion(rpy)
        norm = math.sqrt(w * w + x * x + y * y + z * z)
        assert norm == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_gimbal_lock_pitch(sign):
    """pitch = ±π/2 触发 gimbal lock；pitch 值应被准确保留，
    roll/yaw 的具体分配不保证，但转回矩阵应一致（此处只断言 pitch）。"""
    pitch = sign * math.pi / 2
    out_pitch = _roundtrip_rpy((0.1, pitch, 0.2))[1]
    assert out_pitch == pytest.approx(pitch, abs=1e-9)
```

- [ ] **Step 4: 跑**

Run: `uv run pytest tests/test_rotation.py -v`
Expected: 全部 passed（若有 fail 按 spec 失败预案停下来讨论）

### Sub-task 6c: `tests/test_geometry_store.py`

- [ ] **Step 5: 写 `tests/test_geometry_store.py`**

```python
"""Tests for GeometryStore CRUD + index consistency."""

from __future__ import annotations

import pytest

from bubblify.core import GeometryStore


def test_add_returns_geometry_with_matching_by_id():
    store = GeometryStore()
    g = store.add("link1", xyz=(0.1, 0, 0), geometry_type="sphere", radius=0.05)
    assert store.by_id[g.id] is g
    assert g.link == "link1"
    assert g.local_xyz == (0.1, 0, 0)
    assert g.radius == 0.05


def test_ids_are_monotonically_increasing():
    store = GeometryStore()
    ids = [store.add("l", xyz=(0, 0, 0), radius=0.05).id for _ in range(5)]
    assert ids == sorted(ids)
    assert len(set(ids)) == 5


def test_ids_by_link_tracks_membership():
    store = GeometryStore()
    a = store.add("l1", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l1", xyz=(0.1, 0, 0), radius=0.05)
    c = store.add("l2", xyz=(0, 0, 0), radius=0.05)
    assert store.ids_by_link["l1"] == [a.id, b.id]
    assert store.ids_by_link["l2"] == [c.id]


def test_remove_clears_indexes():
    store = GeometryStore()
    a = store.add("l1", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l1", xyz=(0.1, 0, 0), radius=0.05)
    removed = store.remove(a.id)
    assert removed is a
    assert a.id not in store.by_id
    assert store.ids_by_link["l1"] == [b.id]


def test_remove_last_in_link_drops_link_key():
    store = GeometryStore()
    g = store.add("lonely", xyz=(0, 0, 0), radius=0.05)
    store.remove(g.id)
    assert "lonely" not in store.ids_by_link


def test_remove_unknown_id_returns_none():
    store = GeometryStore()
    assert store.remove(9999) is None


def test_clear_empties_everything():
    store = GeometryStore()
    store.add("l1", xyz=(0, 0, 0), radius=0.05)
    store.add("l2", xyz=(0, 0, 0), radius=0.05)
    store.clear()
    assert store.by_id == {}
    assert store.ids_by_link == {}


def test_get_geometries_for_link_preserves_insertion_order():
    store = GeometryStore()
    a = store.add("l", xyz=(0, 0, 0), radius=0.05)
    b = store.add("l", xyz=(0.1, 0, 0), radius=0.06)
    c = store.add("l", xyz=(0.2, 0, 0), radius=0.07)
    result = store.get_geometries_for_link("l")
    assert [g.id for g in result] == [a.id, b.id, c.id]


def test_get_geometries_for_unknown_link_returns_empty_list():
    store = GeometryStore()
    assert store.get_geometries_for_link("nope") == []
```

- [ ] **Step 6: 跑**

Run: `uv run pytest tests/test_geometry_store.py -v`
Expected: 9 passed

### Sub-task 6d: `tests/test_urdf_injection.py`

- [ ] **Step 7: 写 `tests/test_urdf_injection.py`**

```python
"""Tests for inject_geometries_into_urdf_xml."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
import yourdfpy

from bubblify.core import GeometryStore, inject_geometries_into_urdf_xml


@pytest.fixture
def loaded_urdf(sample_urdf_path):
    return yourdfpy.URDF.load(
        str(sample_urdf_path), build_scene_graph=False, load_meshes=False,
    )


def _inject(sample_urdf_path, urdf, store):
    return inject_geometries_into_urdf_xml(sample_urdf_path, urdf, store)


def test_output_is_parseable_urdf(sample_urdf_path, loaded_urdf, mixed_store, tmp_path):
    xml = _inject(sample_urdf_path, loaded_urdf, mixed_store)
    out = tmp_path / "out.urdf"
    out.write_text(xml)
    reloaded = yourdfpy.URDF.load(str(out), build_scene_graph=False, load_meshes=False)
    assert reloaded is not None


def test_all_existing_collisions_replaced(sample_urdf_path, loaded_urdf, mixed_store):
    xml = _inject(sample_urdf_path, loaded_urdf, mixed_store)
    root = ET.fromstring(xml)
    collision_count = sum(len(link.findall("collision")) for link in root.findall("link"))
    # mixed_store has 6 entries, but only those whose link exists in the URDF survive.
    # xarm6_rs.urdf has link2 and link3; link_base is absent.
    link_names = {link.get("name") for link in root.findall("link")}
    expected = sum(
        1 for g in mixed_store.by_id.values() if g.link in link_names
    )
    assert collision_count == expected


def test_sphere_rpy_is_zero_even_if_store_has_nonzero(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    # Pick a link that exists in xarm6_rs.urdf
    store.add(
        "link2", xyz=(0.0, 0.0, 0.05), geometry_type="sphere",
        radius=0.03, rpy=(0.5, 0.6, 0.7),
    )
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    root = ET.fromstring(xml)
    link2 = next(link for link in root.findall("link") if link.get("name") == "link2")
    origin = link2.find("collision/origin")
    assert origin is not None
    assert origin.get("rpy") == "0 0 0"


def test_box_and_cylinder_rpy_passthrough(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    store.add(
        "link2", xyz=(0, 0, 0), geometry_type="box",
        size=(0.1, 0.1, 0.1), rpy=(0.1, 0.2, 0.3),
    )
    store.add(
        "link3", xyz=(0, 0, 0), geometry_type="cylinder",
        cylinder_radius=0.05, cylinder_height=0.1, rpy=(0.4, 0.5, 0.6),
    )
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    root = ET.fromstring(xml)
    link2 = next(link for link in root.findall("link") if link.get("name") == "link2")
    link3 = next(link for link in root.findall("link") if link.get("name") == "link3")
    assert link2.find("collision/origin").get("rpy") == "0.1 0.2 0.3"
    assert link3.find("collision/origin").get("rpy") == "0.4 0.5 0.6"


def test_unknown_link_is_skipped_silently(sample_urdf_path, loaded_urdf):
    store = GeometryStore()
    store.add("totally_not_a_link", xyz=(0, 0, 0), radius=0.05)
    xml = _inject(sample_urdf_path, loaded_urdf, store)
    # Still parseable and no collision added
    root = ET.fromstring(xml)
    total_collisions = sum(len(link.findall("collision")) for link in root.findall("link"))
    assert total_collisions == 0
```

- [ ] **Step 8: 跑**

Run: `uv run pytest tests/test_urdf_injection.py -v`
Expected: 5 passed

### Sub-task 6e: `tests/test_yaml_io.py`

- [ ] **Step 9: 写 `tests/test_yaml_io.py`**

```python
"""Tests for load_geometry_specs_from_yaml / dump_geometries_to_yaml round-trip."""

from __future__ import annotations

import pytest
import yaml

from bubblify.core import (
    GeometryStore,
    GeometrySpec,
    dump_geometries_to_yaml,
    load_geometry_specs_from_yaml,
)


def _specs_by_link(specs):
    out = {}
    for s in specs:
        out.setdefault(s.link, []).append(s)
    return out


def test_roundtrip_preserves_all_fields(mixed_store, tmp_path):
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    specs = load_geometry_specs_from_yaml(path)

    assert len(specs) == len(mixed_store.by_id)
    by_link = _specs_by_link(specs)
    for g in mixed_store.by_id.values():
        matches = [
            s for s in by_link[g.link]
            if s.geometry_type == g.geometry_type
            and tuple(s.xyz) == tuple(g.local_xyz)
        ]
        assert matches, f"no matching spec for geometry {g}"
        s = matches[0]
        if g.geometry_type == "sphere":
            assert s.radius == pytest.approx(g.radius)
            # sphere rpy is not written to YAML, spec defaults to (0,0,0)
            assert s.rpy == (0.0, 0.0, 0.0)
        elif g.geometry_type == "box":
            assert tuple(s.size) == tuple(g.size)
            assert tuple(s.rpy) == pytest.approx(tuple(g.local_rpy))
        elif g.geometry_type == "cylinder":
            assert s.cylinder_radius == pytest.approx(g.cylinder_radius)
            assert s.cylinder_height == pytest.approx(g.cylinder_height)
            assert tuple(s.rpy) == pytest.approx(tuple(g.local_rpy))


def test_empty_store_dumps_valid_yaml(tmp_path):
    path = tmp_path / "empty.yml"
    dump_geometries_to_yaml(GeometryStore(), path)
    specs = load_geometry_specs_from_yaml(path)
    assert specs == []


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_geometry_specs_from_yaml(tmp_path / "nope.yml")


def test_load_missing_top_level_key_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(yaml.safe_dump({"collision_spheres": {}}))
    with pytest.raises(ValueError, match="collision_geometries"):
        load_geometry_specs_from_yaml(path)


def test_load_unknown_type_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        yaml.safe_dump({
            "collision_geometries": {
                "l1": [{"center": [0, 0, 0], "type": "pyramid", "radius": 0.05}]
            }
        })
    )
    with pytest.raises(ValueError, match="pyramid"):
        load_geometry_specs_from_yaml(path)


def test_load_sphere_missing_radius_raises(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text(
        yaml.safe_dump({
            "collision_geometries": {"l1": [{"center": [0, 0, 0], "type": "sphere"}]}
        })
    )
    with pytest.raises(ValueError, match="radius"):
        load_geometry_specs_from_yaml(path)


def test_geometryspec_to_store_kwargs_omits_none():
    spec = GeometrySpec(link="l", xyz=(0, 0, 0), geometry_type="sphere", radius=0.1)
    kw = spec.to_store_kwargs()
    assert "radius" in kw
    assert "size" not in kw
    assert "cylinder_radius" not in kw
    assert "cylinder_height" not in kw


def test_dumped_yaml_still_has_collision_spheres_key(mixed_store, tmp_path):
    """During Task 4..6, dump writes both collision_geometries and
    collision_spheres for backward compat; Task 7 removes the latter."""
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    raw = yaml.safe_load(path.read_text())
    assert "collision_geometries" in raw
    assert "collision_spheres" in raw  # NOTE: this assertion flips in Task 7
```

- [ ] **Step 10: 跑**

Run: `uv run pytest tests/test_yaml_io.py -v`
Expected: 8 passed

### Sub-task 6f: 跑全量测试 + 覆盖率检查

- [ ] **Step 11: 全量跑**

Run: `uv run pytest -v`
Expected: 全部 passed（约 30+ tests），总时间 < 2s

- [ ] **Step 12: 跑覆盖率**

Run: `uv run pytest --cov`
Expected: `bubblify/core.py` 覆盖率 ≥ 90%（排除 `EnhancedViserUrdf` 后）

如果 < 90%，看 missing lines 报告：
- 若是 `inject_geometries_into_urdf_xml` 的 `indent_xml` helper 内部某分支没覆盖，追加一个测试
- 若是 `_parse_geometry_entry` 中 box 缺 size 的分支没覆盖，追加一个 box-missing-size 测试

- [ ] **Step 13: Commit**

```bash
git add tests/
git commit -m "test: add core.py coverage (Geometry, rotation, store, XML inject, YAML I/O)"
```

---

## Task 7: 删 `collision_spheres` 双写 + 删 `gui.py` 旧格式 fallback

**Files:**
- Modify: `bubblify/core.py`（`dump_geometries_to_yaml`）
- Modify: `bubblify/gui.py`（`_load_geometry_config_yaml` fallback）
- Modify: `tests/test_yaml_io.py`（反转 `test_dumped_yaml_still_has_collision_spheres_key`）

- [ ] **Step 1: 从 `dump_geometries_to_yaml` 去掉 collision_spheres 块**

Edit `bubblify/core.py` 中 `dump_geometries_to_yaml`，原：

```python
    data: Dict[str, Any] = {
        "collision_geometries": collision_geometries,
        # Backward-compatible mirror; removed in cleanup Step 7.
        "collision_spheres": {
            link: [g for g in geometries if g["type"] == "sphere"]
            for link, geometries in collision_geometries.items()
        },
    }
```

改为：

```python
    data: Dict[str, Any] = {
        "collision_geometries": collision_geometries,
    }
```

同时删 metadata 里的 `total_spheres` 字段（它只在双写时期有存在意义）：

```python
        data["metadata"] = {
            "total_geometries": int(len(store.by_id)),
            "total_spheres": int(total_spheres),
            "links": list(collision_geometries.keys()),
            "export_timestamp": float(time.time()),
            "schema_version": YAML_SCHEMA_VERSION,
        }
```

改为：

```python
        data["metadata"] = {
            "total_geometries": int(len(store.by_id)),
            "links": list(collision_geometries.keys()),
            "export_timestamp": float(time.time()),
            "schema_version": YAML_SCHEMA_VERSION,
        }
```

删上方 `total_spheres` 的计算：

```python
        total_spheres = sum(
            1 for g in store.by_id.values() if g.geometry_type == "sphere"
        )
```

整段删除。

- [ ] **Step 2: 删 `gui.py` 的旧格式 fallback 分支**

Edit `bubblify/gui.py` 中 `_load_geometry_config_yaml`。当前（Task 4 完成后）大致是：

```python
        try:
            specs = load_geometry_specs_from_yaml(yaml_path)
        except ValueError:
            # Fallback: old-format file with only collision_spheres key.
            # Removed in cleanup Step 7.
            import yaml

            data = yaml.safe_load(yaml_path.read_text()) or {}
            for link_name, spheres_data in (data.get("collision_spheres") or {}).items():
                for sphere_data in spheres_data:
                    geometry = self.geometry_store.add(
                        link_name,
                        xyz=tuple(sphere_data["center"]),
                        radius=sphere_data["radius"],
                    )
                    self._create_geometry_visualization(geometry)
                    total_loaded += 1
            print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name} (legacy format)")
            return
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
            return
```

替换为：

```python
        try:
            specs = load_geometry_specs_from_yaml(yaml_path)
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
            return
```

同时，把 docstring 里描述 fallback 的那段删除，最终 `_load_geometry_config_yaml` 形似：

```python
    def _load_geometry_config_yaml(self, yaml_path: Path):
        """Load geometry configuration from YAML file at startup."""
        from .core import load_geometry_specs_from_yaml

        if not yaml_path.exists():
            print(f"⚠️  Geometry configuration YAML file not found: {yaml_path}")
            return

        print(f"📥 Loading geometry configuration from: {yaml_path}")

        try:
            specs = load_geometry_specs_from_yaml(yaml_path)
        except Exception as e:
            print(f"❌ Failed to load geometry configuration YAML: {e}")
            return

        total_loaded = 0
        for spec in specs:
            geometry = self.geometry_store.add(spec.link, **spec.to_store_kwargs())
            self._create_geometry_visualization(geometry)
            total_loaded += 1

        print(f"✅ Loaded {total_loaded} geometries from {yaml_path.name}")
```

- [ ] **Step 3: 反转 `tests/test_yaml_io.py::test_dumped_yaml_still_has_collision_spheres_key`**

Edit `tests/test_yaml_io.py`，把该测试：

```python
def test_dumped_yaml_still_has_collision_spheres_key(mixed_store, tmp_path):
    """During Task 4..6, dump writes both collision_geometries and
    collision_spheres for backward compat; Task 7 removes the latter."""
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    raw = yaml.safe_load(path.read_text())
    assert "collision_geometries" in raw
    assert "collision_spheres" in raw  # NOTE: this assertion flips in Task 7
```

改为：

```python
def test_dumped_yaml_has_no_legacy_collision_spheres_key(mixed_store, tmp_path):
    """Cleanup Step 7: collision_spheres double-write is gone."""
    path = tmp_path / "g.yml"
    dump_geometries_to_yaml(mixed_store, path)
    raw = yaml.safe_load(path.read_text())
    assert "collision_geometries" in raw
    assert "collision_spheres" not in raw
    # metadata no longer has total_spheres either
    assert "total_spheres" not in raw["metadata"]
```

- [ ] **Step 4: 跑 pytest**

Run: `uv run pytest -v`
Expected: 全 passed（包含反转后的测试）

- [ ] **Step 5: 跑 ruff**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: 手动验证新格式加载**

先导出一个新格式 yml：`uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf`，UI 加一个 sphere，导出得到 `assets/xarm6/xarm6_rs_geometries.yml`。Ctrl+C 退。

Run: `grep -c collision_spheres assets/xarm6/xarm6_rs_geometries.yml`
Expected: `0`（已无 collision_spheres 键）

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config assets/xarm6/xarm6_rs_geometries.yml`
Expected 终端：`✅ Loaded 1 geometries from xarm6_rs_geometries.yml`。Ctrl+C 退。

- [ ] **Step 7: 验证旧格式文件现在加载失败（预期行为）**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config assets/xarm6/xarm6_rs_spherized.yml`
Expected 终端：`❌ Failed to load geometry configuration YAML: ... collision_geometries ...`——旧格式文件被拒，符合 spec 的风险条款。Ctrl+C 退。

- [ ] **Step 8: Commit**

```bash
git add bubblify/core.py bubblify/gui.py tests/test_yaml_io.py
git commit -m "refactor: drop collision_spheres backward-compat YAML path

- dump_geometries_to_yaml no longer writes the collision_spheres mirror
  or metadata.total_spheres
- gui._load_geometry_config_yaml no longer falls back to old-format files;
  ValueError from core is now a user-facing error
- tests/test_yaml_io flips the assertion accordingly

Old-format .yml files (only collision_spheres key) are no longer loadable;
per spec risk section, assets/xarm6/*_spherized.yml are known affected and
acceptable. Re-export them through the GUI to upgrade."
```

---

## Task 8: 更新 `CLAUDE.md` 过时描述

**Files:**
- Modify: `CLAUDE.md`（注：文件被 `.gitignore`，commit 时需要 `-f` 或跳过 git；我们这里**不**把它加进 git，只本地更新）

- [ ] **Step 1: 找到过时句子**

Run: `grep -n "collision_spheres\|inject_geometries\|Sphere = Geometry\|new and legacy" CLAUDE.md`
Expected: 列出含这些关键词的行（若项目 CLAUDE.md 未描述这些细节，则跳过 Task 8 的编辑步骤）

- [ ] **Step 2: 改写相关段落**

预期会命中的段落（当前 CLAUDE.md 的 "Architecture" 节）：

> "Backward-compat aliases: `Sphere = Geometry` and `SphereStore = GeometryStore` are re-exported from `__init__.py`. On the YAML side, the exporter writes both a new `collision_geometries` section and a legacy `collision_spheres` section; the loader prefers the new one and falls back to the old format."

替换为：

> "YAML 只使用新格式（顶层 `collision_geometries` 键）；`load_geometry_specs_from_yaml` / `dump_geometries_to_yaml` 定义在 `core.py`，`gui.py` 的加载/导出 handler 只是薄包装。历史 `Sphere`/`SphereStore` Python 别名以及 `collision_spheres` YAML 键已在 2026-04 的清理中删除。"

另外如果 `当扩展 Geometry 新形状` 的 checklist 段落提到 "the YAML export branch in `_setup_export_controls`" 和 "the YAML loader in `_load_geometry_config_yaml`"，改为指向 `core.py` 的 `_geometry_to_yaml_entry` 和 `_parse_geometry_entry`。

- [ ] **Step 3: 本地 review**

Run: `cat CLAUDE.md | head -80`
Expected: 相关段落已更新、无遗留 `collision_spheres` 引用。

- [ ] **Step 4: 不 commit（CLAUDE.md 已 gitignore）**

跳过 `git add`。说明：`CLAUDE.md` 在 `.gitignore` 中，属于 per-user 本地文档，本次清理仅更新本地副本，不纳入版本控制。

---

## Task 9: 全局回归检查 + merge 回 `master`

**Files:** 无（纯验证 + merge）

- [ ] **Step 1: lint + format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` 两次

若 `ruff format --check` 报差异：`uv run ruff format .`，再跑一次 check，commit 格式修正：

```bash
git add -u
git commit -m "style: ruff format"
```

- [ ] **Step 2: 完整 pytest**

Run: `uv run pytest -v --cov`
Expected: 全 passed；`bubblify/core.py` 覆盖率 ≥ 90%

- [ ] **Step 3: 手动冒烟（加几何 + 导出 YAML + 导出 URDF）**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf`
在浏览器 UI：
- 加一个 sphere（link2）、一个 box（link3）、一个 cylinder（link3，且勾一次 Display as Capsule，确认警告文案可见）
- `💾 Export` → `Export Geometries (YAML)` → 确认 status 绿
- `Export URDF with Geometries` → 确认 status 绿
Ctrl+C 退。

Run: `grep -c collision_spheres assets/xarm6/xarm6_rs_geometries.yml`
Expected: `0`

- [ ] **Step 4: 手动冒烟（重新加载导出的 YAML，验证几何复现）**

Run: `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config assets/xarm6/xarm6_rs_geometries.yml`
浏览器确认 3 个几何都正确出现在 link2 / link3 上。Ctrl+C 退。

- [ ] **Step 5: Merge `cleanup/core-tests` → `master`**

Run:
```bash
git checkout master
git merge --no-ff cleanup/core-tests -m "merge: cleanup and core tests

8-step cleanup: removed upstream-compat paths, extracted YAML I/O to
core, added pytest safety net (~30 tests, core coverage ≥90%). See
docs/superpowers/specs/2026-04-17-cleanup-and-core-tests-design.md"
git log --oneline -15
```

Expected: merge commit 出现在 master 历史顶端

- [ ] **Step 6: 可选删除本地分支**

Run: `git branch -d cleanup/core-tests`
Expected: 分支删除成功

---

## 验证清单（完成所有 Task 后）

- [ ] `git log master --oneline cleanup/core-tests..HEAD` 列出 8 个 cleanup commits + 1 个 merge
- [ ] `uv run ruff check .` 通过
- [ ] `uv run ruff format --check .` 通过
- [ ] `uv run pytest -v` 全绿，≥ 30 测试
- [ ] `uv run pytest --cov` 的 `bubblify/core.py` 覆盖率 ≥ 90%
- [ ] `grep -rn "Sphere = Geometry\|SphereStore = GeometryStore\|get_spheres_for_link" bubblify/` 无输出
- [ ] `grep -rn "collision_spheres" bubblify/` 无输出（注释或字符串都清掉）
- [ ] `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf` 启动后 GUI 功能正常，cylinder 面板可见警告文案
- [ ] 重新导出的 YAML 文件不含 `collision_spheres` 键

## 风险与回滚

- **Task 4 改动较大（~150 行 core.py 新代码 + gui.py 两处大重写）**。若 Step 9/12/13 手动冒烟失败，`git reset --hard HEAD~1` 回滚 Task 4 commit，localize 出错的子函数再重试。
- **Task 6 的 `test_rotation` 可能暴露 gimbal lock 行为与测试期望不符**：按 spec 失败预案停下来讨论，不得改测试凑过。
- **Task 7 后旧 YAML 文件无法加载**：属预期、spec 已接受。若真需要读回旧 `.yml`，一次性手动转：`yaml.load → 仅保留 collision_spheres → 按新格式重写 collision_geometries + type:sphere`。
