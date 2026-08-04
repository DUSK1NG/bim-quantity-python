# 项目设计规格：基于 Revit/IFC 与 Python 的建筑工程量自动统计及可视化系统

## 文档定位与边界

本规格面向本科生团队，约 4—8 周完成，运行环境为 Windows 10/11 的本地 Python 项目。产品从一个可复现的 CSV 端到端流程开始：读取构件明细、统一字段、清洗、计算工程量和教学示例造价、执行质量检查、导出 Excel 和图表，再由 Streamlit 提供可视化入口，最后以可选适配器接入 IFC。Revit 文件不直接作为首版输入；Revit 导出的 CSV 是首选数据交换格式。

本文是实现和验收依据。文中“必须”“不得”是约束，“目标”是计划中的验收条件；未运行的测试、性能或精度不在此文档中宣称为已达到。

## 1. 目标与成功标准

### 1.1 目标

- 把常见 Revit/IFC 构件明细转换为统一的、可追溯的 DataFrame，并让每一条计价工程量能回到原始行和来源。
- 用显式且可教学的规则计算长度、面积、体积、数量及总价；区分“构件计数”和“计价工程量”。
- 通过至少八类质量检查提前暴露缺字段、单位混乱、重复 GUID、异常尺寸和不可计价记录。
- 生成可交付的八工作表 Excel、CSV 汇总和七类可交互图表；同一套核心函数可从脚本、pytest 和 Streamlit 调用。
- 为后续 IFC 接入保留稳定的 schema 和 reader 边界，不把首版绑死在某一个 BIM 软件版本。

### 1.2 验收条件（在实现完成后逐项执行）

1. 固定随机种子可生成不少于 200 条模拟 CSV 明细；验收样例至少覆盖标准化后的`一层`、`二层`、`三层`和 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类构件。生成器的种子、记录数和字段顺序写入配置，连续运行可得到相同结果。
2. `csv_reader` 按显式顺序识别并读取 UTF-8-SIG、UTF-8、GBK；全部失败时给出包含候选编码的可解释错误。中英文表头通过配置映射到统一 schema。
3. 在同一输入上，命令行和 Streamlit 调用相同 pipeline，产出相同的标准 DataFrame、质量摘要和金额汇总（展示层排序差异除外）。
4. 每条记录保留来源系统给出的 `element_id` 和 `guid`；二者缺失时保持空值并报错，不伪造业务 ID。内部追踪使用 `source_file + raw_row_number`。`quantity_source` 只允许 `IFC BaseQuantity`、`Parameter Calculation`、`CSV Schedule`、`Missing`；主要计价工程量填入 `quantity`，可信构件数量按有效唯一 ID 统计，不以 DataFrame 行数代替。
5. 清洗、工程量、造价、质量检查均有 pytest 单元测试；另有固定 fixture 的端到端测试和命令行冒烟测试。验收只记录实际测试输出，不预先声称通过率或耗时。
6. Excel 导出包含附件约定的八个工作表，冻结表头、开启筛选、调整列宽、设置数值格式并突出异常行；坏行不会静默丢弃，均在质量表中留下行号。
7. Streamlit 包含项目概览、工程量分析、构件查询、数据质量检查、误差分析、报表导出六个页面，支持上传 CSV 和 IFC，并展示附件约定的七类图表；无输入、编码错误和全坏行时显示可行动的提示。
8. IFC 适配器为可选功能：未安装 IfcOpenShell 时主流程仍可运行，页面和命令行脚本能明确说明该能力不可用，而不是在导入阶段导致整个应用退出。

## 2. 技术 MVP、非目标与执行原则

### 2.1 MVP 范围

**数据与样例**

