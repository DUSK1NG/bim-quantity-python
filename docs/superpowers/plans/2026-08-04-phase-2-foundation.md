# Phase 2 Foundation Implementation Plan

阶段2基础工程实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 10/11 与 Python 3.10/3.11 上建立可复现、可验证的 BIM 工程量基础工程：稳定 schema、带版本的显式配置、240 行固定种子演示数据及最小测试与文档，为后续 CSV 主流程提供契约。

**Architecture:** 依赖顺序固定为 `src/schema.py`（字段/枚举契约）→ `src/config_loader.py`（读取并校验七个配置）→ `scripts/generate_sample_data.py`（只消费 `ProjectConfig` 与 schema 常量）→ `data/sample/*.csv`；测试从读回 CSV 核对行数、覆盖范围和七类异常。此阶段不实现 CSV reader、pipeline、Streamlit 或 IFC reader。

**Tech Stack:** Python 3.10/3.11，Windows 10/11，标准库 `pathlib`、`json`、`logging`、`dataclasses`，`pandas`、`pytest`；IfcOpenShell 只放在 `requirements-ifc.txt` 的可选依赖中。

## Global Constraints

- 运行环境目标固定为 Python 3.10 或 3.11、Windows 10/11；所有命令使用相对仓库路径，不写绝对路径。验收必须记录实际解释器版本；本机默认 `python` 可能是 Python 3.13.11，3.13 的测试只能作为探索性结果，不能冒充 3.10/3.11 兼容性证据。
- `requirements.txt` 只列本阶段/后续 CSV、Excel、图表、Streamlit 和测试所需成熟库；为同时支持 Python 3.10/3.11 使用 `pandas>=2.2,<3.0`；`requirements-ifc.txt` 只增加可选 `ifcopenshell>=0.8,<0.9`，缺它不能阻断 CSV 基础工程。
- 复用 `pathlib`、`json`、`logging`、`dataclasses`、`pandas`、`pytest`；不自建通用配置框架、CSV reader、pipeline、Streamlit 或 IFC reader。
- 七个配置文件各自承担一类映射/规则：`field_mapping.json`、`category_mapping.json`、`level_mapping.json`、`material_mapping.json`、`naming_rules.json`、`quality_rules.json`、`sample_unit_prices.csv`；JSON 顶层必须含 `config_version`，未知键、重复映射、缺版本和非法值在加载时可解释地失败。
- 映射必须分文件、显式可审阅；业务代码不复制隐藏映射。配置加载接口与样例生成接口在所有任务、测试和文档中保持同名、同参数、同返回类型。
- 标准字段与枚举精确遵循设计文档：必备列为 `element_id`、`guid`、`source`、`ifc_class`、`category`、`element_name`、`type_name`、`level`、`material`、`length_m`、`area_m2`、`volume_m3`、`quantity`、`unit`、`unit_price`、`total_cost`、`quantity_source`、`quality_status`；`quantity_source` 仅允许 `IFC BaseQuantity`、`Parameter Calculation`、`CSV Schedule`、`Missing`，`quality_status` 仅允许 `Pass`、`Warning`、`Error`。
- 固定种子必须是 `20260804`，恰好生成 240 行；覆盖标准化后的`一层`、`二层`、`三层`和 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类；字段顺序写入配置并在测试核对。
- 生成结果必须包含且精确核对以下七类预置异常数量；七类异常使用互不相交的 `raw_row_number` 集合：缺失材料 5 条、缺失楼层 3 条、重复 GUID 2 组（4 条受影响行）、体积为零 4 条、名称不符合规则 3 条、单位异常 2 条、单价无法匹配 2 条。测试必须从读回的 CSV 字段独立重算这些集合，而不是只统计生成器标签或日志。
- 样例和人工复核表都必须标明“程序演示数据”，免责声明原文为“本项目单价为教学示例数据，不用于正式工程造价。”；不得暗示真实项目精度或正式造价。
- 错误信息面向初学者：指出文件/配置项、失败原因和可执行修复建议；不得静默猜测、填零、删除坏行或伪造 ID。
- 本阶段只创建第 10 节列出的基础工程、配置、样例、占位目录、测试和文档；不得实现 `src/csv_reader.py`、`src/data_cleaner.py`、`src/quantity_calculator.py`、`src/cost_calculator.py`、`src/quality_checker.py`、`src/validation.py`、`src/report_generator.py`、`src/pipeline.py`、`src/ifc_reader.py`、`app/` 或 `scripts/run_pipeline.py`/`scripts/export_report.py`。

---

## 文件与职责地图

| 路径 | 本阶段职责 |
|---|---|
| `README.md` | 安装、生成样例、运行测试、免责声明、范围与退出前置说明；不描述尚未实现的命令为已可用。 |
| `LICENSE` | 保留/创建仓库许可文件；若仓库已有内容，只确认存在并在计划执行时不改动其法律文本。 |
| `requirements.txt` | Python 依赖基线，至少包含 `pandas` 与 `pytest`，并为后续 Excel/图表/UI 预留成熟库版本范围。 |
| `requirements-ifc.txt` | 仅列 `ifcopenshell` 可选依赖，并说明不会被基础安装导入。 |
| `pyproject.toml` | 包元数据、Python 版本约束、pytest 配置和 `src` 包发现。 |
| `.gitignore`、`.env.example` | 忽略本地环境/输出，提供不含绝对路径的环境变量示例。 |
| `src/__init__.py` | 暴露 `__version__` 与 `SCHEMA_VERSION`，不导入可选 IFC。 |
| `src/schema.py` | `STANDARD_COLUMNS`、枚举常量、`SampleDataSpec`/`SchemaValidationResult` 数据类、标准字段顺序和 DataFrame 契约校验。 |
| `src/config_loader.py` | `ProjectConfig` 数据类与 `load_project_config(config_dir)` 接口；读取、版本校验、映射重复检查、单价表列/数值检查。 |
| `configs/*.json`、`configs/sample_unit_prices.csv` | 七类显式、带 `config_version` 的映射/规则和教学单价；生成器与 loader 只从这些文件读取。 |
| `scripts/generate_sample_data.py` | `generate_sample_data(output_dir, config_dir, seed=20260804, rows=240) -> SampleGenerationResult`；写入 `sample_elements.csv`、`sample_manual_validation.csv` 和生成元数据。 |
| `data/sample/sample_elements.csv` | 固定种子、240 行、固定字段顺序的可追溯演示明细。 |
| `data/sample/sample_manual_validation.csv` | 人工抽查子集，含自动/人工数量、复核日期、免责声明与程序演示数据标记。 |
| `data/sample/README.md` | 字段、异常清单、生成命令、程序演示免责声明和不用于正式造价的说明。 |
| `data/raw/.gitkeep`、`data/processed/.gitkeep`、`outputs/{excel,charts,reports}/.gitkeep` | 空目录占位，不放生成的运行产物。 |
| `tests/test_config_loader.py` | 配置成功加载、版本/重复映射/缺键/无效单价的先失败测试。 |
| `tests/test_sample_data.py` | 固定种子哈希、240 行、三层六类、七类异常精确计数、人工样例可读性的测试。 |
| `docs/data_dictionary.md` | 标准字段类型、可空性、枚举、单位、来源与追溯语义。 |
| `docs/technical_route.md` | 路线 A 的阶段2基础边界、配置接口、数据流契约、后续禁止越界项。 |
| `assets/README.md` | 资产目录用途与不提交受限 BIM/真实项目数据的说明。 |

