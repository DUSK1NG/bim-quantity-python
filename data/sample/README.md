# 阶段 2 样例数据

本目录包含固定种子生成的 CSV fixture，用于验证标准字段、配置契约、质量异常和人工复核接口。文件由 `scripts/generate_sample_data.py` 生成，属于**程序演示数据**，不代表真实工程项目。

## 文件

- `sample_elements.csv`：240 行、UTF-8-SIG 编码的构件明细。前 18 列遵循 `src.schema.STANDARD_COLUMNS`，另含 `raw_unit`、`raw_row_number`、`source_file` 和 `exception_tags` 四个追溯列。
- `sample_manual_validation.csv`：至少 12 条人工抽查样例，保留 `auto_quantity` 和 `manual_quantity` 两列，不覆盖自动计算结果。

## 生成命令与覆盖

从仓库根目录运行：

```powershell
.venv\Scripts\python.exe scripts/generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data/sample
```

样例覆盖标准化楼层 `一层`、`二层`、`三层`，以及 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类构件。固定种子为 `20260804`；重新生成应得到相同字节内容和 SHA-256。

## 预置异常

七类异常行集合彼此不重叠，测试从读回的 CSV 业务字段独立重算：

- 缺失材料 5 条；
- 缺失楼层 3 条；
- 重复 GUID 2 组（4 行受影响）；
- 体积为零 4 条；
- 名称不符合规则 3 条；
- 单位异常 2 条；
- 单价无法匹配 2 条。

`exception_tags` 仅用于演示追踪，不是验收依据；不得以标签或生成日志代替 CSV 字段复核。

## 免责声明

本项目单价为教学示例数据，不用于正式工程造价。

请勿将本目录的程序演示数据、示例单价或人工抽查值当作真实工程数据、结算依据或正式造价成果。