- 提供固定种子 `20260804` 的模拟数据生成脚本，生成 240 行数据，覆盖六类 IFC 类、三层、多个材料和类型。主样例采用一套明确表头；UTF-8-SIG、UTF-8、GBK 及中英文字段映射使用独立测试 fixture 验证，避免在同一明细表中制造相互冲突的同义列。
- 样例必须稳定包含：5 条缺失材料、3 条缺失楼层、2 组重复 GUID（4 条受影响行）、4 条体积为零、3 条名称不符合规则、2 条单位异常、2 条单价无法匹配。七类异常行集合必须两两不相交；生成器测试必须从读回的 CSV 独立核对每类精确数量，并在数据说明中标明“程序演示数据”。
- 接受 Revit 导出的 CSV 作为端到端主输入。约定一行代表一个明细元素；同一元素的重复行必须能被检查识别，不能隐式相加。
- 支持可选 IFC 文件输入。`ifc_reader` 只负责提取通用属性和几何候选值，缺失几何时返回可追溯的空值与质量状态。

**读取、映射与清洗**

- `csv_reader` 使用 `pandas.read_csv` 读取并保留 `raw_row_number`，按配置中的 `utf-8-sig`、`utf-8`、`gbk` 顺序尝试；不自写 CSV 解析器。字段名只做项目所需的规范化（去首尾空格、大小写和全角符号归一）。
- 中英字段映射由 JSON 配置驱动，至少覆盖下列别名：`构件ID/Element ID`、`全局唯一标识/GUID`、`楼层/Level`、`类别/Category`、`族名称/Element Name`、`类型/Type Name`、`长度/Length`、`面积/Area`、`体积/Volume`、`数量/Quantity`、`单位/Unit`、`材料/Material`。未知列保留在原始列字典，不擅自猜测。
- `data_cleaner` 做空白与缺失值处理、数值和单位解析、米/平方米/立方米换算、负数和极端值标记、类别标准化、GUID 格式化、ID 去重计数。清洗记录写入警告清单，原值可通过 `raw_*` 字段或原始行号回查。
- 楼层、类别、材料和名称映射分别来自 `configs/level_mapping.json`、`category_mapping.json`、`material_mapping.json`、`naming_rules.json`。例如 `Level 1`、`一层`、`1F`、`First Floor` 统一为`一层`；业务模块不得再维护第二份隐藏映射。

**工程量、造价与质量**

- `quantity_calculator` 使用明确的来源优先级：有效 IFC Base Quantities → 有效 CSV 明细表工程量 → 参数完整时按类别公式补算 → `Missing`。无法可靠计算时 `quantity` 为空，不猜测、不填零。
- `cost_calculator` 从 `configs/sample_unit_prices.csv` 读取人民币教学单价，按“类别 + 材料 + 单位”精确匹配，未命中时再按“类别 + 单位”匹配；不做模糊匹配。找不到单价时 `total_cost` 为空并产生 `Warning`。
- 所有页面和报告必须显示完整声明：“本项目单价为教学示例数据，不用于正式工程造价。”不得使用或暗示使用真实定额数据库。
- `quality_checker` 实现附件规定的 14 类检查：构件名称为空、构件类型为空、材料为空、楼层为空、GUID 为空、构件编号重复、工程量为零、工程量为负、单位无法识别、名称不符合规则、截面尺寸缺失、尺寸明显异常、同一 GUID 重复、单价无法匹配。每条异常包含 GUID、名称、类型、楼层、异常类型、说明、严重程度和建议，严重程度只允许 `Info`、`Warning`、`Error`。
- `validation` 读取人工抽查表，计算绝对误差、相对误差、平均相对误差、最大误差和分构件类型误差。相对误差严格使用 `|自动值 - 人工值| / 人工值 × 100%`；人工值为零时相对误差留空并给出明确提示，不把人工值覆盖系统值。

**输出与交互**

- `report_generator` 导出八个必备工作表：`项目概览`、`全部构件明细`、`分楼层工程量`、`分构件工程量`、`分材料工程量`、`示例造价汇总`、`数据质量问题`、`人工复核结果`。冻结表头并开启筛选，自动调整列宽，金额保留两位、工程量保留三位，异常行使用条件格式；生成时间、来源和免责声明写入项目概览。如确有验收价值，可追加配置快照工作表，但不得替换八个必备表。
- `charts` 用 Plotly 实现七类图：各楼层构件数量、各楼层混凝土体积、构件类型工程量占比、材料用量对比、示例费用分布、数据质量问题数量、人工复核误差。每张图必须处理空数据并明确中文标题、单位、图例、悬浮信息和排序。
- Streamlit 六个页面只承担上传、筛选、表格/图表展示和下载，不复制计算规则。命令行入口采用规格指定的三个专用脚本：`scripts/generate_sample_data.py`、`scripts/run_pipeline.py`、`scripts/export_report.py`；不为四个固定动作自建通用 CLI 框架。