## 接口契约（任务间不可变）

以下签名必须原样实现，后续任务只能扩展返回对象字段，不能改名、改参数顺序或改变返回类型：

```python
# src/config_loader.py
def load_project_config(config_dir: Path) -> ProjectConfig:
    """读取并严格校验七个配置文件；错误以 ConfigError 抛出。"""

# scripts/generate_sample_data.py
def generate_sample_data(
    output_dir: Path,
    config_dir: Path,
    seed: int = 20260804,
    rows: int = 240,
) -> SampleGenerationResult:
    """写入固定字段顺序的样例明细和人工复核表，返回实际输出摘要。"""
```

实现接口时使用 `pathlib.Path`（不是字符串路径）；`ProjectConfig` 与 `SampleGenerationResult` 都是 `@dataclass(frozen=True)`。`SampleGenerationResult` 至少包含 `elements_path: Path`、`manual_validation_path: Path`、`rows: int`、`seed: int`、`sha256: str`、`exception_counts: dict[str, int]`。

---

### Task 1: 元数据、依赖、schema 与配置契约

**Files:**
- Create: `README.md`
- Create: `LICENSE`（只有缺失时；不覆盖既有许可证文本）
- Create: `requirements.txt`
- Create: `requirements-ifc.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/schema.py`
- Test: `tests/test_config_loader.py`

**Interfaces:**
- `src/schema.py` 提供 `STANDARD_COLUMNS: tuple[str, ...]`、`QUANTITY_SOURCES: tuple[str, ...]`、`QUALITY_STATUSES: tuple[str, ...]`、`SampleDataSpec`、`SchemaValidationResult`、`validate_standard_dataframe(frame: pandas.DataFrame) -> SchemaValidationResult`。
- 本任务只验证 schema 契约；配置加载器在 Task 2 创建。依赖顺序不得反转：`schema.py` 不读取配置；Task 2 的 `config_loader.py` 读取并校验七个配置后才构造 `ProjectConfig`；Task 3 的生成器只调用 `load_project_config` 并消费 `ProjectConfig`/schema 常量，不重新解析 JSON 或复制映射。

- [ ] **Step 1: Write the failing test**

创建 `tests/test_config_loader.py`，本任务先只写不依赖配置文件的 schema 契约测试：

```python
import pandas as pd
from src.schema import QUALITY_STATUSES, QUANTITY_SOURCES, STANDARD_COLUMNS, validate_standard_dataframe


def test_schema_constants_are_exact():
    assert STANDARD_COLUMNS == (
        "element_id", "guid", "source", "ifc_class", "category",
        "element_name", "type_name", "level", "material", "length_m",
        "area_m2", "volume_m3", "quantity", "unit", "unit_price",
        "total_cost", "quantity_source", "quality_status",
    )
    assert QUANTITY_SOURCES == (
        "IFC BaseQuantity", "Parameter Calculation", "CSV Schedule", "Missing",
    )
    assert QUALITY_STATUSES == ("Pass", "Warning", "Error")


def test_validate_standard_dataframe_reports_missing_columns():
    result = validate_standard_dataframe(pd.DataFrame({"guid": ["x"]}))
    assert result.valid is False
    assert "element_id" in result.missing_columns
```

预期此时测试失败，因为 `src` 包和 schema 尚不存在；它不读取 Task 2 配置。

- [ ] **Step 2: Run test to verify it fails**

运行：

```powershell
python -m pytest tests/test_config_loader.py -q
```

预期：`FAIL`，首先出现 `ModuleNotFoundError: No module named 'src'`；不得因为环境路径写死而通过。

- [ ] **Step 3: Write minimal implementation**

创建包元数据和 schema。`src/__init__.py`：

```python
"""BIM quantity foundation contracts."""

__version__ = "0.2.0"
SCHEMA_VERSION = "2.0"
```

`src/schema.py`（本任务唯一业务模块）：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

STANDARD_COLUMNS: tuple[str, ...] = (
    "element_id", "guid", "source", "ifc_class", "category",
    "element_name", "type_name", "level", "material", "length_m",
    "area_m2", "volume_m3", "quantity", "unit", "unit_price",
    "total_cost", "quantity_source", "quality_status",
)
QUANTITY_SOURCES: tuple[str, ...] = (
    "IFC BaseQuantity", "Parameter Calculation", "CSV Schedule", "Missing",
)
QUALITY_STATUSES: tuple[str, ...] = ("Pass", "Warning", "Error")
IFC_CLASSES: tuple[str, ...] = (
    "IfcBeam", "IfcColumn", "IfcSlab", "IfcWall", "IfcDoor", "IfcWindow",
)
LEVELS: tuple[str, ...] = ("一层", "二层", "三层")
UNITS: tuple[str, ...] = ("m", "m²", "m³", "个", "樘")


@dataclass(frozen=True)
class SampleDataSpec:
    seed: int = 20260804
    rows: int = 240
    levels: tuple[str, ...] = LEVELS
    ifc_classes: tuple[str, ...] = IFC_CLASSES
    exception_counts: dict[str, int] = field(default_factory=lambda: {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid_groups": 2,
        "zero_volume": 4,
        "invalid_name": 3,
        "invalid_unit": 2,
        "unmatched_unit_price": 2,
    })


@dataclass(frozen=True)
class SchemaValidationResult:
    valid: bool
    missing_columns: tuple[str, ...] = ()
    invalid_enum_values: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    messages: tuple[str, ...] = ()


