# 阶段 3.1：CSV 读取与清洗设计

## 目标

完成阶段 3 的第一条闭环：读取阶段 2 的确定性 CSV 样例，在不丢失追溯信息的前提下进行规范化，计算行级质量问题，并输出清洗后的 CSV 与结构化质量报告。

## 范围

本阶段包含：

- 从仓库相对路径读取 UTF-8-SIG CSV。
- 检查必需列和重复列名。
- 注入来源与原始行号追溯信息。
- 基于现有配置完成字段、类别、楼层、材料和单位规范化。
- 安全数值转换和行级质量检查。
- 生成具有稳定顺序的结构化质量报告。
- 提供可从仓库根目录运行的样例 CLI。

本阶段不包含：

- IFC/IfcOpenShell 读取。
- Streamlit 界面。
- Excel 或图表输出。
- 新的工程量计算规则。
- 通用校验框架或新的运行时依赖。

## 架构与数据流

```text
输入 CSV
  -> csv_reader.read_elements_csv
  -> data_cleaner.clean_elements
  -> CleaningResult(frame, QualityReport)
  -> 清洗 CSV + 质量报告 JSON
```

### Reader 边界

`src/csv_reader.py` 负责文件读取和结构校验。读取编码固定为 `utf-8-sig`；来源文件只保存仓库相对路径中的文件名；注入 `source="CSV"`；为每条数据行分配从 1 开始的 `raw_row_number`，与输入文件中的数据行对应。Reader 不负责行级质量判断。

公开接口：

```python
def read_elements_csv(path: Path) -> pd.DataFrame:
    """读取并完成一个 elements CSV 的结构校验。"""
```

文件不存在、CSV 内容不可读、列名重复或缺少标准必需列时，Reader 抛出 `CsvReaderError`。错误信息包含文件名和面向初学者的修复提示；返回数据和 JSON 报告中不得出现本机绝对路径。

### Cleaner 边界

`src/data_cleaner.py` 负责规范化、安全数值处理和行级规则评估。它接收 Reader 输出的 DataFrame 与已校验的 `ProjectConfig`；不删除问题行，也不把 `exception_tags` 当作质量判断依据。

公开接口：

```python
@dataclass(frozen=True)
class CleaningResult:
    frame: pd.DataFrame
    report: QualityReport

def clean_elements(frame: pd.DataFrame, config: ProjectConfig) -> CleaningResult:
    """规范化标准 elements DataFrame，并生成质量报告。"""
```

空字符串转为缺失值。字段别名以及类别、楼层、材料的标准值使用现有配置。未知值保留原样并产生问题。数值列必须转换为有限数值；无法安全转换时抛出 `DataCleaningError`，错误中包含字段、来源文件名和原始行号，不能静默改成 0。

`quality_status` 根据发现的问题重新计算，取该行最高严重级别；不信任输入 CSV 中原有的 `quality_status`。输入的 `exception_tags` 仅作为样例追踪信息保留。

### Quality Report 边界

`src/quality_report.py` 只存放报告数据契约和确定性序列化辅助函数。

```python
@dataclass(frozen=True)
class QualityIssue:
    raw_row_number: int
    rule_id: str
    severity: str
    field: str
    message: str

@dataclass(frozen=True)
class QualityReport:
    total_rows: int
    issue_rows: int
    clean_rows: int
    counts_by_rule: Mapping[str, int]
    counts_by_severity: Mapping[str, int]
    not_applicable_rules: tuple[str, ...]
    issues: tuple[QualityIssue, ...]
```

问题按原始行号、规则 ID、字段名排序；映射键按字典序输出。报告 JSON 必须包含固定免责声明：“本项目单价为教学示例数据，不用于正式工程造价。”

## 规则覆盖范围

14 个已配置的质量规则 ID 仍是唯一规则来源。阶段 3.1 执行能够由 18 个标准字段判断的规则：

- `missing_element_name`
- `missing_type_name`
- `missing_material`
- `missing_level`
- `missing_guid`
- `duplicate_element_id`
- `zero_quantity`
- `negative_quantity`
- `unknown_unit`
- `invalid_name`
- `duplicate_guid`
- `unmatched_unit_price`

`missing_section_size` 标记为不适用，因为标准字段中没有截面尺寸；`outlier_dimension` 标记为不适用，因为配置中没有离群阈值。不新增规则 ID。适用规则使用配置中的严重级别。

对已提交的样例，Cleaner 必须独立重算出 7 组互不相交的异常集合：缺失材料 5 行、缺失楼层 3 行、重复 GUID 4 行（2 组）、零工程量 4 行、名称不合法 3 行、未知单位 2 行、单价未匹配 2 行。样例标签 `zero_volume` 和 `invalid_unit` 分别通过清洗后的字段映射到配置规则 `zero_quantity` 和 `unknown_unit`；规则判断不能读取标签。

## 输出与 CLI

新增 `scripts/clean_sample_data.py`，参数如下：

```text
--input       输入 CSV 路径（默认：data/sample/sample_elements.csv）
--output-dir  清洗结果目录（默认：data/processed）
--report-dir  质量报告目录（默认：outputs/reports）
--config-dir  配置目录（默认：configs）
```

CLI 加载 `ProjectConfig`，读取并清洗输入文件，写出 `<stem>_clean.csv` 和 `<stem>_quality_report.json`，并打印行数与报告路径。数据和报告中只保存相对路径或文件名，不序列化本机绝对路径。

## 错误处理

- `CsvReaderError`：文件或结构问题，提供面向初学者的修复信息。
- `ConfigError`：沿用现有配置校验错误，原样向上抛出。
- `DataCleaningError`：数值无法安全转换或清洗前置条件不满足，包含文件名和原始行号。
- 行级质量问题：保留在 `QualityReport` 中，不中止整个运行。

不使用吞掉缺陷的全局异常捕获，也不静默丢弃问题行。

## 测试与验收标准

生产代码必须先写测试，并观察测试因功能不存在而失败，再实现最小代码使其通过。专项测试覆盖：

1. Reader 成功读取、UTF-8-SIG、240 行、22 列、文件名追溯和从 1 开始的原始行号。
2. Reader 对缺文件、重复列、缺必需列和损坏 CSV 的失败处理。
3. Cleaner 对空白、字段别名、数值类型和标准映射的规范化。
4. Cleaner 保留全部行，并独立验证 7 组异常集合及其互不相交性。
5. `quality_status` 重算、问题排序、配置严重级别和不适用规则。
6. JSON 序列化不含绝对路径，并包含教学单价免责声明。
7. CLI 输出文件、自定义输出目录和重复运行字节一致性。

现有全量测试必须继续通过。阶段 3.1 验收命令：

```powershell
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage3-1
```

只有在专项测试和全量测试均通过、`git diff --check` 干净、生成结果确定性一致且工作区没有非预期文件时，阶段 3.1 才算完成。
