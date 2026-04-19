# Bubblify 清理 + Core 测试安全网 设计

**日期：** 2026-04-17
**负责人：** Hank Li（fork 自用，不追求 upstream 合并）
**分支：** `cleanup/core-tests`（单独分支，完成后 merge 回 `master`）

## 背景

Bubblify 当前代码里背负了若干"为 upstream PR 合并"保留的向后兼容路径：`Sphere=Geometry`/`SphereStore=GeometryStore` Python 别名、YAML 导出双写 `collision_spheres` + `collision_geometries`、YAML 加载器的旧格式 fallback 分支。与此同时 `tests/` 目录下 14 个文件绝大多数是 smoke script（构造 `BubblifyApp` + `print` + 不断言 + 抢端口），没有真正的回归保护。

维护者 bheijden 在 PR #3 review 里要求保留这些兼容路径。由于 fork 是自用、不推 upstream，**本次明确不采纳这些建议**。

## 目标

- 清掉所有为 upstream 兼容保留的代码路径
- 修已知 bug：`bubblify/gui.py:19-20` `inject_geometries_into_urdf_xml` 重复 import
- 把 YAML load/dump 的数据层逻辑从 `gui.py` 剥出，放到 `core.py`，便于独立测试
- 处理 `display_as_capsule` 字段的用户心智误导（该字段只影响显示，导出 URDF 会丢失）
- 为 `core.py` 建立真正的 pytest 单测，作为后续任何重构的安全网

## 后续工作路线图（本次不做）

| 条目 | 触发条件 / 优先级 | 备注 |
|---|---|---|
| `gui.py` 结构性拆分 | 本次 core 测试落地后下一轮 | 1800 行单类 `BubblifyApp` 拆成 panel / gizmo manager / export / app orchestrator；`_updating_geometry_ui` 重入标志就是类过大的信号 |
| CI（GitHub Actions） | 有外部 contributor 时 | 自己用时本地 `uv run pytest` 已足 |
| capsule 作为一等 primitive | 有明确规划器需求时 | URDF 不支持 capsule 原语；需导出成 "两 sphere + 一 cylinder" 组合 |
| 新 primitive（mesh 作为 primitive、cone 等） | 按实际需求 | |
| Pydantic schema 校验 YAML | 当 YAML 格式开始变动频繁 | 现阶段 dataclass + 手工 validator 够用 |
| 对称镜像 / undo / redo | UX 改进轮 | |
| 文档 / README 更新 | 清理后可能出现示例失效 | 本次只被动修复被清理直接破坏的示例命令 |

## 范围（本次做什么）

### 目标（做）

1. **清理**
   - 删 `Sphere = Geometry`（`core.py:137`）
   - 删 `SphereStore = GeometryStore`（`core.py:233`）
   - 删 `GeometryStore.get_spheres_for_link()`（`core.py:227-229`）
   - `bubblify/__init__.py` 的 `__all__` 和 `from .core import` 同步移除 `Sphere` / `SphereStore`
   - 修 `gui.py:19-20` 重复 `import inject_geometries_into_urdf_xml`
   - 删 YAML 导出中的 `collision_spheres` 双写块（`gui.py:634-637` 附近）
   - 删 YAML 加载器的旧格式 fallback 分支（`gui.py:1747-1758`）
   - `display_as_capsule` 勾选项下方新增 `server.gui.add_markdown("⚠️ Capsule 仅用于显示，导出 URDF 时按 cylinder 处理")`

2. **抽核心：YAML I/O 数据层**
   - 在 `core.py` 新增：
     - `YAML_SCHEMA_VERSION = 1` 常量
     - `GeometrySpec` dataclass（解析后的几何配置，无 `id` / 无 `viser.node`）
     - `load_geometry_specs_from_yaml(path: Path) -> List[GeometrySpec]`
     - `dump_geometries_to_yaml(store: GeometryStore, path: Path, *, include_metadata: bool = True) -> None`
   - `gui.py` 里 `_load_geometry_config_yaml` 缩为薄包装：调 `load_geometry_specs_from_yaml` → 循环 `store.add(**params)` → `_create_geometry_visualization`
   - `gui.py` 里 `_setup_export_controls` 的 YAML 按钮 handler 改为直接调 `dump_geometries_to_yaml`，只保留 UI 状态更新 / error toast

