# BIM 工程量基础工程（阶段 2）

这是一个面向本科生的 BIM 工程量基础工程，采用路线 A：先以 CSV 样例固定数据契约，再逐步扩展后续流程。当前阶段支持 Windows 10/11 与 Python 3.10/3.11。

## 安装

从仓库根目录创建环境并安装基础依赖：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

基础安装不包含 IfcOpenShell。只有在后续选择 IFC 适配器阶段时，才按需安装可选依赖：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-ifc.txt
```

## 生成固定种子样例

```powershell
.venv\Scripts\python.exe scripts/generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data/sample
```

生成器会写入 `data/sample/sample_elements.csv` 与 `data/sample/sample_manual_validation.csv`。样例固定为 240 行、种子 `20260804`，覆盖 `一层`、`二层`、`三层`，以及 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类构件。样例还预置缺失材料、缺失楼层、重复 GUID、零体积、名称、单位和单价异常，便于测试从 CSV 读回后独立复核。

样例是程序演示数据，不代表真实工程项目。本项目单价为教学示例数据，不用于正式工程造价。

## 运行阶段 2 测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

测试覆盖 schema、七个显式配置、固定种子输出、字段顺序、覆盖范围、异常数量、单价匹配、人工复核样例和阶段边界。

## 当前范围与后续边界

当前只交付 schema、配置加载器、确定性样例生成器、样例 CSV、测试和基础文档。以下模块尚未实现，当前命令不会调用它们：

- CSV reader 与 data cleaner；
- 工程量/造价计算器、质量检查器、人工误差分析和 pipeline；
- Streamlit 页面与图表导出；
- IFC reader（IfcOpenShell 仅作为后续可选适配器依赖）。

后续阶段必须复用本阶段的标准字段、配置接口和可追溯约定；不要把样例金额当作正式工程造价依据。
