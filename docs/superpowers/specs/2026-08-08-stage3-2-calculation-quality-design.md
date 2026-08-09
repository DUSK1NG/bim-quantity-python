# 阶段 3.2 工程量、造价与质量核心计算设计

## 1. 目标与边界

阶段 3.2 在阶段 3.1 的清洗 DataFrame 上增加可独立测试的工程量、造价、质量检查和人工复核模块。目标是让每一条记录的工程量来源、教学单价、总价和质量问题都能回溯到 `raw_row_number` 与 `source_file`。

本阶段只实现 CSV 主流程所需的核心计算，不实现 Excel、Plotly 图表、Streamlit、IFC 读取器、数据库或通用规则引擎。所有模块复用 `src/schema.py`、`src/config_loader.py`、`src/data_cleaner.py` 和 `src/quality_report.py` 的既有契约。

## 2. 方案选择

采用方案 A：四个局部模块共享标准 DataFrame，通过显式数据类传递结果。

```text
clean_elements
      ↓
quantity_calculator → cost_calculator
      ↓                    ↓
quality_checker  ← 计算结果表
      ↓
validation（可选人工复核表）
```

不在模块之间复制字段别名、类别、楼层、材料或单价映射；这些信息一律来自 `ProjectConfig`。模块不读取页面状态，也不修改输入 DataFrame 的原对象。

## 3. 模块接口

### 3.1 工程量计算

文件：`src/quantity_calculator.py`

```python
calculate_quantities(frame: pd.DataFrame, config: ProjectConfig) -> QuantityResult
```

`QuantityResult` 是 frozen dataclass，包含 `frame` 和 `calculation_notes`。输出保持全部输入行和标准字段顺序，并更新 `quantity`、`unit`、`quantity_source`。

来源优先级固定为：

1. 已有且为有限非负数的 CSV 工程量：`CSV Schedule`；
2. 可由类别和完整尺寸字段直接补算：`Parameter Calculation`；
3. 信息不足：`Missing`，工程量保持空值，不填零。

本阶段的特化公式如下：

| 规范类别 | 计算条件 | 工程量 | 单位 |
|---|---|---|---|
| Beam | `length_m` 有效 | `length_m` | `m` |
| Column、Slab、Wall | `volume_m3` 有效 | `volume_m3` | `m³` |
| Door、Window | `quantity` 有效 | `quantity` | `樘` |

输入已有 `quantity` 且合法时优先保留，并将来源设为 `CSV Schedule`。零值是合法观测值但会由质量模块标记；负值、无穷值和无法转换的值不参与补算。

### 3.2 造价计算

文件：`src/cost_calculator.py`

```python
calculate_costs(frame: pd.DataFrame, config: ProjectConfig) -> CostResult
```

`CostResult` 是 frozen dataclass，包含 `frame` 和 `unmatched_rows`。单价匹配顺序严格为：

1. `category + material + unit`；
2. `category + unit` 的配置兜底项（当前配置若无该项则不启用）。

不做模糊匹配、不按名称猜材料、不把缺价填为零。匹配成功且 `quantity` 有效时计算 `total_cost = quantity × unit_price`；任一条件不满足时 `unit_price` 和 `total_cost` 保持缺失，并返回可追溯的未匹配行号。

所有报告继续显示完整声明：**本项目单价为教学示例数据，不用于正式工程造价。**

### 3.3 质量检查

文件：`src/quality_checker.py`

```python
check_quality(frame: pd.DataFrame, config: ProjectConfig) -> QualityReport
```

质量检查补齐设计规定的 14 类规则：

`missing_element_name`、`missing_type_name`、`missing_material`、`missing_level`、`missing_guid`、`duplicate_element_id`、`zero_quantity`、`negative_quantity`、`unknown_unit`、`invalid_name`、`missing_section_size`、`outlier_dimension`、`duplicate_guid`、`unmatched_unit_price`。

每条问题包含原始行号、GUID、字段、规则 ID、严重程度、中文说明和建议。严重程度只能取配置中的 `Info`、`Warning`、`Error`。`missing_section_size` 与 `outlier_dimension` 在本阶段若缺少截面配置则显式列入 `not_applicable_rules`，不伪造计数。

问题行始终保留；相同规则在多行上的实例数和不同问题行数分开统计。质量状态按同一行最高严重程度聚合为 `Pass`、`Warning` 或 `Error`。

### 3.4 人工复核误差

文件：`src/validation.py`

```python
validate_manual_results(
    calculated: pd.DataFrame,
    manual: pd.DataFrame,
) -> ValidationResult
```

人工表通过 `element_id`、`guid` 或 `raw_row_number` 与计算表关联，优先使用不为空的 GUID。结果包含逐行 `auto_quantity`、`manual_quantity`、`absolute_error`、`relative_error_pct` 和按类别汇总表。

公式固定为：

```text
absolute_error = |auto_quantity - manual_quantity|
relative_error_pct = absolute_error / manual_quantity × 100
```

人工值为零时 `relative_error_pct` 保持空值，并在结果中记录中文提示；不覆盖系统计算值。缺少匹配键、重复人工键或非法人工数值都抛出带行号的 `ValidationError`。

## 4. 错误处理与可追溯性

- 输入缺列、类型错误和非法数值使用中文异常，指出字段和原始行号。
- 不可信工程量、未知单位、未匹配单价保留空值并生成质量问题。
- 不创建虚构 ID；所有问题均保留 `source_file` 和 `raw_row_number`。
- 模块输出不得写入绝对本机路径，不得改变输入对象，不得引入 IfcOpenShell。

## 5. 测试策略

采用 TDD，每个模块先观察预期 RED，再写最小实现：

- 工程量：覆盖四种来源、六类公式、负值/缺尺寸/零值和输入不变性。
- 造价：覆盖精确匹配、类别+单位兜底、未知材料、缺量和教学免责声明。
- 质量：逐条覆盖 14 类规则，验证严重程度、问题行保留、未适用规则和稳定排序。
- 人工复核：覆盖正常误差、人工值为零、重复键、缺失键、非法数值和分类型汇总。
- 阶段集成：使用固定样例运行四个模块，核对 240 行仍然保留、质量问题可追溯、所有标准列契约不变。

每个任务完成后运行专项 pytest、全量 pytest 和 `git diff --check`；阶段末再运行 `pip check` 与清洗 CLI 回归。阶段 3.2 不宣称未经实际运行的精度、性能或工程适用性。
