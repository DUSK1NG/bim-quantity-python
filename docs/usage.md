# 使用指南

以下命令从仓库根目录运行，使用 `.venv\Scripts\python.exe`。先按根目录 README 创建环境并安装 `requirements.txt`。

## 生成教学样例

```powershell
.venv\Scripts\python.exe scripts\generate_sample_data.py
```

生成器默认把构件明细与人工复核样例写入 `data/sample/`。样例仅用于程序演示，单价不用于正式工程造价。详细字段说明见 [样例数据说明](../data/sample/README.md)。

一次实测的文件 SHA-256：`ea491fc092b16b8907144b0d662f7eff4e81d735cd82d2b2c1bdb3feb7b54c41`。

## Pipeline 与报表

运行清洗、质量检查和汇总：

```powershell
.venv\Scripts\python.exe scripts\run_pipeline.py
```

一次实测输出（教学样例含预置质量问题，退出码为 `2`）：

```text
Pipeline 完成：240 行，问题行 23 行，示例总价 371855.02
标准明细：sample_elements_standard.csv
质量报告：sample_elements_quality_report.json
汇总文件：sample_elements_summary.csv
```

导出 Excel 与 CSV 报表：

```powershell
.venv\Scripts\python.exe scripts\export_report.py
```

对应输出（退出码为 `2`）：

```text
报表导出完成：240 行，问题行 23 行，示例总价 371855.02
Excel：sample_elements_report.xlsx
CSV 文件：6 个
```

两个命令默认使用 `data/sample/sample_elements.csv` 和 `configs/`，并可通过 `--input`、`--config-dir`、`--manual`、`--output-dir` 指定路径。存在 Error 级质量问题时，处理结果仍会写出，命令以退出码 `2` 结束；输入、配置、依赖或输出失败时以退出码 `1` 结束。

## 使用 IFC

基础安装使用 CSV。安装 `requirements-ifc.txt` 中的可选依赖后，Streamlit 输入面板可读取 IFC；`scripts/inspect_ifc.py` 也可把 IFC 转为标准构件 CSV 并生成诊断 JSON。reader 处理 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor` 和 `IfcWindow`，并读取可识别的构件属性与 Base Quantities。读取范围见 [数据字典](data_dictionary.md)。

处理结果保留 `source_file` 和 `raw_row_number`，便于回查输入文件与行。报表中的来源文件名会去除本机目录路径。单价与金额为配置中的教学示例值；输出不能用于真实工程造价、结算或项目验收。
