# Phase 2 样例数据

本目录包含固定种子生成的 CSV fixture，用于验证 CSV 主流程的数据契约、质量规则和人工复核接口。文件由 `scripts/generate_sample_data.py` 生成，属于**程序演示数据**，不代表真实工程项目。

## 文件

- `sample_elements.csv`：240 行、UTF-8-SIG 编码的构件明细。前 18 列遵循 `src.schema.STANDARD_COLUMNS`，另含 `raw_unit`、`raw_row_number`、`source_file` 和 `exception_tags` 四个追溯列。
- `sample_manual_validation.csv`：12 条人工抽查样例，保留 `auto_quantity` 和 `manual_quantity` 两列，未覆盖自动计算结果。

样例覆盖 `一层`、`二层`、`三层` 和 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow`。固定种子为 `20260804`；重新生成应得到相同字节内容和 SHA-256。

## 预置异常

七类异常行集合彼此不重叠：缺失材料 5 行、缺失楼层 3 行、重复 GUID 2 组（4 行）、体积为零 4 行、名称无效 3 行、单位无效 2 行、未匹配教学单价 2 行。`exception_tags` 仅用于演示追踪；测试会从 CSV 的业务字段独立重算这些数量。

## 免责声明

本项目单价为教学示例数据，不用于正式工程造价。
