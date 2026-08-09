# 阶段 3.5 IFC reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不影响 CSV 主流程的前提下，交付一个延迟加载 IfcOpenShell、输出既有标准字段并保留来源追溯的六类 IFC 薄适配器。

**Architecture:** `src/ifc_reader.py` 是唯一 IFC 边界，内部延迟导入 IfcOpenShell，读取结果返回不可变结果对象和标准 DataFrame；配置、schema、quantity_calculator、pipeline 和 Streamlit 不复制 IFC 解析逻辑。可选 CLI 只负责参数、写出和中文错误提示。

**Tech Stack:** Python 3.10/3.11、pandas、dataclasses、pathlib、pytest、IfcOpenShell（仅 `requirements-ifc.txt` 可选）。

## Global Constraints

- IFC 只支持 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类实体。
- `ifcopenshell` 必须延迟导入；未安装时 CSV、Pipeline、Streamlit 和 `import src` 仍然可运行。
- 输出必须包含 `src.schema.STANDARD_COLUMNS`，并按 `ProjectConfig.field_mapping["field_order"]` 排序；额外追溯列为 `raw_unit`、`raw_row_number`、`source_file`。
- `source` 固定为 `IFC`；`source_file` 只保留 basename；`raw_row_number` 为稳定的实体遍历序号，从 1 开始。
- 缺失属性保持缺失，不伪造 element_id/guid，不把未知单位或负数当作有效 Base Quantity。
- 不实现自定义 IFC 解析器、复杂几何重建、钢筋/幕墙/机电/碰撞或 IFC 写回。
- 所有错误信息使用中文修复提示，不暴露临时路径或完整堆栈。
- 所有结果和金额仅为程序演示数据；本项目单价为教学示例数据，不用于正式工程造价。

---

### Task 1: Reader boundary and lazy dependency contract

**Files:**
- Create: `src/ifc_reader.py`
- Test: `tests/test_ifc_reader.py`
- Modify: `tests/test_config_loader.py` only if its stale forbidden-module list blocks the new reader

**Interfaces:**
- Produces `IfcReaderUnavailable`, `IfcReaderError`, `IfcReadResult(frame: pandas.DataFrame, diagnostics: tuple[str, ...])` and `read_ifc(path: Path, config: ProjectConfig) -> IfcReadResult`.
- `read_ifc` validates a regular file, imports `ifcopenshell` inside the function, opens the file, and closes/releases the model in a `finally` block when the fake or real API supports it.

- [ ] **Step 1: Write the failing test**

Add tests that import `src.ifc_reader` without importing `ifcopenshell`, assert a missing dependency raises `IfcReaderUnavailable` with `requirements-ifc.txt` in the message, assert a missing path raises `IfcReaderError` with a Chinese repair hint, and assert `IfcReadResult` is frozen and contains an empty DataFrame only when the fake model has no supported entities.

- [ ] **Step 2: Run the RED test**

```powershell
.venv\python.exe -m pytest tests/test_ifc_reader.py -q --basetemp=.pytest_cache\stage35-ifc-boundary-red
```

Expected: collection or import failures because `src.ifc_reader` does not yet exist; no test should require a real IfcOpenShell installation.

- [ ] **Step 3: Implement the minimal boundary**

Create the two exception classes and frozen result dataclass. Use `importlib.import_module("ifcopenshell")` inside `read_ifc`, catch `ModuleNotFoundError` only for the optional dependency, and convert path/open errors to `IfcReaderError`. Keep the reader output empty but correctly shaped until Task 2 adds entity extraction.

- [ ] **Step 4: Run GREEN and import regression**

```powershell
.venv\python.exe -m pytest tests/test_ifc_reader.py -q --basetemp=.pytest_cache\stage35-ifc-boundary-green
.venv\python.exe -c "import src, sys; assert 'ifcopenshell' not in sys.modules"
```

- [ ] **Step 5: Commit**

```powershell
git add src/ifc_reader.py tests/test_ifc_reader.py tests/test_config_loader.py
git commit -m "feat: add optional ifc reader boundary"
```

### Task 2: Six-class entity extraction and fake IFC fixtures

**Files:**
- Modify: `src/ifc_reader.py`
- Modify: `tests/test_ifc_reader.py`
- Create: `tests/fixtures/fake_ifc.py`

