# 阶段 3.3 Pipeline 与报表实施计划

> **For agentic workers:** 必须使用 `superpowers:subagent-driven-development` 按任务执行。每个任务使用复选框跟踪，写生产代码前先观察测试失败。

**目标：** 编排阶段 3.1/3.2 模块，生成可追溯汇总、8 工作表 Excel 和稳定的 CSV 主流程命令。

**架构：** `aggregations` 只负责确定性分组统计，`pipeline` 只负责调用顺序和结果组装，`report_generator` 只负责 Excel/CSV 输出，两个脚本只负责参数解析和退出码。所有模块复用既有标准字段、配置和质量报告契约。

**技术栈：** Python 3.10/3.11、pandas、openpyxl、dataclasses、pathlib、pytest；不导入 Plotly、Streamlit 或 IfcOpenShell，不建立通用 ETL 框架。

## 全局约束

- 标准明细列严格按 `configs/field_mapping.json` 的 `field_order` 输出，问题行不删除。
- 汇总只对有限非负数值聚合；缺失金额保持空值，不填 0 伪造价格。
- 可信构件数按非空唯一 `element_id` 统计，不用 DataFrame 行数冒充。
- Excel 固定 8 个工作表及顺序：`项目概览`、`全部构件明细`、`分楼层工程量`、`分构件工程量`、`分材料工程量`、`示例造价汇总`、`数据质量问题`、`人工复核结果`。
- 所有报告包含 `本项目单价为教学示例数据，不用于正式工程造价。`。
- 来源字段只保留文件名，不能写入本机绝对路径；不能静默删除坏行。
- 每项任务先写测试并观察预期 RED，再写最小实现；完成后运行专项、全量和 `git diff --check`。

## 文件地图

- 创建 `src/aggregations.py`：楼层、类别、材料、造价汇总和概览。
- 创建 `src/pipeline.py`：PipelineArtifacts 与统一编排。
- 创建 `src/report_generator.py`：Excel 八表与 CSV 导出。
- 创建 `scripts/run_pipeline.py`：流水线输出 CLI。
- 创建 `scripts/export_report.py`：Excel/CSV 报表 CLI。
- 创建 `tests/test_aggregations.py`、`tests/test_pipeline.py`、`tests/test_report_generator.py`、`tests/test_stage33_cli.py`。
- 修改 `README.md`：增加中文阶段 3.3 命令和边界说明。

---

### Task 1：汇总函数

**Files:**

- Create: `src/aggregations.py`
- Test: `tests/test_aggregations.py`

**Interfaces:**

```python
summarize_by_level(frame: pd.DataFrame) -> pd.DataFrame
summarize_by_category(frame: pd.DataFrame) -> pd.DataFrame
summarize_by_material(frame: pd.DataFrame) -> pd.DataFrame
summarize_costs(frame: pd.DataFrame) -> pd.DataFrame
build_overview(frame: pd.DataFrame, report: QualityReport, source_file: str) -> dict[str, Any]
```

- [ ] **Step 1: Write the failing test**

先测试固定小表的楼层/类别/材料分组，断言 `element_count`、`quantity_sum`、`area_sum`、`volume_sum`、`total_cost`；测试空表返回固定列；测试重复/空 `element_id` 不增加可信构件数；测试有限非负金额汇总和概览字段。

运行：

```powershell
.venv\python.exe -m pytest tests/test_aggregations.py -q --basetemp=.pytest_cache\stage33-aggregations-red
```

预期：因 `src.aggregations` 不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

复制输入后用 pandas `groupby(dropna=False, sort=True)`；对缺失分组显示 `未分类`；数值列只保留有限非负值后聚合；所有空结果使用与非空结果相同的列顺序。概览中 `total_cost` 只累加有限非负已匹配金额。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_aggregations.py -q --basetemp=.pytest_cache\stage33-aggregations-green
```

- [ ] **Step 4: Commit**

```powershell
git add src/aggregations.py tests/test_aggregations.py
git commit -m "feat: add quantity aggregations"
```

---

### Task 2：Pipeline 编排

**Files:**

- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class PipelineArtifacts: ...

run_pipeline(
    input_path: Path,
    config_dir: Path,
    manual_path: Path | None = None,
) -> PipelineArtifacts
```

- [ ] **Step 1: Write the failing test**

先测试固定样例：Pipeline 返回 240 行标准明细、22 列字段顺序、质量报告、非空汇总和人工复核结果；再测试没有人工表时返回空 `ValidationResult`；输入文件不存在和配置错误抛出可读的 `PipelineError`。

运行：

```powershell
.venv\python.exe -m pytest tests/test_pipeline.py -q --basetemp=.pytest_cache\stage33-pipeline-red
```

