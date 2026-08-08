# 阶段 3.2 工程量造价质量实施计划

> **For agentic workers:** 必须使用 `superpowers:subagent-driven-development` 按任务执行。每个任务都使用复选框跟踪，并在写生产代码前先观察测试失败。

**目标：** 在阶段 3.1 清洗结果上完成工程量来源判定、教学单价匹配、14 类质量检查和人工复核误差计算。

**架构：** 四个独立模块分别接收标准 DataFrame 和 `ProjectConfig`，返回不可变结果数据类；不复制字段映射、类别映射或单价表。阶段 3.2 不实现 Excel、图表、Streamlit、IFC 或完整报告导出。

**技术栈：** Python 3.10/3.11、pandas、dataclasses、pathlib、json、pytest；不新增运行时依赖，不导入 IfcOpenShell。

## 全局约束

- 标准字段必须保持 `src/schema.py` 的 18 个 `STANDARD_COLUMNS` 顺序。
- `quantity_source` 只能使用 `IFC BaseQuantity`、`Parameter Calculation`、`CSV Schedule`、`Missing`。
- `quality_status` 只能使用 `Pass`、`Warning`、`Error`。
- 所有问题行必须保留，缺失标识不得伪造，未知数值不得静默填 0。
- 单价必须来自 `configs/sample_unit_prices.csv`，且所有输出保留免责声明：`本项目单价为教学示例数据，不用于正式工程造价。`
- `missing_section_size` 与 `outlier_dimension` 没有可用截面配置时列入 `not_applicable_rules`，不伪造问题计数。
- 所有问题保留 `source_file` 文件名和 `raw_row_number`；不得写入绝对本机路径。
- 每项任务必须先写测试并观察预期 RED，再写最小实现；完成后运行专项测试、全量测试和 `git diff --check`。

## 文件地图

- 创建 `src/quantity_calculator.py`：工程量来源选择和六类特化公式。
- 创建 `src/cost_calculator.py`：配置单价匹配与总价计算。
- 创建 `src/quality_checker.py`：14 类质量规则和状态聚合。
- 创建 `src/validation.py`：人工复核关联、误差和分类型汇总。
- 创建 `tests/test_quantity_calculator.py`、`tests/test_cost_calculator.py`、`tests/test_quality_checker.py`、`tests/test_validation.py`。
- 修改 `README.md`：只补充阶段 3.2 的运行/接口说明，不宣称未经运行的指标。

---

### Task 1：工程量计算器

**文件：**

- 创建：`src/quantity_calculator.py`
- 测试：`tests/test_quantity_calculator.py`

**接口：**

```python
calculate_quantities(frame: pd.DataFrame, config: ProjectConfig) -> QuantityResult
```

`QuantityResult` 为 frozen dataclass，包含 `frame: pd.DataFrame` 与 `calculation_notes: tuple[str, ...]`。

- [ ] **步骤 1：写失败测试**

先写以下行为测试：已有合法 `quantity` 的行来源为 `CSV Schedule`；无数量但 Beam 有合法 `length_m` 时来源为 `Parameter Calculation` 且单位为 `m`；Column/Slab/Wall 使用 `volume_m3` 和 `m³`；Door/Window 使用可用数量和 `樘`；缺尺寸保持空值且来源为 `Missing`；负数不补算；输入 DataFrame 不被原地修改。

运行：

```powershell
.venv\python.exe -m pytest tests/test_quantity_calculator.py -q --basetemp=.pytest_cache\stage32-quantity-red
```

预期：因 `src.quantity_calculator` 不存在而 RED。

- [ ] **步骤 2：写最小实现**

复制输入后按类别执行显式公式。有限非负的已有 `quantity` 优先保留；来源已经是 `IFC BaseQuantity` 的有效值也必须保留。仅对 `Beam`、`Column`、`Slab`、`Wall`、`Door`、`Window` 执行设计中的特化公式；其余类别返回 `Missing`。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\python.exe -m pytest tests/test_quantity_calculator.py -q --basetemp=.pytest_cache\stage32-quantity-green
```

预期：专项测试全部通过。

- [ ] **步骤 4：提交**

```powershell
git add src/quantity_calculator.py tests/test_quantity_calculator.py
git commit -m "feat: add quantity calculator"
```

---

### Task 2：教学造价计算器

**文件：**

- 创建：`src/cost_calculator.py`
- 测试：`tests/test_cost_calculator.py`

**接口：**

```python
calculate_costs(frame: pd.DataFrame, config: ProjectConfig) -> CostResult
```

`CostResult` 为 frozen dataclass，包含 `frame: pd.DataFrame` 与 `unmatched_rows: tuple[int, ...]`。

- [ ] **步骤 1：写失败测试**

先写精确匹配 Beam/混凝土/`m³`、Door/木材/`樘`；写未知材料、未知单位、空工程量和缺价测试；确认不做模糊匹配、不把未匹配价格或总价填为 0；确认结果包含完整免责声明所需的常量。

运行：

```powershell
.venv\python.exe -m pytest tests/test_cost_calculator.py -q --basetemp=.pytest_cache\stage32-cost-red
```

预期：因 `src.cost_calculator` 不存在而 RED。

- [ ] **步骤 2：写最小实现**

从 `config.unit_prices` 精确查找 `category + material + unit`；只有配置明确存在类别+单位兜底记录时才使用第二级匹配。匹配成功且数量为有限非负数时计算 `total_cost`；否则单价和总价保留缺失，并记录 `raw_row_number`。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\python.exe -m pytest tests/test_cost_calculator.py -q --basetemp=.pytest_cache\stage32-cost-green
```