3. **测试：`tests/` 重写**
   - 删 `tests/` 下所有现有 `.py` 文件
   - 新建布局：
     ```
     tests/
     ├── conftest.py              # sample_urdf_path / mixed_store fixtures
     ├── test_geometry.py         # Geometry 字段 + get_effective_radius + RPY↔quat 同步方法
     ├── test_rotation.py         # rpy_to_quaternion / quaternion_to_rpy 双向 + 边界
     ├── test_geometry_store.py   # CRUD + 索引一致性
     ├── test_urdf_injection.py   # inject_geometries_into_urdf_xml 输出结构
     └── test_yaml_io.py          # load/dump round-trip + 错误路径
     ```

### 非目标（不做）

见上方"后续工作路线图"。

## 设计

### `core.py` API 扩展

```python
# 新增
YAML_SCHEMA_VERSION = 1

@dataclasses.dataclass
class GeometrySpec:
    """YAML 解析后的一条几何配置，尚未分配 id / 挂接 viser node。
    
    用于 load 路径：YAML → GeometrySpec 列表 → 调用方负责转成 Geometry
    （通过 store.add(**spec_kwargs)）并建立可视化。
    """
    link: str
    xyz: Tuple[float, float, float]
    geometry_type: GeometryType
    rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    # type-specific — 按 geometry_type 只填对应子集，其余保持 None
    radius: Optional[float] = None
    size: Optional[Tuple[float, float, float]] = None
    cylinder_radius: Optional[float] = None
    cylinder_height: Optional[float] = None
    # 注：Geometry.display_as_capsule 不序列化到 YAML（仅运行时显示状态），
    # 因此 GeometrySpec 不包含该字段。此行为沿用清理前的现状。

    def to_store_kwargs(self) -> Dict[str, Any]:
        """转成 GeometryStore.add() 的 kwargs（略去 None 值）。"""


def load_geometry_specs_from_yaml(path: Path) -> List[GeometrySpec]:
    """读 YAML，返回 GeometrySpec 列表。
    
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 顶层缺 collision_geometries 键 / 条目缺必填字段 / 未知 type
    """


def dump_geometries_to_yaml(
    store: GeometryStore,
    path: Path,
    *,
    include_metadata: bool = True,
) -> None:
    """序列化 store 到 YAML，只写 collision_geometries 键。
    
    metadata（可选）: total_geometries, links, export_timestamp, schema_version
    """
```

### YAML 格式（清理后）

```yaml
collision_geometries:
  base_link:
    - center: [0.0, 0.0, 0.0]
      type: sphere
      radius: 0.05
      # 注：sphere 不写 rpy
    - center: [0.1, 0.0, 0.0]
      type: box
      size: [0.1, 0.1, 0.1]
      rpy: [0.785, 0.0, 0.0]
    - center: [0.2, 0.0, 0.0]
      type: cylinder
      radius: 0.03
      height: 0.15
      rpy: [0.0, 0.0, 1.047]
metadata:
  total_geometries: 3
  links: [base_link]
  export_timestamp: 1745000000.0
  schema_version: 1
```

**不再写** `collision_spheres` 键。**不再支持加载**只有 `collision_spheres` 键的旧文件。

### 测试矩阵