预期：因 `src.pipeline` 不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

按固定顺序调用 `load_project_config`、`read_elements_csv`、`clean_elements`、`calculate_quantities`、`calculate_costs`、`check_quality`、可选 `validate_manual_results` 和 Task 1 汇总函数；任何上游错误转换为中文 `PipelineError`，不吞掉错误。`standard_frame` 使用 cost 结果，质量报告使用同一标准表。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_pipeline.py -q --basetemp=.pytest_cache\stage33-pipeline-green
```

再运行 Stage 3.1/3.2 全部测试，确认 Pipeline 不修改输入文件。

- [ ] **Step 4: Commit**

```powershell
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add quantity pipeline"
```

---

### Task 3：Excel 与 CSV 报表生成器

**Files:**

- Create: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Interfaces:**

```python
write_excel_report(artifacts: PipelineArtifacts, output_path: Path) -> None
write_csv_exports(artifacts: PipelineArtifacts, output_dir: Path) -> tuple[Path, ...]
```

- [ ] **Step 1: Write the failing test**

先用最小 `PipelineArtifacts` fixture 调用 Excel 写出函数，使用 `openpyxl.load_workbook` 断言 8 个工作表及顺序、冻结首行、自动筛选、免责声明、概览来源和数值格式；再断言 CSV 导出文件集合、UTF-8-SIG 和相对来源字段。

运行：

```powershell
.venv\python.exe -m pytest tests/test_report_generator.py -q --basetemp=.pytest_cache\stage33-report-red
```

预期：因 `src.report_generator` 不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

使用 `pandas.ExcelWriter(engine="openpyxl")` 写固定 8 表；通过 openpyxl 设置冻结窗格、自动筛选、列宽、三位工程量/两位金额格式和 Error/Warning 条件格式；输出前创建父目录，先写临时文件再替换目标。质量问题 DataFrame 从 `QualityReport` 序列化，人工结果为空时写固定列空表。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_report_generator.py -q --basetemp=.pytest_cache\stage33-report-green
```

回读工作簿并确认坏行数量与质量报告一致。

- [ ] **Step 4: Commit**

```powershell
git add src/report_generator.py tests/test_report_generator.py
git commit -m "feat: add excel report generator"
```

---

### Task 4：两个 CLI 与阶段回归

**Files:**

- Create: `scripts/run_pipeline.py`
- Create: `scripts/export_report.py`
- Test: `tests/test_stage33_cli.py`
- Modify: `README.md`

**Interfaces:**

```text
run_pipeline.py --input --config-dir --manual --output-dir
export_report.py --input --config-dir --manual --output-dir
```

- [ ] **Step 1: Write the failing test**

先测试两个脚本的 `--help` 参数、两个自定义目录的确定性输出、Excel 8 表、CSV 文件、相对路径和退出码；错误输入测试返回非零退出码并包含中文修复提示。

运行：

```powershell
.venv\python.exe -m pytest tests/test_stage33_cli.py -q --basetemp=.pytest_cache\stage33-cli-red
```

预期：因两个脚本不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

两个脚本都只解析参数并调用 `run_pipeline`；`run_pipeline.py` 写中间标准 CSV、质量 JSON 和汇总 CSV；`export_report.py` 调用 `write_excel_report` 与 `write_csv_exports`；根据质量 Error 数量返回 0 或 2，异常返回 1。不得在脚本中复制计算逻辑。

- [ ] **Step 3: Verify GREEN and full regression**

```powershell
.venv\python.exe -m pytest tests/test_stage33_cli.py -q --basetemp=.pytest_cache\stage33-cli-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage33-full
.venv\python.exe -m pip check
```

运行两个 CLI 和既有清洗 CLI，使用 `openpyxl` 回读 Excel，并运行 `git diff --check`。

- [ ] **Step 4: Update Chinese README and commit**

README 增加阶段 3.3 命令、输出位置、8 个工作表列表、免责声明和仍未实现的 Streamlit/Plotly/IFC 边界；不宣称未经运行的精度或性能。

```powershell
git add scripts/run_pipeline.py scripts/export_report.py tests/test_stage33_cli.py README.md
git commit -m "feat: add pipeline and report cli"
```

---

## 计划自审

- 四项任务覆盖设计中的汇总、PipelineArtifacts、8 工作表、CSV 导出、两个 CLI 和端到端回归。
- 所有接口名称、字段、工作表顺序、退出码和免责声明与阶段 3.3 设计一致。
- 未引入数据库、通用 ETL、Streamlit、Plotly 或 IFC；未包含未完成占位词和绝对用户路径。
- 每项任务都有独立 RED、GREEN、回归和提交步骤。