| Streamlit 页面 | 固定职责 |
|---|---|
| 项目概览 | 文件名、构件总数、类别数、楼层数、总面积、总体积、异常数、示例总价 |
| 工程量分析 | 按楼层、类别、材料筛选，展示工程量表和统计图 |
| 构件查询 | 按 GUID、名称、类型、楼层、材料、类别组合查询 |
| 数据质量检查 | 异常总数、严重程度/异常类型统计、明细筛选和处理建议 |
| 误差分析 | 自动值与人工值、平均/最大/分类型误差及误差图 |
| 报表导出 | 下载全部构件 CSV、工程量统计 CSV、异常清单 CSV 和完整 Excel |

### 2.2 明确非目标

- 不在 MVP 中实现 Revit 插件、Revit API 写回、实时模型同步、云端协作、用户权限、数据库服务或跨项目成本数据库。
- 不引入 Web 后端、数据库、ETL 编排、依赖注入（DI）容器、事件总线或通用规则 DSL；三个专用脚本和 Streamlit 直接调用轻量 pipeline 即可满足教学闭环。
- 不承诺施工图级或竣工结算级精度，不替代造价师审核、合同计价规则、规范审查或现场复测。
- 不实现复杂曲面、钢筋翻样、幕墙深化、机电管综、洞口自动扣减和跨模型碰撞；这类需求只能在 IFC 适配器稳定后另行立项。
- 不隐式推断缺失值、不把未知单位当作米、不删除坏行、不用随机数据声称真实项目结果，也不自行实现 CSV/Excel/IFC 解析器来替代成熟库。
- 原始（raw）字段、规范（canonical）字段和转换事件必须保持可追溯关系；未知、拒绝或缺失记录不得静默填 0。无法计价时使用空值并产生 `Warning` 或 `Error`，同时保留原始值、规则 ID 与行号。

### 2.3 八条原则的可执行约束

| 原则 | 执行约束 | 检查证据 |
|---|---|---|
| 系统所需 | 每个需求必须对应模块、输入、输出和验收测试；无对应项的功能不进入 MVP。 | 需求—模块—测试追踪表、八工作表样例 |
| 局部自治 | reader、cleaner、calculator、checker、reporter 通过明确 DataFrame/数据类接口通信；模块不得读取页面全局状态。 | 单元测试可独立构造输入；依赖方向检查 |
| 显式逻辑 | 公式、单位换算、单价匹配、质量规则、状态优先级均写成可审阅配置/函数，并记录 `quantity_source`；规则集和配置必须带 `schema_version`/`config_version`。 | 规则 ID、公式测试、运行元数据 |
| 特化实现 | 只实现建筑六类构件和教学示例单价；每个特殊规则带类别/单位条件，拒绝泛化猜测。 | 类别覆盖测试、未知类别警告 |
| 闭环验证 | 每次运行都生成明细、汇总、质量报告和元数据；错误可回到原始文件行号。 | 端到端 fixture、坏行报告、下载文件检查 |
| 可控放权 | 自动计算仅在字段、单位、公式和单价均可信时采用；其余标记 `Warning`/`Error` 并进入人工复核清单。 | 状态聚合测试、人工复核误差报告 |
| 并行迭代 | CSV、质量、报告、UI 可在稳定接口下并行开发；每周合并前运行全套 pytest 和三个脚本的冒烟测试。 | 分支/任务清单、CI 或本地命令记录 |
| 必要时重构 | 当同一逻辑在两个以上入口重复、规则难以测试或字段映射持续膨胀时，暂停加功能，先提取共享模块并补回归测试。 | 重构前后回归结果、架构决策记录 |

