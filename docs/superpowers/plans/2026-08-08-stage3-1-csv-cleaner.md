# 阶段 3.1 CSV 读取与清洗实施计划

> **For agentic workers:** 必须使用 `superpowers:subagent-driven-development` 按任务执行。每个任务都使用复选框跟踪，并在写生产代码前先观察测试失败。

**目标：** 读取阶段 2 的 CSV 样例，完成可追溯的字段规范化和行级质量检查，并输出确定性的清洗 CSV 与质量报告 JSON。

**架构：** Reader 只负责 UTF-8-SIG 文件读取、标准列检查和来源/行号注入；Cleaner 只负责配置驱动的规范化和质量规则；Quality Report 只负责不可变报告契约与稳定 JSON 序列化；CLI 负责组装三者并写出两个结果文件。问题行始终保留，不把样例标签当作规则来源。

**技术栈：** Python 3.10/3.11、pandas、dataclasses、pathlib、json、pytest；不新增运行时依赖，不导入 IfcOpenShell。

## 全局约束

- 使用 UTF-8-SIG 读取和写出 CSV。
- 标准数据字段保持 `src/schema.py` 中的 18 个 `STANDARD_COLUMNS` 及其顺序。
- 输入来源必须写为 `source="CSV"`，`source_file` 只保留文件名，`raw_row_number` 从 1 开始。
- 任何问题行都不得静默删除；缺失标识不得伪造，未知值不得静默改成默认值或 0。
- 质量状态只能使用 `Pass`、`Warning`、`Error`；严重级别来自 `configs/quality_rules.json`。
- `missing_section_size` 与 `outlier_dimension` 在本阶段记录为不适用，不伪造计数。
- 报告必须包含：“本项目单价为教学示例数据，不用于正式工程造价。”
- 输出中不得写入本机绝对路径或未完成占位语句。
- 保持阶段 2 的 IFC、Streamlit、Excel、图表边界，不提前实现后续模块。
- 每个任务先写测试并运行到预期 RED，再写最小生产代码；每个任务完成后运行专项测试、全量测试和 `git diff --check`。

## 文件地图

- 创建 `src/csv_reader.py`：文件读取、结构检查、追溯列注入和 `CsvReaderError`。
- 创建 `src/quality_report.py`：`QualityIssue`、`QualityReport`、稳定字典/JSON 序列化。
- 创建 `src/data_cleaner.py`：字段/枚举规范化、质量规则、`CleaningResult` 和 `DataCleaningError`。
- 创建 `scripts/clean_sample_data.py`：仓库根目录 CLI，写清洗 CSV 与质量报告 JSON。
- 创建 `tests/test_csv_reader.py`：Reader 的成功与结构错误测试。
- 创建 `tests/test_quality_report.py`：报告排序、计数和 JSON 契约测试。
- 创建 `tests/test_data_cleaner.py`：Cleaner 规范化、规则计数和状态聚合测试。
- 创建 `tests/test_stage3_cli.py`：CLI、自定义目录和确定性输出测试。
- 创建 `data/processed/.gitkeep` 与 `outputs/reports/.gitkeep`（若已存在则保持不变）；测试输出使用 ignored 临时目录。

---

### 任务 1：CSV Reader

**文件：**

- 创建：`src/csv_reader.py`
- 测试：`tests/test_csv_reader.py`

**接口：**

- 消费：`src.schema.STANDARD_COLUMNS` 和阶段 2 样例 CSV。
- 产出：`read_elements_csv(path: Path) -> pandas.DataFrame`；异常类型 `CsvReaderError(ValueError)`。

- [ ] **步骤 1：先写失败测试**

```python
def test_read_elements_csv_injects_trace_columns_and_preserves_rows():
    frame = read_elements_csv(Path("data/sample/sample_elements.csv"))
    assert len(frame) == 240
    assert frame.loc[0, "source"] == "CSV"
    assert frame.loc[0, "source_file"] == "sample_elements.csv"
    assert frame["raw_row_number"].tolist() == list(range(1, 241))
```

同时写入缺文件、重复列名、缺标准列和损坏 CSV 的 `pytest.raises(CsvReaderError)` 测试。运行：

```powershell
.venv\\python.exe -m pytest tests/test_csv_reader.py -q --basetemp=.pytest_cache\\stage3-reader-red
```