| 文件 | 覆盖点 |
|---|---|
| `test_geometry.py` | 默认字段值；`get_effective_radius()` 对 sphere / box / cylinder 各返回正确值；`update_rpy_from_quaternion` 和 `update_quaternion_from_rpy` 双向同步，调用后另一字段随之更新 |
| `test_rotation.py` | 零旋转 `(0,0,0)` 往返；单轴 ±π/4、±π/2 往返；复合角度（roll+pitch+yaw 非零）往返数值误差 < 1e-9；pitch = ±π/2 gimbal lock 边界行为记录（不苛求 roll/yaw 精确，但转回矩阵应一致） |
| `test_geometry_store.py` | `add` 返回 Geometry，`by_id[id] is geometry`；连续 `add` 的 id 单调递增；`ids_by_link` 包含对应 id；`remove` 后 `by_id` / `ids_by_link` 都清理；某 link 最后一个 geometry 被 remove 后 `ids_by_link` 不再有该 key；`remove(不存在 id)` 返回 `None` 不抛；`clear()` 后两个索引都空；`get_geometries_for_link` 返回顺序与插入顺序一致 |
| `test_urdf_injection.py` | 用 `assets/xarm6/xarm6_rs.urdf`：(1) 注入混合 3 种 geometry 的 store 后输出 XML 能被 `yourdfpy.URDF.load` 重新解析无错；(2) 原 URDF 里所有 `<collision>` 元素在输出中消失（count 从 N → 注入数）；(3) sphere 的 `<origin rpy>` 恒为 `"0 0 0"`，即使 store 里的 geometry 设了非零 rpy；(4) store 里指向不存在 link 名的 geometry 被跳过，不抛异常；(5) box 和 cylinder 的 rpy 值正确透传 |
| `test_yaml_io.py` | (1) `dump → load` 三种 geometry 全覆盖，字段完全一致；(2) 空 store `dump` 产出合法 YAML 且 `load` 回来是空列表；(3) load 不存在文件抛 `FileNotFoundError`；(4) load 合法 YAML 但缺 `collision_geometries` 顶层键抛 `ValueError`；(5) load 未知 `type` 字段抛 `ValueError`；(6) load 的 sphere 条目缺 `radius` 抛 `ValueError` |

**Fixtures（`conftest.py`）：**
- `sample_urdf_path`：`Path` 指向 `assets/xarm6/xarm6_rs.urdf`
- `mixed_store`：预填 3 个 link、sphere/box/cylinder 共 6 条记录的 `GeometryStore`

**成功标准：**
- `uv run pytest` 全绿
- 覆盖率：把 `EnhancedViserUrdf` 类（依赖 `viser.ViserServer`，本轮不可测）从统计中排除后，`core.py` 其余部分覆盖率 ≥ 90%。具体配置：在 `pyproject.toml` 新增
  ```toml
  [tool.coverage.run]
  source = ["bubblify.core"]
  [tool.coverage.report]
  exclude_also = [
      "class EnhancedViserUrdf",  # 依赖 viser，本轮不测
  ]
  ```
  （或改用 `# pragma: no cover` 标注整个类，二选一）
- 每个新 API（`Geometry`、`rpy_to_quaternion`、`quaternion_to_rpy`、`GeometryStore.add/remove/get/clear`、`inject_geometries_into_urdf_xml`、`load_geometry_specs_from_yaml`、`dump_geometries_to_yaml`）至少有一个 happy path + 一个边界/错误 case
- 测试总时间 < 2 秒
- 无测试启动 viser server / 抢端口

### 约束

- Python ≥ 3.8：`from __future__ import annotations` 已在用；避免 3.9+ 专用语法
- ruff 现有配置不动（line-length 127、忽略 E402/E501）
- 不引入新运行时依赖；`pyyaml` 已经是间接依赖（`viser` 传递）；`pytest` 已在 dev group
- 本次需在 `pyproject.toml` 的 `dev` 依赖组新增 `pytest-cov` 以支撑覆盖率检查

## 执行步骤

分支：`cleanup/core-tests`（从 `master` 切出，完成后 merge 回 master）

每步一个 commit，可独立回滚。