依赖实现优先采用 Python 标准库 `pathlib`、`json`、`logging`、`dataclasses`；CSV、数据清洗和聚合复用 `pandas`，Excel 复用 `pandas.ExcelWriter` 与 `openpyxl`，图表和界面复用 `Plotly`、`Streamlit`，测试使用 `pytest`。不自写 CSV、Excel、IFC 解析器，不封装通用 DataFrame、规则引擎或图表框架。`IfcOpenShell` 是唯一可选运行依赖，CSV 主流程、安装、测试和 Streamlit 启动不得被其缺失阻断；只有成熟库接口无法满足项目明确需求且已有测试包围时，才增加单一职责的薄适配层。

## 3. 三种技术路线与选择

| 路线 | 输入与核心 | 优点 | 主要代价/风险 | 结论 |
|---|---|---|---|---|
| A：CSV 主流程 → Streamlit → 可选 IFC（已批准） | Revit CSV 先跑通，统一 schema 和计算闭环，IFC 通过独立 reader 接入 | 4—8 周可控；易生成固定 fixture；教学可见；问题容易定位；没有 IFC 安装也能演示 | 需处理导出字段差异和编码；几何语义先受 CSV 能力限制 | **选择 A**，作为 MVP 基线 |
| B：IFC 优先 | 直接用 IfcOpenShell 解析实体和几何，再补 CSV | 语义完整、可接近开放标准 | 几何提取、版本和安装问题复杂；本科生周期内难以稳定覆盖所有模型 | 作为第二阶段适配器，不作为首个闭环 |
| C：Revit 插件优先 | C#/Revit API 中读取参数并导出结果 | 可直接获取项目参数和用户界面 | 依赖 Revit 授权/版本；开发、部署和测试环境门槛高；无法覆盖无 Revit 用户 | 非目标；仅保留未来集成边界 |

选择 A 的决策依据是“先证明数据—规则—报告闭环，再扩大输入面”。只要标准 DataFrame 和测试 fixture 稳定，B 可作为替换 reader 加入，不需要重写计算和报告；C 则需要另立项目。

## 4. 模块边界与依赖

推荐包结构（首批文件清单见第 10 节）如下。箭头表示允许的调用方向，禁止 UI 反向注入业务规则。

```text
configs + schema
       ↓
csv_reader / ifc_reader
       ↓
data_cleaner → quantity_calculator → cost_calculator → quality_checker
                       ↓                                    ↓
manual validation → validation                        PipelineArtifacts
                       └────────────────────────────────────┘
                                      ↓
                     report_generator / charts / Streamlit

scripts 与 Streamlit 只调用 pipeline；pipeline 负责按上述顺序编排。
```

| 模块 | 责任边界 | 输入/输出 | 允许依赖 |
|---|---|---|---|
| `src/schema.py` | 列名、数据类型、枚举、状态和版本；提供标准 DataFrame 契约校验 | 配置/原始表 → 标准列定义与校验结果 | 标准库、pandas |
| `src/config_loader.py` | 读取并严格校验带版本号的映射、规则和单价配置 | 路径 → 不可变配置对象 | pathlib、json、dataclasses、pandas |
| `src/csv_reader.py` | 编码尝试、表头识别、原始行号保留、别名初步映射 | CSV → 原始 DataFrame + 读取诊断 | pandas、logging |
| `src/ifc_reader.py` | 可选 IfcOpenShell 薄适配器；提取六类实体的 GUID、名称、类型、楼层、材料、属性集和 Base Quantities | IFC → 与 CSV 相同的原始字段集合 + 诊断 | IfcOpenShell（可选）、logging |
| `src/data_cleaner.py` | 标准化字段、单位、ID、空值和原始值留痕；记录重复后只移除完全重复行 | 原始表 → 清洗表 + 清洗事件 | pandas、schema、config |
| `src/quantity_calculator.py` | 按显式优先级选择来源、补算缺失工程量并分类汇总 | 清洗表 → 含 quantity 的表 + 楼层/类别/材料/类型汇总 | pandas、schema、config |
| `src/cost_calculator.py` | 确定性匹配教学单价和计算 total_cost，禁止把缺价当 0 | 计量表 → 计价表 + 分楼层/构件/材料费用汇总 | pandas、config |
| `src/quality_checker.py` | 14 类规则、严重程度、质量状态聚合和元素定位 | 计价表 + 诊断 → 质量问题表/摘要 | pandas、schema、config |
| `src/validation.py` | 对比自动值与人工值，计算绝对/相对/平均/最大及分类型误差 | 自动汇总 + 人工抽查表 → 误差明细与摘要 | pandas、logging |
| `src/report_generator.py` | 八个必备工作表的 Excel、格式、元数据和免责声明 | 流水线结果 → Excel 文件或内存字节 | pandas、openpyxl、pathlib |
| `src/pipeline.py` | 编排读取、清洗、计算、计价、质检和复核，统一错误与日志 | 配置 + 输入 → `PipelineArtifacts` | 所有业务模块，不依赖 Streamlit |
| `app/utils/charts.py` | 从结果生成七类 Plotly 图表并处理空数据 | 标准表 + 各类摘要 → Plotly Figure | Plotly |
| `app/streamlit_app.py` 与 `app/pages/` | CSV/IFC 上传、筛选、查询、展示和下载 | `PipelineArtifacts` → 六页面界面 | Streamlit、charts、pipeline |

