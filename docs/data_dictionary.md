# 标准字段数据字典

## 适用范围

本字典定义 Phase 2 基础工程使用的 18 个标准字段。字段顺序、类型、可空性和枚举与 `src/schema.py` 及配置中的契约保持一致；本阶段只为固定种子样例和 schema 校验提供文档依据。字段的原始值必须能够通过来源文件与原始行号回查，未知值不得静默改写为零。

样例文件是“程序演示数据”，不是一个真实项目。所有示例单价都必须附带以下声明：**本项目单价为教学示例数据，不用于正式工程造价。**

## 字段总表

| # | 标准字段 | 类型 | 可空性 | SI 单位 / 展示单位 | 允许枚举或取值约束 | 原始追溯与说明 |
|---:|---|---|---|---|---|---|
| 1 | `element_id` | `string` | 可空 | 无 | 来源系统的元素编号；不限定格式 | 来源系统字段（如 `Element ID`）；保留 `raw_element_id`、`source_file` 与 `raw_row_number`。缺失时保持空值，不生成伪造编号。 |
| 2 | `guid` | `string` | 可空 | 无 | 来源 GUID 字符串；格式化后仍须可回查 | 来源系统 GUID（如 `GUID`）；保留 `raw_guid`、`source_file` 与 `raw_row_number`。缺失时保持空值，不伪造 GUID。 |
| 3 | `source` | `enum/string` | 不可空 | 无 | `CSV`、`IFC` | reader 注入的来源类型；具体文件由 `source_file` 记录，原始行由 `raw_row_number` 记录。 |
| 4 | `ifc_class` | `enum/string` | 不可空 | 无 | `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow`；未知类别保留原值并报警 | CSV 映射或 IFC 实体原值；通过 `source_file`、`raw_row_number` 和映射说明回查。 |
| 5 | `category` | `string/enum` | 不可空 | 无 | 标准化类别；样例覆盖梁、柱、板、墙、门、窗 | `configs/category_mapping.json` 的映射结果；保留原表头值和 `mapping_notes`。 |
| 6 | `element_name` | `string` | 可空 | 无 | 名称规则由 `configs/naming_rules.json` 校验 | 原始族/构件名称（如 `Element Name`）；保留原值、来源文件和行号，空值进入质量问题。 |
| 7 | `type_name` | `string` | 可空 | 无 | 不预设自由文本枚举 | 原始类型字段（如 `Type Name`）；保留原值、来源文件和行号。 |
| 8 | `level` | `string/enum` | 可空 | 无 | `一层`、`二层`、`三层`；缺失为空 | `configs/level_mapping.json` 将别名映射为标准值；保留原始楼层和映射说明，缺失不猜测。 |
| 9 | `material` | `string/enum` | 可空 | 无 | 由 `configs/material_mapping.json` 定义的材料值；未知值保留并报警 | 原始材料字段和材料映射记录；保留 `raw_material`、来源文件和行号，缺失为空。 |
| 10 | `length_m` | `float` | 可空 | SI：米（m）；展示可显示为米并按报告约定保留精度 | 非负有限数；无长度或无法换算时为空 | 原始长度与 `raw_unit` 一并保留；转换规则写入清洗事件，可凭来源文件和行号回查。 |
| 11 | `area_m2` | `float` | 可空 | SI：平方米（m²）；展示单位为 m² | 非负有限数；无面积或无法换算时为空 | 原始面积与 `raw_unit` 保留；清洗事件记录换算前后值及行号。 |
| 12 | `volume_m3` | `float` | 可空 | SI：立方米（m³）；展示单位为 m³ | 非负有限数；零值可保留并触发质量检查 | 原始体积与 `raw_unit` 保留；清洗事件及 `raw_row_number` 提供回查。 |
| 13 | `quantity` | `float` | 可空 | 与 `unit` 成对；内部按 SI 计量，展示按 `unit` | 非负有限数；不可可靠计算时为空，不以行数替代 | 来源由 `quantity_source` 说明；保留原始工程量、原始单位、规则说明和行号。 |
| 14 | `unit` | `enum/string` | 可空 | `m`、`m²`、`m³`、`个`、`樘` 等统一展示单位 | 仅允许配置中登记的单位；无法识别时为空并报错 | 原始单位保留在 `raw_unit`；单位解析和换算事件带来源文件、行号及规则说明。 |
| 15 | `unit_price` | `float` | 可空 | 元 / `unit`；展示为人民币元 | 非负有限数；必须来自教学单价精确匹配 | 匹配来源为 `configs/sample_unit_prices.csv`；保留类别、材料、单位键和行号。未命中保持空值。 |
| 16 | `total_cost` | `float` | 可空 | 人民币元（元）；展示保留两位小数 | `quantity × unit_price`；任一输入缺失则为空 | 由 `quantity`、`unit_price` 和匹配记录计算；可通过元素主键、来源文件和行号回查。 |
| 17 | `quantity_source` | `enum` | 不可空 | 无 | `IFC BaseQuantity`、`Parameter Calculation`、`CSV Schedule`、`Missing` | 记录选择的工程量来源及规则 ID；原始候选值、来源文件和行号必须保留。 |
| 18 | `quality_status` | `enum` | 不可空 | 无 | `Pass`、`Warning`、`Error` | 由质量问题聚合得到；问题明细保留规则 ID、严重程度、元素标识、来源文件和 `raw_row_number`。 |

## 标识与追溯约定

- `element_id` 和 `guid` 都是来源系统标识。任何一个缺失都必须保持缺失并进入质量问题表；不得用行号、随机值或拼接值冒充业务标识。二者同时缺失的行仍保留，内部定位使用 `source_file + raw_row_number`。
- 原始列名和原始值不被覆盖。字段映射、单位换算、类别/楼层/材料标准化都应记录在清洗事件或 `mapping_notes` 中，以便从标准字段返回原始 CSV 行。
- `quantity` 是主要计价工程量，不是 DataFrame 行数；`quantity_source=Missing` 时工程量和总价保持空值。构件数量只用有效且唯一的来源标识统计。
- `source` 只表示输入分支（CSV 或 IFC），并不替代 `source_file`。所有输出相对仓库路径，例如 `data/sample/sample_elements.csv`、`outputs/excel/`，不得记录本机绝对路径。

## 配置与质量状态

字段别名、类别、楼层、材料、命名、质量阈值和单价分别由 `configs/field_mapping.json`、`configs/category_mapping.json`、`configs/level_mapping.json`、`configs/material_mapping.json`、`configs/naming_rules.json`、`configs/quality_rules.json` 与 `configs/sample_unit_prices.csv` 管理。`quantity_source` 和 `quality_status` 的值只能从本字典列出的枚举中选择；未知或拒绝值必须保留原始值并产生质量问题。

示例单价仅用于课堂演示和测试；任何页面或报告展示金额时，都必须显示：**本项目单价为教学示例数据，不用于正式工程造价。**