| # | 动作 | 自证 |
|---|---|---|
| 1 | 修 `gui.py:19-20` 重复 import | `uv run ruff check .` 通过；`uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf` 启动正常、加一条 sphere、导出 URDF 无异常 |
| 2 | 删 `Sphere` / `SphereStore` / `get_spheres_for_link` 别名；同步 `__init__.py` | `python -c "from bubblify import BubblifyApp"` 无 ImportError；ruff 通过 |
| 3 | `display_as_capsule` 下方加 warning markdown | 启动 GUI，选中 cylinder，确认文字显示 |
| 4 | 抽 YAML 数据层到 `core.py`：新增 `GeometrySpec` + `load_geometry_specs_from_yaml`（此时**只认新格式**，无旧格式 fallback）+ `dump_geometries_to_yaml`（此时**仍写 `collision_spheres` 双写**，保持行为）；`gui.py` 的 `_load_geometry_config_yaml` 改造为：先尝试 `load_geometry_specs_from_yaml`，捕获 `ValueError` 时落到**仍保留在 `gui.py` 的旧格式 fallback 分支**；`_setup_export_controls` 的 YAML 按钮改调 `dump_geometries_to_yaml`。此步**只迁移数据层、不改外部行为**（双写 + 旧格式支持）。 | 手动：加载 `assets/xarm6/xarm6_rs_spherized.yml` → 可视化正常 → 导出覆盖 → diff 无关键差异（时间戳可变） |
| 5 | `rm tests/*.py`；建 `conftest.py` + 5 个测试文件空骨架（只 import、pass） | `uv run pytest` 退出码 0 |
| 6 | 按测试矩阵填充用例；在 `pyproject.toml` 配置 coverage 排除 `EnhancedViserUrdf` | `uv run pytest -v` 全绿；`uv run pytest --cov` 报告中 `bubblify/core.py` 覆盖率 ≥ 90%（排除 `EnhancedViserUrdf` 后）；时间 < 2s |
| 7 | 改 `dump_geometries_to_yaml` 不再写 `collision_spheres` 双写；删 `gui.py` 里 `_load_geometry_config_yaml` 残留的旧格式 fallback 分支；`load_geometry_specs_from_yaml` 的签名和实现在步骤 4 起就已"只认新格式"，此步无需改动 | `uv run pytest` 全绿（步骤 6 的 round-trip 测试覆盖）；手动 GUI 再跑一次加载+导出：确认导出的 YAML 不再含 `collision_spheres` 键 |
| 8 | 更新 `CLAUDE.md` 过时描述（"YAML 同时输出新旧格式"相关句子） | 人肉 review |

### 全局回归检查（merge 回 master 前）

1. `uv run ruff check . && uv run ruff format --check .`
2. `uv run pytest -v`
3. 手动冒烟：
   - `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf` → 加 sphere / box / cylinder 各一个 → 导出 YAML → 退出
   - `uv run bubblify --urdf_path assets/xarm6/xarm6_rs.urdf --geometry_config <刚导出的 yml>` → 确认几何重现

### 失败预案

- 步骤 6 发现 core 实际行为与预期不符（RPY 边界、XML 结构细节）：停，讨论是改实现还是改测试期望，**不得"改测试凑过"**
- 步骤 7 清理后 pytest 出红：回退该 commit，检查步骤 6 的测试是否依赖了旧行为（典型：测试读了自带双写 `collision_spheres` 的 YAML）——属测试写法漏，修测试再前进

## 风险

- **破坏性**：`Sphere` / `SphereStore` 别名被删，`from bubblify import Sphere` 会炸。0.1.0 alpha + 自用，视为零影响。
- **破坏性**：YAML 旧格式 fallback 被删，只有 `collision_spheres` 键的 `.yml` 文件无法加载。`assets/xarm6/*_spherized.yml` 是新格式，不受影响；硬盘上其他老 `.yml`（若有）会被拒。用户已明确接受。
- **测试 fixture 硬编码 `assets/xarm6/xarm6_rs.urdf`**：若 asset 路径调整，测试一起动。风险低，因为 asset 布局短期内无变更计划。