**Interfaces:**
- `read_ifc` emits one row per supported entity with exact standard field order plus trace columns.
- Helpers are private and operate on the fake/real IfcOpenShell object model; no generic parser framework is introduced.

- [ ] **Step 1: Extend tests first**

Create a fake module injected through `sys.modules["ifcopenshell"]` whose `open()` returns six supported entities plus one unknown entity. Test exact class coverage, `source == "IFC"`, basename trace, deterministic row numbers, GUID preservation, explicit category mapping, level/material extraction, finite non-negative Base Quantities, missing element IDs, unknown-class diagnostics, and continuation after one malformed entity.

- [ ] **Step 2: Run RED**

```powershell
.venv\python.exe -m pytest tests/test_ifc_reader.py -q --basetemp=.pytest_cache\stage35-ifc-extract-red
```

Expected: the boundary tests pass but extraction assertions fail because rows are still empty or incomplete.

- [ ] **Step 3: Implement explicit extraction**

Implement only the six class branches. Read `GlobalId`, `Name`, type/object name, spatial containment level, material association, and known quantity attributes through explicit candidate keys. Normalize values with finite/non-negative checks, map classes via `ProjectConfig`, preserve missing values as `pd.NA`, append diagnostics for unknown classes, multiple materials, bad quantities and missing GUIDs, then reindex to configured field order.

- [ ] **Step 4: Run focused and full GREEN**

```powershell
.venv\python.exe -m pytest tests/test_ifc_reader.py -q --basetemp=.pytest_cache\stage35-ifc-extract-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage35-ifc-extract-full
.venv\python.exe -m pip check
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add src/ifc_reader.py tests/test_ifc_reader.py tests/fixtures/fake_ifc.py
git commit -m "feat: extract standard fields from ifc entities"
```

### Task 3: Optional IFC inspection CLI and documentation

**Files:**
- Create: `scripts/inspect_ifc.py`
- Create: `tests/test_inspect_ifc.py`
- Modify: `README.md`
- Modify: `requirements-ifc.txt` only if the existing optional dependency declaration is incomplete

**Interfaces:**
- CLI command: `python scripts/inspect_ifc.py --input model.ifc --config-dir configs --output-dir outputs/ifc`.
- Success writes `*_ifc_elements.csv` with UTF-8-SIG and `*_ifc_diagnostics.json`; exit `0` when no `Error` diagnostics, `2` when rows are written with recoverable diagnostics, and `1` for unavailable dependency, invalid input, configuration, or output failures.

- [ ] **Step 1: Write failing CLI tests**

Use monkeypatched fake IfcOpenShell and temporary directories to assert help text, basename-only output, UTF-8-SIG CSV, diagnostics JSON, exit-code mapping, and Chinese missing-dependency guidance. Add a real subprocess test only for `--help`; never require a binary IFC or installed IfcOpenShell in the base suite.

- [ ] **Step 2: Run RED**

```powershell
.venv\python.exe -m pytest tests/test_inspect_ifc.py -q --basetemp=.pytest_cache\stage35-ifc-cli-red
```

Expected: CLI module or script is missing.

- [ ] **Step 3: Implement the thin CLI**

Parse only the three documented paths, call `read_ifc`, write via pandas/JSON, print a Chinese summary, and map exceptions to the three exit codes. Do not add calculation, cleaning, pricing, or UI logic.

- [ ] **Step 4: Run complete validation**

```powershell
.venv\python.exe -m pytest tests/test_ifc_reader.py tests/test_inspect_ifc.py -q --basetemp=.pytest_cache\stage35-ifc-cli-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage35-full
.venv\python.exe -m pip check
git diff --check
```

Update README with the optional install and inspection commands, explicitly state that CSV remains the default and IFC support requires `requirements-ifc.txt`, then run the existing stage 3.3 CLI and Streamlit AppTest regression.

- [ ] **Step 5: Commit**

```powershell
git add scripts/inspect_ifc.py tests/test_inspect_ifc.py README.md requirements-ifc.txt
git commit -m "feat: add optional ifc inspection cli"
```

## Completion Gate

The stage is complete only when the reader and CLI have focused tests, the full suite is green, `pip check` is clean, `git diff --check` is clean, `import src` does not load IfcOpenShell, and the existing CSV/Streamlit/3.3 CLI paths still run without installing the optional dependency.
