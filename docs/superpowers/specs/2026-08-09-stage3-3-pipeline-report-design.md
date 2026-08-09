# 阶段 3.3 Pipeline、汇总与 Excel 报表设计

## 1. 目标与边界

阶段 3.3 将阶段 3.1 和 3.2 已验证的模块编排成一条可复用的 CSV 主流程，并交付可回读的工程量与教学造价报表。命令行和后续 Streamlit 只调用同一个 Pipeline，不在入口中复制计算规则。

本阶段实现：PipelineArtifacts、楼层/类别/材料汇总、项目概览、示例造价汇总、8 个工作表 Excel、明细/汇总/质量 CSV 导出和两个专用脚本。Streamlit、Plotly 图表、IFC reader、数据库和通用 ETL 框架仍不实现。

## 2. 数据流与模块边界

```text
CSV + configs + optional manual CSV
              ↓
        src.pipeline.run_pipeline
              ↓
reader → cleaner → quantity → cost → quality → validation
              ↓
        PipelineArtifacts
          ├─ standard_frame
          ├─ quality_report
          ├─ validation_result
          ├─ overview
          └─ aggregations
              ↓
      report_generator / run_pipeline.py / export_report.py
```

### 2.1 Pipeline

文件：`src/pipeline.py`

```python
run_pipeline(
    input_path: Path,
    config_dir: Path,
    manual_path: Path | None = None,
) -> PipelineArtifacts
```

`PipelineArtifacts` 使用 frozen dataclass，至少包含：

- `standard_frame`：经过 reader、cleaner、quantity、cost 的 22 列标准明细；所有输入行保留；
- `quality_report`：含 14 类规则、问题行、严重度计数和追溯字段；
- `validation_result`：有人工表时返回验证结果，否则返回空结果；
- `overview`：输入文件名、总行数、可信构件数、类别数、楼层数、总面积、总体积、问题行数和示例总价；
- `by_level`、`by_category`、`by_material`、`cost_summary`：汇总 DataFrame；
- `source_file` 和 `disclaimer`：运行元数据。

Pipeline 只负责顺序、错误边界和结果组装，不在其中实现别名、公式或单价规则。缺少人工复核表不是错误，返回空验证结果；配置错误、输入结构错误和不可读文件是可解释的致命错误。

### 2.2 汇总

文件：`src/aggregations.py`

```python
summarize_by_level(frame: pd.DataFrame) -> pd.DataFrame
summarize_by_category(frame: pd.DataFrame) -> pd.DataFrame
summarize_by_material(frame: pd.DataFrame) -> pd.DataFrame
summarize_costs(frame: pd.DataFrame) -> pd.DataFrame
build_overview(frame: pd.DataFrame, report: QualityReport, source_file: str) -> dict[str, Any]
```

汇总只使用有效非负数值；缺失值不填零后参与金额推断。可信构件数按非空且唯一的 `element_id` 统计，若没有有效 ID 则不使用 DataFrame 行数冒充构件数。各分组结果保留分组字段、`element_count`、`quantity_sum`、`volume_sum`、`area_sum`、`total_cost`，空结果也返回固定列。

### 2.3 Excel 报表

文件：`src/report_generator.py`

```python
write_excel_report(artifacts: PipelineArtifacts, output_path: Path) -> None
write_csv_exports(artifacts: PipelineArtifacts, output_dir: Path) -> tuple[Path, ...]
```

Excel 固定包含以下 8 个工作表，名称和顺序不得改变：

1. `项目概览`
2. `全部构件明细`
3. `分楼层工程量`
4. `分构件工程量`
5. `分材料工程量`
6. `示例造价汇总`
7. `数据质量问题`
8. `人工复核结果`

每张表冻结首行并开启自动筛选；列宽按内容限制在可读范围；数量保留三位小数，金额保留两位小数；质量问题表的 Error/Warning 行使用条件格式或显式填充；概览表写入生成时间、来源文件和完整免责声明。坏行只标记，不删除。

CSV 导出至少包含全部构件明细、楼层汇总、类别汇总、材料汇总、造价汇总和质量问题清单，文件名固定使用输入 stem 加表义名称，来源字段只写文件名。

## 3. 命令行入口

### 3.1 `scripts/run_pipeline.py`

参数：`--input`、`--config-dir`、`--manual`、`--output-dir`。运行 Pipeline，写出中间标准 CSV、质量 JSON 和汇总 CSV，并打印行数、问题行数、示例总价和输出位置。

### 3.2 `scripts/export_report.py`

参数：`--input`、`--config-dir`、`--manual`、`--output-dir`。直接调用同一个 Pipeline，写出 8 工作表 Excel 和约定 CSV；不复制任何计算逻辑。

脚本退出码：0 表示完成且无 Error 质量问题，2 表示报告已生成但存在 Error，1 表示配置/输入/写出失败。路径只通过 `pathlib` 处理，报错包含中文修复建议。

## 4. 错误处理与可追溯性

- Pipeline 失败前不生成半成品；报告写入临时文件后再替换目标文件。
- 所有质量问题包含 `source_file` 文件名和 `raw_row_number`；汇总不能隐藏问题行。
- 无法计价的单价和总价保持空值；概览中的示例总价只累加有限非负的已匹配金额。
- 空 DataFrame、全坏行和缺少人工复核表都必须产生结构正确的结果，而不是异常崩溃。
- 报表只使用 `openpyxl` 和 `pandas`，不自写 Excel 解析器；不导入 IfcOpenShell。

## 5. 测试策略

- Pipeline fixture：固定 240 行样例经过所有模块后行数不变，列顺序为配置 field_order，质量计数和人工复核结果可追溯。
- 汇总测试：逐层、类别、材料和造价的固定值、空数据、缺失值和重复 ID 统计。
- Excel 测试：使用 `openpyxl.load_workbook` 回读 8 个工作表、顺序、冻结窗格、自动筛选、格式、免责声明和异常行格式。
- CLI 测试：两个输出目录字节确定性、相对路径、退出码和错误提示；`run_pipeline.py` 与 `export_report.py` 使用同一 Pipeline。
- 每个任务先 RED，再 GREEN；阶段结束运行全量 pytest、`pip check`、两个 CLI 冒烟和 `git diff --check`。

阶段 3.3 的金额、误差和报表只服务于程序演示与教学验证，不代表正式工程造价、结算或验收结论。