预期：因 `src.csv_reader` 不存在而 RED，不能是测试语法错误。

- [ ] **步骤 2：写最小实现**

实现 `pd.read_csv(path, encoding="utf-8-sig")`；检查文件存在、列名唯一、`STANDARD_COLUMNS` 全部存在；将 `source`、`source_file`、`raw_row_number` 设为标准值；捕获 `OSError`、`UnicodeError`、`pd.errors.ParserError` 并转换为中文 `CsvReaderError`。不做行级质量判断。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\\python.exe -m pytest tests/test_csv_reader.py -q --basetemp=.pytest_cache\\stage3-reader-green
```

预期：Reader 专项测试全部通过，且 `source_file` 不包含路径分隔符。

- [ ] **步骤 4：提交任务**

```powershell
git add src/csv_reader.py tests/test_csv_reader.py
git commit -m "feat: add csv reader"
```

---

### 任务 2：质量报告契约

**文件：**

- 创建：`src/quality_report.py`
- 测试：`tests/test_quality_report.py`

**接口：**

- 消费：`QualityIssue` 和 `QualityReport` 实例。
- 产出：`quality_report_to_dict(report, source_file: str) -> dict[str, Any]` 与 `write_quality_report(report, path: Path, source_file: str) -> None`。

- [ ] **步骤 1：先写失败测试**

```python
def test_quality_report_serializes_stable_counts_and_disclaimer(tmp_path):
    report = QualityReport(
        total_rows=2,
        issue_rows=1,
        clean_rows=1,
        counts_by_rule={"missing_level": 1},
        counts_by_severity={"Warning": 1},
        not_applicable_rules=("outlier_dimension",),
        issues=(QualityIssue(2, "missing_level", "Warning", "level", "缺失楼层"),),
    )
    output = tmp_path / "report.json"
    write_quality_report(report, output, "sample_elements.csv")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_file"] == "sample_elements.csv"
    assert payload["disclaimer"] == "本项目单价为教学示例数据，不用于正式工程造价。"
    assert payload["issues"][0]["raw_row_number"] == 2
```

运行并确认因模块缺失而 RED：

```powershell
.venv\\python.exe -m pytest tests/test_quality_report.py -q --basetemp=.pytest_cache\\stage3-report-red
```

- [ ] **步骤 2：写最小实现**

使用 frozen dataclasses；序列化时按 `raw_row_number/rule_id/field` 排序，映射键按字典序输出，路径只接受并写出 basename；JSON 使用 UTF-8、稳定缩进和换行。 `issue_rows` 表示出现至少一个问题的不同原始行数，规则和严重级别计数表示问题实例数。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\\python.exe -m pytest tests/test_quality_report.py -q --basetemp=.pytest_cache\\stage3-report-green
```

- [ ] **步骤 4：提交任务**

```powershell
git add src/quality_report.py tests/test_quality_report.py
git commit -m "feat: add quality report contract"
```

---

### 任务 3：Data Cleaner

**文件：**

- 创建：`src/data_cleaner.py`
- 测试：`tests/test_data_cleaner.py`

**接口：**

- 消费：任务 1 的 DataFrame、`load_project_config(Path("configs"))`、任务 2 的 `QualityReport`。
- 产出：`clean_elements(frame: pd.DataFrame, config: ProjectConfig) -> CleaningResult`；异常类型 `DataCleaningError(ValueError)`。

- [ ] **步骤 1：先写失败测试**

```python
def test_clean_elements_recomputes_disjoint_sample_anomalies():
    config = load_project_config(Path("configs"))
    frame = read_elements_csv(Path("data/sample/sample_elements.csv"))
    result = clean_elements(frame, config)
    assert len(result.frame) == 240
    assert result.report.counts_by_rule == {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid": 4,
        "zero_quantity": 4,
        "invalid_name": 3,
        "unknown_unit": 2,
        "unmatched_unit_price": 2,
    }
    assert result.report.not_applicable_rules == ("missing_section_size", "outlier_dimension")
```

再写别名、空白、非法数值、质量状态重算、问题行不删除、未知值保留和重复 GUID 分组测试。运行：

```powershell
.venv\\python.exe -m pytest tests/test_data_cleaner.py -q --basetemp=.pytest_cache\\stage3-cleaner-red
```