def validate_standard_dataframe(frame: pd.DataFrame) -> SchemaValidationResult:
    missing = tuple(column for column in STANDARD_COLUMNS if column not in frame.columns)
    invalid: dict[str, tuple[Any, ...]] = {}
    if "quantity_source" in frame:
        values = tuple(sorted(set(frame["quantity_source"].dropna()) - set(QUANTITY_SOURCES)))
        if values:
            invalid["quantity_source"] = values
    if "quality_status" in frame:
        values = tuple(sorted(set(frame["quality_status"].dropna()) - set(QUALITY_STATUSES)))
        if values:
            invalid["quality_status"] = values
    messages = tuple([f"missing required column: {name}" for name in missing])
    messages += tuple(f"invalid {name} values: {values}" for name, values in invalid.items())
    return SchemaValidationResult(not missing and not invalid, missing, invalid, messages)
```

依赖与元数据需至少体现：Python `>=3.10,<3.12`、`pandas>=2.2,<3.0`、`pytest>=8,<10`，并为后续阶段固定成熟库版本范围；`requirements-ifc.txt` 只写 `ifcopenshell>=0.8,<0.9`。Task 1 的 README 只说明 schema 测试已可用，并明确样例生成命令要到 Task 3 才可用，不能把尚未创建的脚本写成当前能力。

- [ ] **Step 4: Run test to verify it passes**

运行：

```powershell
python -m pytest tests/test_config_loader.py -q
```

预期：schema 常量和 schema 缺列测试全部 `PASS`。若缺少 `pandas`/`pytest`，先按 README 的 `python -m pip install -r requirements.txt` 安装，再重复同一命令；不要把安装缺失误报为代码通过。

- [ ] **Step 5: Commit**

```powershell
git add README.md LICENSE requirements.txt requirements-ifc.txt pyproject.toml .gitignore .env.example src/__init__.py src/schema.py tests/test_config_loader.py
git commit -m "feat: establish phase 2 schema and config contracts"
```

提交前确认 `git diff --cached --check` 无空白错误且只包含 Task 1 文件。

---

### Task 2: 七个显式配置文件与基础说明文档

**Files:**
- Create: `src/config_loader.py`
- Create: `configs/field_mapping.json`
- Create: `configs/category_mapping.json`
- Create: `configs/level_mapping.json`
- Create: `configs/material_mapping.json`
- Create: `configs/naming_rules.json`
- Create: `configs/quality_rules.json`
- Create: `configs/sample_unit_prices.csv`
- Create: `data/raw/.gitkeep`
- Create: `data/processed/.gitkeep`
- Create: `outputs/excel/.gitkeep`
- Create: `outputs/charts/.gitkeep`
- Create: `outputs/reports/.gitkeep`
- Create: `docs/data_dictionary.md`
- Create: `docs/technical_route.md`
- Create: `assets/README.md`

**Interfaces:**
- Every JSON is UTF-8 and has exactly the documented top-level `config_version` plus its explicit payload; every JSON uses `config_version: "2.0"`.
- `sample_unit_prices.csv` columns and order are exactly `category,material,unit,unit_price`; all prices are positive teaching values and include at least one deliberate unmatched category/material/unit combination for two generated rows.
- `load_project_config(config_dir: Path) -> ProjectConfig` from this task must load these files without special cases; Task 3 may call only this interface.

- [ ] **Step 1: Write the failing test**

在 `tests/test_config_loader.py` 追加配置加载失败测试和完整结构断言（本任务首次导入 `src.config_loader`）：

```python
from pathlib import Path
import json
import shutil
import pandas as pd
import pytest

from src.config_loader import ConfigError, ProjectConfig, load_project_config

@pytest.fixture()
def repo_config_dir() -> Path:
    return Path(__file__).parents[1] / "configs"


def test_load_project_config_returns_frozen_config(repo_config_dir: Path):
    config = load_project_config(repo_config_dir)
    assert isinstance(config, ProjectConfig)
    assert config.config_version == "2.0"
    with pytest.raises(Exception):
        config.config_version = "changed"


def test_all_phase_two_configs_load_without_unknown_top_level_keys(repo_config_dir: Path):
    config = load_project_config(repo_config_dir)
    assert set(config.field_mapping) == {"config_version", "aliases", "field_order"}
    assert set(config.category_mapping) == {"config_version", "canonical_categories", "ifc_class_to_category", "aliases"}
    assert set(config.level_mapping) == {"config_version", "canonical_levels", "aliases"}
    assert set(config.material_mapping) == {"config_version", "canonical_materials", "aliases"}
    assert set(config.naming_rules) == {"config_version", "allowed_patterns", "invalid_name_examples"}
    assert set(config.quality_rules) == {"config_version", "rules"}
    assert list(config.unit_prices.columns) == ["category", "material", "unit", "unit_price"]
    assert config.level_mapping["canonical_levels"] == ["一层", "二层", "三层"]
    assert set(config.category_mapping["canonical_categories"]) == {
        "Beam", "Column", "Slab", "Wall", "Door", "Window",
    }