依赖规则：`schema/config_loader` 不依赖任何业务上层；`pipeline` 是唯一业务编排者；业务模块不得直接读写 Streamlit 状态；UI 不得绕过 pipeline 调用 calculator；可选 IfcOpenShell 必须延迟导入并捕获缺包异常。输入结构校验由 `schema.py` 和 `config_loader.py` 承担，`validation.py` 专用于人工复核，二者不得混用。

配置职责固定且不互相覆盖：`configs/field_mapping.json` 管字段别名，`configs/category_mapping.json` 管构件类别，`configs/level_mapping.json` 管楼层，`configs/material_mapping.json` 管材料，`configs/naming_rules.json` 管命名，`configs/quality_rules.json` 管质量阈值与严重程度，`configs/sample_unit_prices.csv` 管教学单价。每个 JSON 文件含 `config_version`，未知键和重复映射在启动时直接报错，不由业务模块隐式解释。

## 5. 标准 DataFrame 与计量约定

### 5.1 必备列

标准 DataFrame 至少包含以下列，类型和可空性在 `schema` 中固定：

| 列 | 类型/可空 | 语义 |
|---|---|---|
| `element_id` | string，可空 | Revit 或 IFC 来源系统的元素 ID；缺失时保持空值并产生质量问题，不生成伪造 ID |
| `guid` | string，可空 | IFC/Revit 全局 ID；格式规范化后保留原值备查 |
| `source` | string，不可空 | `CSV` 或 `IFC`；具体文件名另存 `source_file` |
| `ifc_class` | enum/字符串，不可空 | `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 等 |
| `category` | string，不可空 | 面向统计和单价匹配的分类 |
| `element_name` | string，可空 | 构件/族名称 |
| `type_name` | string，可空 | 类型名称 |
| `level` | string，可空 | 标准化为`一层`、`二层`、`三层`；缺失时为空并进入质量问题表 |
| `material` | string，可空 | 材料名称 |
| `length_m` | float，可空 | 长度，统一为米 |
| `area_m2` | float，可空 | 面积，统一为平方米 |
| `volume_m3` | float，可空 | 体积，统一为立方米 |
| `quantity` | float，可空 | **主要计价工程量**，与 `unit` 成对；不可用行数替代 |
| `unit` | enum，可空 | `m`、`m²`、`m³`、`个`、`樘` 等统一计价单位；无法识别时为空并报错 |
| `unit_price` | float，可空 | 教学示例单价，单位为元/`unit` |
| `total_cost` | float，可空 | `quantity × unit_price`；任一缺失则为空 |
| `quantity_source` | enum，不可空 | 只允许 `IFC BaseQuantity`、`Parameter Calculation`、`CSV Schedule`、`Missing` |
| `quality_status` | enum，不可空 | 只允许 `Pass`、`Warning`、`Error` |

可增加但不替代上述列：`width_m`、`height_m`、`thickness_m`、`raw_unit`、`raw_row_number`、`duplicate_guid_count`、`raw_element_id`、`source_file`、`mapping_notes`。

### 5.2 计量规则

- `quantity` 是主要计价工程量；构件计数优先使用有效 `element_id`，缺失时使用有效 GUID，二者都缺失的记录进入质量问题并从“可信唯一构件数”中排除。门窗“个/樘”同样按有效唯一标识计数，不按输入行数计数。
- 来源选择按“有效 IFC Base Quantities → 有效 CSV 明细表工程量 → 参数计算 → Missing”执行。参数计算公式仅限：矩形梁/柱体积 `length_m × width_m × height_m`、板体积 `area_m2 × thickness_m`、墙体积 `length_m × height_m × thickness_m`；门/窗按唯一 ID 计数。公式所需字段和适用类别在配置中显式列出，不写死在 UI。
- 所有换算保留原始单位 `raw_unit`，计算时统一 SI 单位；四舍五入只在报告展示层进行，内部计算保留足够精度。
- 负数、零尺寸、无单位或多个冲突候选值时不强行选择；无法计算时置 `quantity_source=Missing`，并产生带规则 ID 的 `Warning` 或 `Error`。问题表的 `Info`/`Warning` 都聚合为元素级 `quality_status=Warning`，任一 `Error` 聚合为 `quality_status=Error`，无问题为 `Pass`。

## 6. 数据流及错误处理

1. **准备配置**：`config_loader` 读取并校验分项配置文件的版本、字段映射、单位、单价、阈值和输出目录；配置错误属于致命错误，命令行脚本返回非零码。
2. **读取输入**：reader 记录文件路径、大小、编码、表头和行数；每行保留 `raw_row_number`。文件不存在、无法解码、表头为空或格式非表格时停止本次运行并给出修复建议。
3. **字段映射**：将中英文别名映射为标准列，冲突别名记录 `mapping_notes`；未知列保留但不参与计算；必需列全部缺失时停止，部分缺失则逐行产生 `Warning` 或 `Error`。
4. **清洗与标准化**：按字段级策略转换数字、单位、枚举、GUID 和空值；行级错误写入清洗事件并继续处理其余行。禁止静默删除；原始行号和错误码进入 `数据质量问题` 工作表。
5. **计算工程量和造价**：计算器只消费已通过 schema 的列；每个结果带来源和诊断。异常公式、溢出或单价解析错误隔离为元素级 `Error`，不影响其他元素。
6. **质量检查与聚合**：所有规则运行完后，将问题严重程度 `Info`/`Warning`/`Error` 映射为元素状态 `Pass`/`Warning`/`Error`，并生成总体计数；质量检查本身异常视为流水线错误并记录堆栈到日志。
7. **报告与可视化**：仅对通过输出结构校验的结果写八工作表 Excel 和约定 CSV；文件写入采用临时文件后原子替换，避免半成品。图表生成失败不应丢失数据报告，页面显示降级提示。
8. **运行结束**：`PipelineResult` 包含 `run_id`、输入摘要、行数、状态计数、输出路径、警告数和错误数。日志使用 `logging`，默认 INFO，`--verbose` 开启 DEBUG；不记录 BIM 文件中的敏感路径之外的隐私信息。

错误分级：配置/输入结构错误为致命；单行可恢复问题写入严重程度为 `Error` 的问题记录并继续；可疑值为 `Info` 或 `Warning`；可选 IFC 依赖缺失只在选择 IFC 时阻止该分支，CSV 分支仍可运行。专用脚本使用 0（完成且无 Error）、2（报告已生成但存在数据质量 Error）、1（流水线/配置失败）三类退出码，含义写入用户指南。

## 7. 测试策略

- **规格要求的单元测试**：逐项验证 CSV 编码读取、字段名称映射、单位转换、完全重复数据删除、工程量分组汇总、示例费用计算、缺失字段检查、重复 GUID 检查、零工程量检查、相对误差计算、人工值为零、空 DataFrame，共 12 个必测行为。六类补算公式和 14 类质量规则再分别使用最小 DataFrame 覆盖。
- **数据生成器测试**：连续两次生成的文件哈希一致，行数为 240，覆盖三层和六类构件，并精确核对七类预置异常数量；测试读取生成结果而非相信日志。
- **契约测试**：reader 输出可直接交给 cleaner；cleaner 输出满足标准 schema；calculator 不改变元素主键；reporter 生成八个固定工作表和必备列。pytest fixture 固定列顺序、随机种子和配置版本。
- **端到端测试**：对固定种子模拟 CSV 跑完整 pipeline，核对行数、三层/六类覆盖、四种 `quantity_source`、质量摘要和导出文件可读性；不把未验证的金额、误差或性能值写成项目事实。
- **负向与边界测试**：UTF-8-SIG、UTF-8、GBK、空文件、重复表头、未知列、缺 ID、重复 GUID、负尺寸、混合单位、缺单价、全坏行、IFC 缺包、输出目录不可写均有明确预期结果和可读错误。
- **Excel 验证**：用 `openpyxl.load_workbook` 回读报告，核对八个工作表、冻结窗格、自动筛选、列宽、金额/工程量格式、异常条件格式、生成时间、数据来源和免责声明。
- **脚本与界面闭环**：在 Windows PowerShell 下运行 `generate_sample_data.py`、`run_pipeline.py`、`export_report.py`，检查退出码、日志和文件；使用 Streamlit 官方测试能力覆盖无输入、示例数据载入、筛选和下载的主要路径，人工视觉检查只作为补充，不作为功能兜底。
- **回归与覆盖**：每次合并运行全套 pytest 和相关脚本冒烟；覆盖率只用于发现遗漏，不规定未经测量的百分比目标。记录测试时间、Python 版本和实际结果。

## 8. 6 周主计划 + 2 周缓冲

| 周次 | 交付与验收 | 并行工作边界 |
|---|---|---|
| 第 1 周 | 确认 schema、分项 JSON/CSV 配置、模拟数据规格和三个专用脚本；完成字段映射表、风险清单和测试 fixture 框架 | 数据样例与 schema；测试骨架与日志约定 |
| 第 2 周 | 完成 csv_reader、data_cleaner、≥200 条固定种子数据；通过编码/映射/单位负向测试 | reader/cleaner 与测试可并行，接口以 schema 为准 |
| 第 3 周 | 完成 quantity_calculator、cost_calculator、14 类质量规则和人工误差分析；产出明细与各类汇总 DataFrame | 公式/单价、质量规则、误差分析可在稳定 schema 下并行 |
| 第 4 周 | 完成 report_generator 八工作表和 CSV 导出；跑通三个专用脚本 | 报告格式和流水线编排并行，端到端 fixture 每日回归 |
| 第 5 周 | 完成 Streamlit 六页面、七类图表、上传/筛选/查询/下载闭环 | 页面按稳定的 `PipelineArtifacts` 并行开发，不复制业务逻辑 |
| 第 6 周 | 完成 IFC 六类构件薄适配器、集成验收、README 和用户/BIM 建模指南；执行全套 pytest、脚本冒烟和界面自动化检查 | IFC 分支不得阻断 CSV；发现跨层重复逻辑时先重构再验收 |
| 第 7 周（缓冲） | 处理集成缺陷、编码/路径兼容和安装问题；不得借机扩大非目标 | 只做已记录缺陷和可验证的稳定性修复 |
| 第 8 周（缓冲） | 复跑验收、整理演示脚本和已知限制；若前面无缺陷则用于 IFC 可选适配器加固 | IFC 仍不可阻塞 CSV 主流程 |

## 9. 风险、解决方案与需准备的 BIM 数据

| 风险 | 影响 | 解决方案/触发条件 |
|---|---|---|
| Revit 导出列名、编码和单位不一致 | 映射失败或错误计量 | JSON 别名与显式编码策略；保留原始列和行号；未知/冲突映射产生 `Warning` 或 `Error` |
| 缺少稳定 ID 或 GUID 重复 | 重复计数、无法追溯 | 保留空 ID，不伪造来源标识；使用来源文件和原始行号定位，`duplicate_guid_count` 触发复核并从可信统计中排除歧义记录 |
| 几何量缺失/口径不同 | 公式不可用或重复扣减 | 显式 `quantity_source` 与优先级；缺量不填零；人工复核表确认 |
| 类别与材料/单价不匹配 | 金额误导 | 教学单价小而明确；无匹配时 total_cost 为空并报警 |
| IfcOpenShell 安装或 IFC 版本问题 | 可选分支阻塞 | 延迟导入、版本记录和最小实体集；CSV 运行不依赖 IFC |
| Windows 路径、权限、Excel 锁定 | 导出失败 | `pathlib`、临时文件原子替换、可写目录检查和可操作提示 |
| 数据量增大导致页面缓慢 | 交互体验下降 | MVP 先限制单次文件大小并显示行数；计算在 pipeline 一次完成，必要时再分块优化 |
| 学生团队并行改接口 | 集成冲突 | 稳定 schema/配置契约、每周合并回归、重大变更先重构并记录决策 |

提交给开发者的 BIM 数据准备清单：

1. 从一个可公开教学使用的 Revit 模型导出 CSV，包含 `Element ID`、GUID（如有）、类别、族/类型、楼层、材料、长/宽/高/厚、面积、体积、数量和单位；每行保留原始导出行号。
2. 数据中明确原始楼层命名，并能映射为`一层`、`二层`、`三层`；每类至少准备数十个元素，覆盖梁、柱、板、墙、门、窗六类。
3. 记录导出软件与版本、项目单位制、是否包含链接模型、明细表过滤条件和面积/体积口径；不要混入个人或受限项目信息。
4. 准备一份人工抽样复核表（至少覆盖每类和每层的元素），由有 BIM 经验的人给出长度/面积/体积或数量及复核日期。
5. 若提供 IFC，确认文件能在 IfcOpenShell 读取，至少包含 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 的 GUID、Name、楼层关系和可用尺寸/几何属性；同时保留原始 IFC 版本和导出设置。

## 10. 下一阶段首批文件清单

下一阶段只创建基础工程、配置和可验证的模拟数据，不提前铺开全部业务模块：

```text
bim-quantity-python/
├─ README.md
├─ LICENSE
├─ requirements.txt
├─ requirements-ifc.txt
├─ pyproject.toml
├─ .gitignore
├─ .env.example
├─ src/
│  ├─ __init__.py
│  ├─ schema.py
│  └─ config_loader.py
├─ configs/
│  ├─ field_mapping.json
│  ├─ category_mapping.json
│  ├─ level_mapping.json
│  ├─ material_mapping.json
│  ├─ naming_rules.json
│  ├─ quality_rules.json
│  └─ sample_unit_prices.csv
├─ scripts/
│  └─ generate_sample_data.py
├─ data/
│  ├─ sample/
│  │  ├─ sample_elements.csv
│  │  ├─ sample_manual_validation.csv
│  │  └─ README.md
│  ├─ raw/.gitkeep
│  └─ processed/.gitkeep
├─ outputs/
│  ├─ excel/.gitkeep
│  ├─ charts/.gitkeep
│  └─ reports/.gitkeep
├─ tests/
│  ├─ test_config_loader.py
│  └─ test_sample_data.py
├─ docs/
│  ├─ project_design.md
│  ├─ data_dictionary.md
│  └─ technical_route.md
└─ assets/README.md
```

`requirements.txt` 安装 CSV、Excel、图表、Streamlit 和 pytest 所需成熟库，保证附件中的基础安装命令可直接运行；`requirements-ifc.txt` 只增加 IfcOpenShell。首批验收以实际测试为准：配置可加载、固定种子两次生成一致、240 行数据覆盖三层/六类并具有约定异常。通过后再按第 8 节顺序实现 CSV 主流程、Streamlit 和 IFC。
