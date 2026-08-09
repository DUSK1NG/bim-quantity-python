# 阶段 3.5 IFC reader 设计规格

## 目标

在不改变 CSV 主流程的前提下，增加一个可选的 IfcOpenShell 薄适配器，将六类常见 IFC 构件转换为项目既有的标准字段表。适配器只负责 IFC 文件读取、属性提取和可追溯诊断；工程量计算、质量检查、造价和界面编排继续复用现有模块。

## 范围与非目标

本阶段支持 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类实体。读取以下信息：GUID、可用 element_id、Name、类型名、楼层关系、材料、属性集和可识别的 Base Quantities。实体缺少某项信息时保留缺失值并记录诊断，不伪造业务 ID、不用几何猜测替代缺失属性。

本阶段不实现自定义 IFC 解析器、复杂曲面和网格重建、钢筋翻样、幕墙深化、机电管综、洞口扣减、碰撞检测或 IFC 写回。IfcOpenShell 只放在 `requirements-ifc.txt`，基础 `requirements.txt`、CSV 流程和 Streamlit 启动均不依赖它。

## 推荐架构

新增 `src/ifc_reader.py`，保持独立薄边界：

```text
read_ifc(path, config) -> IfcReadResult
                         ├─ frame: 18 标准字段 + raw_unit/raw_row_number/source_file
                         └─ diagnostics: 可读的文件/实体级问题
```

`ifcopenshell` 必须在 `read_ifc` 内部延迟导入。缺少依赖时抛出专用 `IfcReaderUnavailable`，错误信息说明安装 `requirements-ifc.txt` 或继续使用 CSV；文件损坏、路径不存在和实体提取失败统一转换为 `IfcReaderError`，不得暴露临时路径或完整堆栈给 UI。

输出字段沿用 `src.schema.STANDARD_COLUMNS` 和已有追溯约定：

- `source` 固定为 `IFC`，`source_file` 仅保留 IFC 文件名；
- `guid` 使用 IFC 实体的 GlobalId 原值；
- `element_id` 只使用 IFC 明确提供的 ElementId/编号属性，缺失保持空值；
- `ifc_class` 保留实体类型，`category` 通过 ProjectConfig 的 IFC 映射获得；
- `raw_row_number` 使用确定性的实体遍历序号，从 1 开始；
- `quantity_source` 仅在识别到有效 Base Quantity 时写入 `IFC BaseQuantity`，否则保留 `Missing`，后续由现有 `quantity_calculator` 决定是否按参数补算；
- 输出始终补齐并按配置 `field_mapping.field_order` 排列标准字段，额外追溯列置于末尾。

## 提取规则

1. 文件打开后按配置允许的六类 IFC class 过滤；未知实体不进入明细表，但计入诊断摘要。
2. Name、ObjectType、类型关联和常见属性集按显式候选键读取；候选键不存在时返回空值，不做模糊子串推断。
3. 楼层从 `IfcRelContainedInSpatialStructure` 关系读取，缺失时保留空值并让质量规则处理。
4. 材料从 `IfcRelAssociatesMaterial` 读取单一可显示名称；多材料只保留稳定拼接名称并记录诊断。
5. Base Quantities 只接受有限非负数，并按已有标准单位映射写入 `length_m`、`area_m2`、`volume_m3`、`quantity`；负数、无穷、单位不明值保持缺失。
6. 每一行保留来源文件名与实体序号，任何单实体异常都继续读取其余实体。

## 测试策略

- TDD 先写 `tests/test_ifc_reader.py`，在没有 IfcOpenShell 的环境中验证延迟导入、缺包错误、路径错误和输出字段契约。
- 使用最小 fake IfcOpenShell 模块与 fake entity graph 测试六类实体、楼层/材料/Base Quantity、未知 class、缺失属性和坏值；不提交真实 IFC 二进制。
- 运行阶段 2、3.1、3.2、3.3、3.4 全量回归，确认 `import src`、CSV CLI、Streamlit bare import 不加载 IfcOpenShell。
- 若本机确实安装 IfcOpenShell，再增加一个非门禁 smoke：打开一个临时教学 IFC 并核对六类实体和 basename 追溯；该检查不得成为基础测试前置条件。

## 依赖与边界

`requirements-ifc.txt` 是唯一可选依赖入口。任何模块顶层都不得导入 IfcOpenShell；CSV 主流程在未安装该依赖时必须保持现有行为。阶段 3.5 首先交付独立 reader 和测试，后续再决定是否把 IFC 上传接入 Streamlit 数据入口；不得在本阶段复制 pipeline 或 calculator 逻辑。

所有 IFC 结果、诊断、示例数据和金额仅用于程序演示与教学验证；本项目单价为教学示例数据，不用于正式工程造价，也不构成真实项目精度、验收或合规结论。