def test_loader_rejects_missing_config_version(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "level_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("config_version")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="level_mapping.json.*config_version"):
        load_project_config(bad_dir)


def test_loader_rejects_unknown_top_level_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "quality_rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="quality_rules.json.*未知顶层键"):
        load_project_config(bad_dir)


def test_loader_rejects_duplicate_alias_in_any_mapping(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "material_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["aliases"]["钢材"].append(payload["aliases"]["混凝土"][0])
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="material_mapping.json.*重复别名"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_unit_price(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "unit_price"] = -1
    frame.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="unit_price.*正数"):
        load_project_config(bad_dir)
```

预期：因 `src/config_loader.py` 和七个文件尚不存在或键集合不符合约定而 `FAIL`。

- [ ] **Step 2: Run test to verify it fails**

运行：

```powershell
python -m pytest tests/test_config_loader.py::test_all_phase_two_configs_load_without_unknown_top_level_keys -q
```

预期：`FAIL`，错误指出缺少配置文件或顶层键不匹配。

- [ ] **Step 3: Write minimal implementation**

创建 `src/config_loader.py`。loader 严格验证六个 JSON 的允许顶层键、版本和所有 `aliases` 的全局唯一性，并用中文给出文件名、原因和修复建议：

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from src.schema import STANDARD_COLUMNS

CONFIG_VERSION = "2.0"
JSON_FILES = (
    "field_mapping.json", "category_mapping.json", "level_mapping.json",
    "material_mapping.json", "naming_rules.json", "quality_rules.json",
)
ALLOWED_KEYS = {
    "field_mapping.json": {"config_version", "aliases", "field_order"},
    "category_mapping.json": {"config_version", "canonical_categories", "ifc_class_to_category", "aliases"},
    "level_mapping.json": {"config_version", "canonical_levels", "aliases"},
    "material_mapping.json": {"config_version", "canonical_materials", "aliases"},
    "naming_rules.json": {"config_version", "allowed_patterns", "invalid_name_examples"},
    "quality_rules.json": {"config_version", "rules"},
}


class ConfigError(ValueError):
    """面向初学者、带修复建议的配置错误。"""


@dataclass(frozen=True)
class ProjectConfig:
    config_version: str
    field_mapping: Mapping[str, Any]
    category_mapping: Mapping[str, Any]
    level_mapping: Mapping[str, Any]
    material_mapping: Mapping[str, Any]
    naming_rules: Mapping[str, Any]
    quality_rules: Mapping[str, Any]
    unit_prices: pd.DataFrame


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"缺少 {path.name}；请在 configs/ 下创建该文件。")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取 {path.name}：{exc}；请保存为 UTF-8 JSON。") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{path.name} 顶层必须是对象；请检查 JSON 大括号。")
    unknown = set(payload) - ALLOWED_KEYS[path.name]
    if unknown:
        names = "、".join(sorted(unknown))
        raise ConfigError(f"{path.name} 含未知顶层键 {names}；请删除未列入契约的键。")
    if payload.get("config_version") != CONFIG_VERSION:
        raise ConfigError(f"{path.name} 的 config_version 必须为 {CONFIG_VERSION}；请修正版本后重试。")
    return payload


def _assert_unique_aliases(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    for filename, payload in payloads.items():
        aliases = payload.get("aliases")
        if aliases is None:
            continue
        if not isinstance(aliases, dict):
            raise ConfigError(f"{filename} 的 aliases 必须是对象；请按 canonical 名称分组。")
        seen: dict[str, tuple[str, str]] = {}
        for canonical, values in aliases.items():
            if not isinstance(values, list) or not values:
                raise ConfigError(f"{filename} 的 aliases[{canonical!r}] 必须是非空列表；请补充别名。")
            for alias in values:
                if not isinstance(alias, str) or not alias.strip():
                    raise ConfigError(f"{filename} 的别名必须是非空字符串；请删除空值。")
                normalized = alias.strip().casefold()
                if normalized in seen:
                    old_canonical, old_file = seen[normalized]
                    raise ConfigError(f"{filename} 存在重复别名 {alias!r}（已在 {old_file}:{old_canonical} 使用）；请保留一个归属。")
                seen[normalized] = (str(canonical), filename)


def load_project_config(config_dir: Path) -> ProjectConfig:
    config_dir = Path(config_dir)
    payloads = {name: _load_json(config_dir / name) for name in JSON_FILES}
    _assert_unique_aliases(payloads)
    field_order = tuple(payloads["field_mapping.json"].get("field_order", ()))
    if field_order[:len(STANDARD_COLUMNS)] != STANDARD_COLUMNS:
        raise ConfigError("field_mapping.json 的 field_order 必须以 STANDARD_COLUMNS 原顺序开头；请修正字段顺序。")
    unit_path = config_dir / "sample_unit_prices.csv"
    if not unit_path.is_file():
        raise ConfigError("缺少 sample_unit_prices.csv；请添加教学单价表。")
    prices = pd.read_csv(unit_path)
    required = ["category", "material", "unit", "unit_price"]
    missing = [column for column in required if column not in prices.columns]
    if missing:
        raise ConfigError(f"sample_unit_prices.csv 缺少列 {', '.join(missing)}；请使用固定表头。")
    if list(prices.columns) != required:
        raise ConfigError("sample_unit_prices.csv 列顺序必须为 category,material,unit,unit_price；请调整表头。")
    prices["unit_price"] = pd.to_numeric(prices["unit_price"], errors="coerce")
    if prices["unit_price"].isna().any() or (prices["unit_price"] <= 0).any():
        raise ConfigError("sample_unit_prices.csv 的 unit_price 必须是正数；请删除空值、文字和零/负数。")
    keys = prices[["category", "material", "unit"]].astype(str).apply(tuple, axis=1)
    if keys.duplicated().any():
        raise ConfigError("sample_unit_prices.csv 含重复 category/material/unit；请合并重复价格行。")
    return ProjectConfig(
        config_version=CONFIG_VERSION,
        field_mapping=MappingProxyType(payloads["field_mapping.json"]),
        category_mapping=MappingProxyType(payloads["category_mapping.json"]),
        level_mapping=MappingProxyType(payloads["level_mapping.json"]),
        material_mapping=MappingProxyType(payloads["material_mapping.json"]),
        naming_rules=MappingProxyType(payloads["naming_rules.json"]),
        quality_rules=MappingProxyType(payloads["quality_rules.json"]),
        unit_prices=prices.copy(deep=True),
    )
```

按下列完整 JSON 结构创建配置。别名不得跨 canonical 重复（大小写折叠后也不得重复）；loader 还必须拒绝每个 JSON 的未知顶层键：

`configs/field_mapping.json`：

```json
{
  "config_version": "2.0",
  "aliases": {
    "element_id": ["构件ID", "Element ID", "element_id"],
    "guid": ["全局唯一标识", "GUID", "guid"],
    "level": ["楼层", "Level", "level"],
    "category": ["类别", "Category", "category"],
    "element_name": ["族名称", "Element Name", "element_name"],
    "type_name": ["类型", "Type Name", "type_name"],
    "length_m": ["长度", "Length", "length_m"],
    "area_m2": ["面积", "Area", "area_m2"],
    "volume_m3": ["体积", "Volume", "volume_m3"],
    "quantity": ["数量", "Quantity", "quantity"],
    "unit": ["单位", "Unit", "unit"],
    "material": ["材料", "Material", "material"]
  },
  "field_order": [
    "element_id", "guid", "source", "ifc_class", "category", "element_name",
    "type_name", "level", "material", "length_m", "area_m2", "volume_m3",
    "quantity", "unit", "unit_price", "total_cost", "quantity_source", "quality_status",
    "raw_unit", "raw_row_number", "source_file", "exception_tags"
  ]
}
```

`configs/category_mapping.json`：

```json
{
  "config_version": "2.0",
  "canonical_categories": ["Beam", "Column", "Slab", "Wall", "Door", "Window"],
  "ifc_class_to_category": {
    "IfcBeam": "Beam", "IfcColumn": "Column", "IfcSlab": "Slab",
    "IfcWall": "Wall", "IfcDoor": "Door", "IfcWindow": "Window"
  },
  "aliases": {
    "Beam": ["IfcBeam", "梁", "Beam"],
    "Column": ["IfcColumn", "柱", "Column"],
    "Slab": ["IfcSlab", "板", "Slab"],
    "Wall": ["IfcWall", "墙", "Wall"],
    "Door": ["IfcDoor", "门", "Door"],
    "Window": ["IfcWindow", "窗", "Window"]
  }
}
```

`configs/level_mapping.json`：

```json
{
  "config_version": "2.0",
  "canonical_levels": ["一层", "二层", "三层"],
  "aliases": {
    "一层": ["一层", "Level 1", "1F", "First Floor"],
    "二层": ["二层", "Level 2", "2F", "Second Floor"],
    "三层": ["三层", "Level 3", "3F", "Third Floor"]
  }
}
```

`configs/material_mapping.json`：

```json
{
  "config_version": "2.0",
  "canonical_materials": ["混凝土", "钢材", "木材", "玻璃", "铝合金"],
  "aliases": {
    "混凝土": ["混凝土", "Concrete"],
    "钢材": ["钢材", "Steel"],
    "木材": ["木材", "Wood"],
    "玻璃": ["玻璃", "Glass"],
    "铝合金": ["铝合金", "Aluminum"]
  }
}
```

`configs/naming_rules.json`：

```json
{
  "config_version": "2.0",
  "allowed_patterns": {
    "IfcBeam": "^梁-[A-Z]{2}-\\d{3}$",
    "IfcColumn": "^柱-[A-Z]{2}-\\d{3}$",
    "IfcSlab": "^板-[A-Z]{2}-\\d{3}$",
    "IfcWall": "^墙-[A-Z]{2}-\\d{3}$",
    "IfcDoor": "^门-[A-Z]{2}-\\d{3}$",
    "IfcWindow": "^窗-[A-Z]{2}-\\d{3}$"
  },
  "invalid_name_examples": ["INVALID", "未命名", "???"]
}
```

`configs/quality_rules.json`：

```json
{
  "config_version": "2.0",
  "rules": [
    {"id": "missing_element_name", "severity": "Error"},
    {"id": "missing_type_name", "severity": "Error"},
    {"id": "missing_material", "severity": "Warning"},
    {"id": "missing_level", "severity": "Warning"},
    {"id": "missing_guid", "severity": "Error"},
    {"id": "duplicate_element_id", "severity": "Warning"},
    {"id": "zero_quantity", "severity": "Warning"},
    {"id": "negative_quantity", "severity": "Error"},
    {"id": "unknown_unit", "severity": "Error"},
    {"id": "invalid_name", "severity": "Warning"},
    {"id": "missing_section_size", "severity": "Warning"},
    {"id": "outlier_dimension", "severity": "Warning"},
    {"id": "duplicate_guid", "severity": "Error"},
    {"id": "unmatched_unit_price", "severity": "Warning"}
  ]
}
```

`configs/sample_unit_prices.csv` 的完整表头和最小教学价格表：

```csv
category,material,unit,unit_price
Beam,混凝土,m³,520
Column,混凝土,m³,560
Slab,混凝土,m³,480
Wall,混凝土,m³,430
Door,木材,樘,860
Window,玻璃,樘,720
```

为让生成器可演示“单价无法匹配”两行，生成器使用 `material=未知材料`（不新增价格行）并保留 `unit_price` 空值；不要把未知价格写成 0。

占位目录只创建空 `.gitkeep`，不生成报告内容。`docs/data_dictionary.md` 逐列复制标准字段表（类型/可空/单位/枚举/追溯语义）；`docs/technical_route.md` 明确路线 A、配置到生成器的单向依赖、IfcOpenShell 可选且延迟到后续、当前未实现模块；`assets/README.md` 明确只放经授权的教学截图/图标，禁止真实项目或个人信息。

- [ ] **Step 4: Run test to verify it passes**

运行：

```powershell
python -m pytest tests/test_config_loader.py -q
```

预期：所有配置结构测试 `PASS`，并显示 `6 passed`（以实际测试数量为准，不在提交说明中虚构耗时或覆盖率）。

- [ ] **Step 5: Commit**

```powershell
git add src/config_loader.py configs data/raw/.gitkeep data/processed/.gitkeep outputs/excel/.gitkeep outputs/charts/.gitkeep outputs/reports/.gitkeep docs/data_dictionary.md docs/technical_route.md assets/README.md tests/test_config_loader.py
git commit -m "feat: add versioned mappings and foundation documentation"
```

提交前运行 `git diff --cached --check`，确认没有绝对路径和意外生成物。

---

### Task 3: 固定种子样例生成器、240 行明细与人工复核样例

**Files:**
- Create: `scripts/generate_sample_data.py`
- Create: `data/sample/sample_elements.csv`
- Create: `data/sample/sample_manual_validation.csv`
- Create: `data/sample/README.md`
- Test: `tests/test_sample_data.py`

**Interfaces:**
- Consumes: `ProjectConfig` from `load_project_config(config_dir: Path) -> ProjectConfig` and `SampleDataSpec`/`STANDARD_COLUMNS` from `src.schema`.
- Produces: `generate_sample_data(output_dir: Path, config_dir: Path, seed: int = 20260804, rows: int = 240) -> SampleGenerationResult` with deterministic paths, hash and exception counts. CLI defaults resolve `configs/` and `data/sample/` relative to repository root.

- [ ] **Step 1: Write the failing test**

创建 `tests/test_sample_data.py`，测试必须读取生成的 CSV，而不是相信日志：

```python
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_sample_data import generate_sample_data
from src.schema import STANDARD_COLUMNS


@pytest.fixture()
def generated_sample(tmp_path: Path):
    config_dir = Path(__file__).parents[1] / "configs"
    return generate_sample_data(tmp_path / "sample", config_dir)


def test_seeded_generation_is_240_rows_and_reproducible(tmp_path: Path):
    config_dir = Path(__file__).parents[1] / "configs"
    first = generate_sample_data(tmp_path / "one", config_dir)
    second = generate_sample_data(tmp_path / "two", config_dir)
    first_bytes = first.elements_path.read_bytes()
    second_bytes = second.elements_path.read_bytes()
    assert first.rows == second.rows == 240
    assert sha256(first_bytes).hexdigest() == sha256(second_bytes).hexdigest()
    assert first.sha256 == sha256(first_bytes).hexdigest()


def test_sample_covers_three_levels_and_six_ifc_classes(generated_sample):
    frame = pd.read_csv(generated_sample.elements_path)
    assert list(frame.columns) == list(STANDARD_COLUMNS) + [
        "raw_unit", "raw_row_number", "source_file", "exception_tags",
    ]
    assert set(frame["level"].dropna()) == {"一层", "二层", "三层"}
    assert set(frame["ifc_class"]) == {
        "IfcBeam", "IfcColumn", "IfcSlab", "IfcWall", "IfcDoor", "IfcWindow",
    }


def test_sample_has_exact_exception_counts(generated_sample):
    frame = pd.read_csv(generated_sample.elements_path, keep_default_na=False)
    valid_units = {"m", "m²", "m³", "个", "樘"}
    exception_rows = {
        "missing_material": set(frame.loc[frame["material"].eq(""), "raw_row_number"]),
        "missing_level": set(frame.loc[frame["level"].eq(""), "raw_row_number"]),
        "duplicate_guid": set(frame.loc[frame["guid"].duplicated(keep=False), "raw_row_number"]),
        "zero_volume": set(frame.loc[pd.to_numeric(frame["volume_m3"]).eq(0), "raw_row_number"]),
        "invalid_name": set(frame.loc[frame["element_name"].eq("INVALID"), "raw_row_number"]),
        "invalid_unit": set(frame.loc[~frame["unit"].isin(valid_units), "raw_row_number"]),
        "unmatched_unit_price": set(frame.loc[frame["material"].eq("未知材料"), "raw_row_number"]),
    }
    assert {name: len(rows) for name, rows in exception_rows.items()} == {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid": 4,
        "zero_volume": 4,
        "invalid_name": 3,
        "invalid_unit": 2,
        "unmatched_unit_price": 2,
    }
    from itertools import combinations
    for left, right in combinations(exception_rows.values(), 2):
        assert left.isdisjoint(right)
    duplicate = frame.loc[frame["guid"].duplicated(keep=False), "guid"]
    assert duplicate.nunique() == 2
    assert sorted(duplicate.value_counts().tolist()) == [2, 2]
    assert frame.loc[frame["material"].eq("未知材料"), "unit_price"].eq("").all()


def test_manual_validation_contains_disclaimer_and_sample_rows(generated_sample):
    manual = pd.read_csv(generated_sample.manual_validation_path)
    assert len(manual) >= 12
    assert set(manual["data_status"]) == {"程序演示数据"}
    assert manual["disclaimer"].eq("本项目单价为教学示例数据，不用于正式工程造价。").all()
    assert {"guid", "auto_quantity", "manual_quantity", "review_date", "data_status", "disclaimer"} <= set(manual.columns)
```

预期此时 `FAIL`，因为生成器、输出 CSV 和测试目标均不存在。

- [ ] **Step 2: Run test to verify it fails**

运行：

```powershell
python -m pytest tests/test_sample_data.py -q
```

预期：`FAIL`，出现 `ModuleNotFoundError` 或 `FileNotFoundError`；不能以手工创建未验证 CSV 代替生成器。

- [ ] **Step 3: Write minimal implementation**

创建 `scripts/generate_sample_data.py`，下列代码是完整可执行的核心实现（可将 CLI 帮助文字补充到同一文件，但不得改变签名）：

```python
from __future__ import annotations

import argparse
import hashlib
import logging
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_loader import ProjectConfig, load_project_config
from src.schema import STANDARD_COLUMNS, SampleDataSpec

LOGGER = logging.getLogger(__name__)
DISCLAIMER = "本项目单价为教学示例数据，不用于正式工程造价。"


@dataclass(frozen=True)
class SampleGenerationResult:
    elements_path: Path
    manual_validation_path: Path
    rows: int
    seed: int
    sha256: str
    exception_counts: dict[str, int]


def _base_rows(spec: SampleDataSpec, config: ProjectConfig) -> pd.DataFrame:
    rng = random.Random(spec.seed)
    classes = [spec.ifc_classes[index % len(spec.ifc_classes)] for index in range(spec.rows)]
    levels = [spec.levels[index % len(spec.levels)] for index in range(spec.rows)]
    field_order = tuple(config.field_mapping["field_order"])
    rows: list[dict[str, Any]] = []
    for index in range(spec.rows):
        ifc_class = classes[index]
        level = levels[index]
        category = config.category_mapping["ifc_class_to_category"][ifc_class]
        unit = "樘" if ifc_class in {"IfcDoor", "IfcWindow"} else "m³"
        price_candidates = config.unit_prices.query("category == @category and unit == @unit")
        if price_candidates.empty:
            raise ValueError(f"No baseline teaching price for {category}/{unit}; add it to sample_unit_prices.csv.")
        material = str(price_candidates.iloc[0]["material"])
        name_prefix = config.naming_rules["allowed_patterns"][ifc_class].split("-", 1)[0].lstrip("^")
        volume = round(rng.uniform(0.2, 8.0), 3)
        quantity = 1.0 if unit == "樘" else volume
        rows.append({
            "element_id": f"E-{index + 1:04d}",
            "guid": f"GUID-{index + 1:04d}",
            "source": "CSV",
            "ifc_class": ifc_class,
            "category": category,
            "element_name": f"{name_prefix}-AA-{index + 1:03d}",
            "type_name": f"{ifc_class}-Standard",
            "level": level,
            "material": material,
            "length_m": round(rng.uniform(1.0, 12.0), 3),
            "area_m2": round(rng.uniform(0.5, 30.0), 3),
            "volume_m3": volume,
            "quantity": quantity,
            "unit": unit,
            "unit_price": float("nan"),
            "total_cost": float("nan"),
            "quantity_source": "CSV Schedule",
            "quality_status": "Pass",
            "raw_unit": unit,
            "raw_row_number": index + 2,
            "source_file": "data/sample/sample_elements.csv",
            "exception_tags": "",
        })
    frame = pd.DataFrame(rows, columns=list(field_order))
    return frame


def _mark(frame: pd.DataFrame, indices: list[int], tag: str) -> None:
    for index in indices:
        existing = frame.at[index, "exception_tags"]
        frame.at[index, "exception_tags"] = tag if not existing else f"{existing}|{tag}"


def _inject_exceptions(frame: pd.DataFrame, spec: SampleDataSpec) -> None:
    _mark(frame, [0, 1, 2, 3, 4], "missing_material")
    frame.loc[[0, 1, 2, 3, 4], "material"] = ""
    _mark(frame, [5, 6, 7], "missing_level")
    frame.loc[[5, 6, 7], "level"] = ""
    duplicate_groups = ((8, 9), (10, 11))
    for first, second in duplicate_groups:
        frame.at[second, "guid"] = frame.at[first, "guid"]
        _mark(frame, [first, second], "duplicate_guid")
    _mark(frame, [12, 13, 14, 15], "zero_volume")
    frame.loc[[12, 13, 14, 15], "volume_m3"] = 0.0
    _mark(frame, [16, 17, 18], "invalid_name")
    frame.loc[[16, 17, 18], "element_name"] = "INVALID"
    _mark(frame, [19, 20], "invalid_unit")
    frame.loc[[19, 20], "unit"] = "unknown"
    frame.loc[[19, 20], "raw_unit"] = "unknown"
    _mark(frame, [21, 22], "unmatched_unit_price")
    frame.loc[[21, 22], "material"] = "未知材料"


def _fill_prices(frame: pd.DataFrame, config: ProjectConfig) -> None:
    price_rows = config.unit_prices.set_index(["category", "material", "unit"])["unit_price"]
    for index, row in frame.iterrows():
        key = (row["category"], row["material"], row["unit"])
        if key in price_rows.index:
            frame.at[index, "unit_price"] = float(price_rows.loc[key])
            frame.at[index, "total_cost"] = float(row["quantity"]) * float(price_rows.loc[key])


def generate_sample_data(output_dir: Path, config_dir: Path, seed: int = 20260804, rows: int = 240) -> SampleGenerationResult:
    spec = SampleDataSpec(seed=seed, rows=rows)
    if spec.seed != 20260804 or spec.rows != 240:
        raise ValueError("Phase 2 sample data requires seed=20260804 and rows=240.")
    config = load_project_config(Path(config_dir))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = _base_rows(spec, config)
    _inject_exceptions(frame, spec)
    _fill_prices(frame, config)
    elements_path = output_dir / "sample_elements.csv"
    frame.to_csv(elements_path, index=False, encoding="utf-8-sig", lineterminator="\n")
    manual = frame.iloc[::20][["guid", "ifc_class", "level", "quantity"]].copy()
    manual = manual.rename(columns={"quantity": "auto_quantity"})
    manual["manual_quantity"] = manual["auto_quantity"].round(2)
    manual["review_date"] = "2026-08-04"
    manual["data_status"] = "程序演示数据"
    manual["disclaimer"] = DISCLAIMER
    manual_path = output_dir / "sample_manual_validation.csv"
    manual.to_csv(manual_path, index=False, encoding="utf-8-sig", lineterminator="\n")
    digest = hashlib.sha256(elements_path.read_bytes()).hexdigest()
    tags = frame["exception_tags"].str.split("|").explode()
    counts = tags[tags.ne("")].value_counts().to_dict()
    counts["duplicate_guid_groups"] = 2
    return SampleGenerationResult(elements_path, manual_path, len(frame), spec.seed, digest, counts)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成固定种子程序演示数据")
    parser.add_argument("--output-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--rows", type=int, default=240)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = generate_sample_data(args.output_dir, args.config_dir, args.seed, args.rows)
    LOGGER.info("generated %s rows at %s (sha256=%s)", result.rows, result.elements_path, result.sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

实现者必须在 `scripts/` 增加空的 `__init__.py`，使 pytest 的 `from scripts.generate_sample_data` 在 Windows 上稳定导入；该文件属于生成器交付物。随机数只使用上面代码中的标准库 `random.Random(seed)`，缺失数值只使用 `float("nan")`；不得直接导入 NumPy，也不得把 pandas 的传递依赖当作项目直接依赖。

生成器必须用配置单价填充可匹配行，未知材料行的 `unit_price`/`total_cost` 保持空值；`exception_tags` 只用于测试追踪，不替代后续质量规则。人工复核样例至少 12 行，`auto_quantity` 与 `manual_quantity` 保留，绝不覆盖自动值。

- [ ] **Step 4: Run test to verify it passes**

运行：

```powershell
python -m pytest tests/test_sample_data.py -q
```

预期：固定哈希、行数/列顺序、覆盖范围、七类异常和人工复核免责声明测试全部 `PASS`；测试从 CSV 读回验证，而不是只检查 `SampleGenerationResult`。

- [ ] **Step 5: Commit**

```powershell
git add scripts/__init__.py scripts/generate_sample_data.py data/sample/sample_elements.csv data/sample/sample_manual_validation.csv data/sample/README.md tests/test_sample_data.py
git commit -m "feat: add deterministic 240-row teaching sample"
```

提交前确认 CSV 使用 UTF-8-SIG、固定字段顺序、无绝对路径，且 `python scripts/generate_sample_data.py` 可从仓库根目录重复生成相同哈希。

---

### Task 4: 阶段2整体验证、文档收口与交付检查

**Files:**
- Modify: `README.md`
- Modify: `data/sample/README.md`
- Modify: `docs/data_dictionary.md`
- Modify: `docs/technical_route.md`
- Modify: `assets/README.md`
- Test: `tests/test_config_loader.py`
- Test: `tests/test_sample_data.py`

**Interfaces:**
- Consumes the exact `load_project_config` and `generate_sample_data` contracts from Tasks 1–3.
- Produces a checked-in sample plus a documented, repeatable validation sequence. No new business module is introduced.

- [ ] **Step 1: Write the failing test**

追加“文档/路径/边界”测试，防止计划执行时越界：

```python
def test_phase_two_outputs_and_docs_exist():
    root = Path(__file__).parents[1]
    required = [
        root / "README.md", root / "requirements.txt", root / "requirements-ifc.txt",
        root / "pyproject.toml", root / "src" / "schema.py", root / "src" / "config_loader.py",
        root / "data" / "sample" / "README.md", root / "docs" / "data_dictionary.md",
        root / "docs" / "technical_route.md", root / "assets" / "README.md",
        root / "data" / "raw" / ".gitkeep", root / "data" / "processed" / ".gitkeep",
        root / "outputs" / "excel" / ".gitkeep", root / "outputs" / "charts" / ".gitkeep",
        root / "outputs" / "reports" / ".gitkeep",
    ]
    assert all(path.is_file() for path in required)
    forbidden = [
        root / "src" / "csv_reader.py", root / "src" / "pipeline.py",
        root / "src" / "ifc_reader.py", root / "app" / "streamlit_app.py",
    ]
    assert all(not path.exists() for path in forbidden)


def test_sample_document_contains_disclaimer_and_exception_counts():
    text = (Path(__file__).parents[1] / "data" / "sample" / "README.md").read_text(encoding="utf-8")
    assert "程序演示数据" in text
    assert "缺失材料 5 条" in text
    assert "缺失楼层 3 条" in text
    assert "重复 GUID 2 组" in text
    assert "体积为零 4 条" in text
    assert "名称不符合规则 3 条" in text
    assert "单位异常 2 条" in text
    assert "单价无法匹配 2 条" in text
    assert "本项目单价为教学示例数据，不用于正式工程造价。" in text
```

预期：文档、占位目录或禁止越界模块缺失时 `FAIL`。

- [ ] **Step 2: Run test to verify it fails**

运行：

```powershell
python -m pytest tests/test_config_loader.py tests/test_sample_data.py -q
```

预期：新增文档/边界测试至少一项 `FAIL`，其失败信息明确指出缺失路径或免责声明文字。

- [ ] **Step 3: Write minimal implementation**

将 `README.md` 收口为以下可执行内容：

````markdown
# BIM 工程量基础工程（阶段2）

支持 Python 3.10/3.11、Windows 10/11。安装：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

生成固定种子样例：

```powershell
.venv\Scripts\python.exe scripts/generate_sample_data.py
```

运行阶段2测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

样例是程序演示数据，固定种子 `20260804`、240 行、三层、六类和预置异常仅用于教学测试；本项目单价为教学示例数据，不用于正式工程造价。

本阶段只提供 schema、配置加载器和样例生成器；CSV reader、工程量/造价 pipeline、Streamlit 和 IFC reader 在后续阶段实现。IfcOpenShell 不在基础 requirements 中；仅在选择 IFC 阶段时安装 `requirements-ifc.txt`。
````

`data/sample/README.md` 必须列出字段来源、生成命令、七类异常精确数量、人工复核列含义、固定免责声明和“不得将样例当真实工程数据”的提示。`docs/data_dictionary.md` 必须逐列列出类型/可空/单位/枚举/原始追溯；`docs/technical_route.md` 必须画出 `configs → config_loader → schema/generator → sample CSV` 的路线并列出后续边界；`assets/README.md` 必须说明仅接受授权教学素材。

- [ ] **Step 4: Run test to verify it passes**

从仓库根目录依次运行完整验证命令：

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_config_loader.py tests/test_sample_data.py -q
python scripts/generate_sample_data.py --config-dir configs --output-dir data/sample
python -m pytest -q
python -c "from pathlib import Path; import pandas as pd; p=Path('data/sample/sample_elements.csv'); f=pd.read_csv(p); print(f.shape, f['level'].dropna().nunique(), f['ifc_class'].nunique())"
```

预期结果：依赖安装成功；两个定向测试与全套阶段2测试均 `PASS`；生成器退出码 `0`，输出 `data/sample/sample_elements.csv` 和 `data/sample/sample_manual_validation.csv`；最后一条打印 `(240, 22) 3 6`（如果实现保留 22 列；若字段扩展，必须在测试和文档同步精确列数，不得静默变化）。同时确认 `sha256` 连续两次一致、无禁止模块文件、目录占位存在、文档包含完整免责声明。

- [ ] **Step 5: Commit**

```powershell
git add README.md data/sample/README.md docs/data_dictionary.md docs/technical_route.md assets/README.md tests/test_config_loader.py tests/test_sample_data.py
git commit -m "docs: close phase 2 foundation validation"
```

提交前执行：

```powershell
git diff --check
git status --short
```

预期只看到阶段2列出的文件；不得提交 `.venv`、运行时报告、绝对路径或 IFC 二进制。

---

## 阶段2完整验证命令与预期结果

以下命令必须按顺序从 `bim-quantity-python/` 仓库根目录运行；PowerShell 和 Windows CMD 均可用相同的相对路径：

```powershell
python --version
python -m pip install -r requirements.txt
python -m pytest tests/test_config_loader.py -q
python -m pytest tests/test_sample_data.py -q
python scripts/generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data/sample
python -m pytest -q
python -c "from pathlib import Path; import hashlib, pandas as pd; p=Path('data/sample/sample_elements.csv'); m=Path('data/sample/sample_manual_validation.csv'); f=pd.read_csv(p); print('rows=', len(f)); print('levels=', sorted(f['level'].dropna().unique())); print('classes=', sorted(f['ifc_class'].unique())); print('sha256=', hashlib.sha256(p.read_bytes()).hexdigest()); print('manual_rows=', len(pd.read_csv(m)))"
git diff --check
git status --short
```

预期：

1. `python --version` 显示 `3.10.x` 或 `3.11.x`；不接受其他主版本作为阶段2验收环境。
2. 基础依赖安装成功；不需要安装 `requirements-ifc.txt`，且导入 `src` 不尝试导入 IfcOpenShell。
3. `test_config_loader.py` 与 `test_sample_data.py` 定向测试及 `pytest -q` 全套测试均显示 `passed`、退出码 0。
4. 生成器显示 240 行写入日志并退出码 0；`sample_elements.csv` 行数为 240，非空楼层集合恰为`一层`、`二层`、`三层`，IFC 类集合恰为六类；人工复核 CSV 至少 12 行，含“程序演示数据”和完整免责声明。
5. 连续两次生成的 `sha256` 完全一致；字段顺序与 `STANDARD_COLUMNS + raw_unit/raw_row_number/source_file/exception_tags` 一致；七类异常计数分别为 5、3、2 组、4、3、2、2。
6. `git diff --check` 无输出；`git status --short` 仅显示阶段2预期的新增/修改文件，不出现 `src/csv_reader.py`、pipeline、Streamlit、IFC reader 或其它运行产物。

## 交付物评审切分

1. **交付物 A — 契约骨架：** Task 1 的元数据、依赖、`src/__init__.py`、`src/schema.py` 及其失败→通过测试；评审可单独检查导入、版本和枚举。
2. **交付物 B — 配置与文档：** Task 2 的 `src/config_loader.py`、七个显式配置、占位目录、数据字典、技术路线和素材规则；评审可单独运行配置加载测试并查验 `config_version`、未知键拒绝和映射无重复。
3. **交付物 C — 可复现实例：** Task 3 的生成器、240 行样例、人工复核样例、样例 README 与生成测试；评审可重复运行并比较哈希与异常数量。
4. **交付物 D — 阶段2验收收口：** Task 4 的基础 README、文档边界测试、全套命令与工作区检查；评审可确认免责声明、Windows 相对路径和未越界到 CSV reader/pipeline/Streamlit/IFC reader。

## 自审清单

- [x] 规格第 10 节的每个路径都在文件地图和至少一个任务中出现；未列模块明确禁止。
- [x] 所有实现接口均使用 `Path`、`ProjectConfig`、`SampleGenerationResult`，任务间签名一致。
- [x] 标准字段、枚举、三层六类、seed `20260804`、240 行及七类异常数量在全局约束、测试和文档中一致。
- [x] 明确 Python 3.10/3.11、Windows 10/11、IfcOpenShell 仅可选 requirements-ifc、免责声明、无绝对路径、初学者可读错误。
- [x] 每个任务遵循先失败测试→确认失败→最小实现→确认通过→提交，代码步骤展示完整关键代码，不使用占位表达。
- [x] 计划只覆盖基础工程和样例；没有 CSV reader、pipeline、Streamlit 或 IFC reader 的实现步骤。

**Execution method already selected:** Subagent-Driven。用户已指定使用 `luna-worker`、可控放权和并行迭代；执行时只并行文件所有权不重叠的交付物，并在每个交付物后完成规格与质量复核。