预期：因 `src.data_cleaner` 不存在而 RED。

- [ ] **步骤 2：写最小实现**

按现有 `field_mapping.json`、`category_mapping.json`、`level_mapping.json`、`material_mapping.json` 和命名规则构建别名查找；空白转缺失；数值列用 `pd.to_numeric(errors="coerce")` 后对原始非空且转换失败的单元格抛 `DataCleaningError`；使用配置严重级别创建规则问题；重复 GUID/ID 按非空值分组；单价按 category/material/unit 精确匹配；根据每行最高严重级别设置 `quality_status`；保留全部行。

- [ ] **步骤 3：验证 GREEN**

```powershell
.venv\\python.exe -m pytest tests/test_data_cleaner.py -q --basetemp=.pytest_cache\\stage3-cleaner-green
```

预期：7 组样例异常计数精确、集合两两不相交、重复 GUID 为 2 组/4 行，且报告排序稳定。

- [ ] **步骤 4：提交任务**

```powershell
git add src/data_cleaner.py tests/test_data_cleaner.py
git commit -m "feat: add configurable data cleaner"
```

---

### 任务 4：清洗 CLI 与端到端验收

**文件：**

- 创建：`scripts/clean_sample_data.py`
- 测试：`tests/test_stage3_cli.py`
- 修改：`README.md`（只补充阶段 3.1 运行命令和输出说明）

**接口：**

- 消费：任务 1–3 的公开接口。
- 产出：`--input`、`--output-dir`、`--report-dir`、`--config-dir` 四个 CLI 参数；清洗 CSV 与质量报告 JSON。

- [ ] **步骤 1：先写失败测试**

```python
def test_clean_cli_writes_repeatable_relative_outputs(tmp_path):
    run_cli(tmp_path / "one")
    run_cli(tmp_path / "two")
    assert (tmp_path / "one" / "sample_elements_clean.csv").read_bytes() == (
        tmp_path / "two" / "sample_elements_clean.csv"
    ).read_bytes()
    report = json.loads((tmp_path / "one" / "sample_elements_quality_report.json").read_text(encoding="utf-8"))
    assert report["source_file"] == "sample_elements.csv"
    assert "\\" not in report["source_file"]
```

运行：

```powershell
.venv\\python.exe -m pytest tests/test_stage3_cli.py -q --basetemp=.pytest_cache\\stage3-cli-red
```

预期：因 CLI 文件不存在而 RED。

- [ ] **步骤 2：写最小实现**

使用 `argparse` 设置四个参数默认值；从仓库根路径解析默认输入、配置、处理结果和报告目录；调用 `load_project_config`、`read_elements_csv`、`clean_elements`；写 `<stem>_clean.csv` 为 UTF-8-SIG，并通过 `write_quality_report` 写 JSON；输出总行数、问题行数和报告相对路径。

- [ ] **步骤 3：验证 GREEN 与全量回归**

```powershell
.venv\\python.exe -m pytest tests/test_stage3_cli.py -q --basetemp=.pytest_cache\\stage3-cli-green
.venv\\python.exe -m pytest -q --basetemp=.pytest_cache\\stage3-1-full
```

预期：阶段 3.1 专项测试与既有测试全部通过；两套自定义目录输出字节一致；输出无绝对路径。

- [ ] **步骤 4：更新中文运行文档并提交**

在 `README.md` 增加阶段 3.1 命令：

```powershell
.venv\\python.exe scripts\\clean_sample_data.py --input data\\sample\\sample_elements.csv --output-dir data\\processed --report-dir outputs\\reports --config-dir configs
```

然后运行 `git diff --check`，提交：

```powershell
git add scripts/clean_sample_data.py tests/test_stage3_cli.py README.md
git commit -m "feat: add stage3 cleaning cli"
```

---

## 计划自审

- 覆盖设计文档中的 Reader、Cleaner、Quality Report、CLI、异常处理、7 组样例异常、免责声明、确定性输出和阶段边界。
- 全文不使用未完成占位语句或模糊的“稍后实现”描述。
- 后续任务只依赖前置任务明确的函数、类和字段名称。
- 每个任务都有明确文件、RED 命令、GREEN 命令和提交边界。