- [ ] **步骤 4：提交**

```powershell
git add src/cost_calculator.py tests/test_cost_calculator.py
git commit -m "feat: add teaching cost calculator"
```

---

### Task 3：14 类质量检查器

**文件：**

- 创建：`src/quality_checker.py`
- 测试：`tests/test_quality_checker.py`

**接口：**

```python
check_quality(frame: pd.DataFrame, config: ProjectConfig) -> QualityReport
```

- [ ] **步骤 1：写失败测试**

先构造最小 DataFrame，逐项覆盖 `quality_rules.json` 的 14 个 ID，验证每条问题含 `raw_row_number`、字段、规则 ID、严重程度、中文说明和建议；另测重复 GUID/ID 的分组、问题行保留、最高严重程度状态、两个未适用规则和稳定排序。

运行：

```powershell
.venv\python.exe -m pytest tests/test_quality_checker.py -q --basetemp=.pytest_cache\stage32-quality-red
```

预期：因 `src.quality_checker` 不存在而 RED。

- [ ] **步骤 2：写最小实现**

读取配置规则 ID 和严重程度；空值检查使用清洗后的标准字段；重复 ID/GUID 只对非空值分组；单位检查复用 `schema.UNITS`；名称检查复用 `naming_rules`；未适用规则写入 `not_applicable_rules`；以 `QualityIssue` 组装 `QualityReport`，不删除任何行。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\python.exe -m pytest tests/test_quality_checker.py -q --basetemp=.pytest_cache\stage32-quality-green
```

再运行固定样例，确认各规则的计数可回溯到 `raw_row_number`，但不把报告标签当作规则来源。

- [ ] **步骤 4：提交**

```powershell
git add src/quality_checker.py tests/test_quality_checker.py
git commit -m "feat: add quality checker"
```

---

### Task 4：人工复核验证与阶段回归

**文件：**

- 创建：`src/validation.py`
- 测试：`tests/test_validation.py`
- 修改：`README.md`

**接口：**

```python
validate_manual_results(
    calculated: pd.DataFrame,
    manual: pd.DataFrame,
) -> ValidationResult
```

`ValidationResult` 为 frozen dataclass，包含逐行 `details`、`summary_by_category` 和 `messages`。

- [ ] **步骤 1：写失败测试**

覆盖 GUID 关联、`absolute_error`、`relative_error_pct`、人工值为零时留空并提示、重复人工键、缺少匹配键、非法人工值和按类别汇总。使用 `data/sample/sample_manual_validation.csv` 验证正常样例可读取。

运行：

```powershell
.venv\python.exe -m pytest tests/test_validation.py -q --basetemp=.pytest_cache\stage32-validation-red
```

预期：因 `src.validation` 不存在而 RED。

- [ ] **步骤 2：写最小实现**

按 GUID、非空 element_id、raw_row_number 的顺序选择关联键；关联前检查人工键唯一；数值转换失败抛出带行号的 `ValidationError`；使用严格公式计算误差；人工值为零时相对误差为缺失并写入中文消息，不覆盖自动值。

- [ ] **步骤 3：验证 GREEN 与阶段回归**

```powershell
.venv\python.exe -m pytest tests/test_validation.py -q --basetemp=.pytest_cache\stage32-validation-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage32-full
.venv\python.exe -m pip check
```

运行现有清洗 CLI，确认阶段 3.1 输出仍可读，且 `git diff --check` 无错误。

- [ ] **步骤 4：更新中文文档并提交**

在 `README.md` 增加阶段 3.2 已交付模块、固定免责声明、测试命令和未实现边界；不得宣称未经实际运行的精度或工程适用性。

```powershell
git add src/validation.py tests/test_validation.py README.md
git commit -m "feat: add manual validation"
```

---

## 计划自审

- 四项任务覆盖设计文档中的工程量、造价、14 类质量检查和人工复核；Excel、图表、Streamlit、IFC 均未进入本阶段。
- 所有接口名称、质量规则 ID、来源枚举和错误公式与现有 schema/config 契约一致。
- 全文不含未完成占位词、绝对用户路径或模糊的后续步骤。
- 每个任务都有独立 RED、GREEN、全量回归和提交边界。
