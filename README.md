# BIM 工程量分析与可视化系统

这是一个面向本科生学习、实习展示和简历作品集的 BIM 工程量分析项目。系统以统一的标准字段连接 CSV 与可选 IFC 数据，完成构件清洗、工程量计算、教学示例造价、质量检查、人工复核、汇总报表和 Streamlit 可视化。

当前支持 Windows 10/11 与 Python 3.10/3.11，默认使用 CSV；IFC reader 通过可选 IfcOpenShell 接入。所有金额、误差和样例结果均为程序演示数据，不用于正式工程造价或真实项目验收。

## 主要功能

- CSV reader：构件明细读取、字段校验、清洗和质量报告
- IFC reader：提取六类常见构件的 GUID、名称、类型、楼层、材料和可用 Base Quantities
- 工程量来源追踪、教学单价匹配、质量规则检查和人工复核
- Excel/CSV 报表导出
- Streamlit 六页看板与 Plotly 图表
- 所有结果保留来源文件名和原始行号，不记录本机绝对路径

## 环境安装

### 标准 Python venv

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Conda prefix 环境

```powershell
$ProjectRoot = (Resolve-Path ".").Path
conda create --prefix "$ProjectRoot\.venv" python=3.11 -y
& ".\.venv\python.exe" -m pip install --upgrade pip
& ".\.venv\python.exe" -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
& ".\.venv\python.exe" -m pip check
```

检查版本时使用合法的 Python 属性：`numpy.__version__` 和 `pandas.__version__`。`numpy.**version**`、`pandas.**version**` 是错误语法；NumPy 不是项目基础直接依赖。

## 快速运行

从仓库根目录执行：

```powershell
.venv\python.exe -m pip check
.venv\python.exe -m pytest -q
.venv\python.exe scripts\generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data\sample
.venv\python.exe scripts\clean_sample_data.py --input data\sample\sample_elements.csv --output-dir data\processed --report-dir outputs\reports --config-dir configs
```

固定样例使用种子 `20260804`，生成 240 行数据，覆盖 `一层`、`二层`、`三层` 和 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类构件。

脚本路径：`scripts/generate_sample_data.py`。

## Pipeline 与报表

```powershell
.venv\python.exe scripts\run_pipeline.py --input data\sample\sample_elements.csv --config-dir configs --manual data\sample\sample_manual_validation.csv --output-dir outputs\pipeline
.venv\python.exe scripts\export_report.py --input data\sample\sample_elements.csv --config-dir configs --manual data\sample\sample_manual_validation.csv --output-dir outputs\reports
```

Pipeline 会生成标准明细、质量报告和汇总文件；报表导出会生成 Excel 及六个 UTF-8-SIG CSV。退出码为 `0`（完成且无 Error）、`2`（已生成但存在质量 Error）、`1`（输入、配置或写出失败）。

## Streamlit 看板

```powershell
.venv\python.exe -m streamlit run app\streamlit_app.py
```

看板包含项目概览、工程量分析、构件查询、数据质量检查、误差分析和报表导出六个页面。输入面板支持 CSV（默认）和 IFC；选择 IFC 后上传 `.ifc` 文件，缺少可选依赖时会显示中文修复提示，CSV 分支仍可使用。

## 可选 IFC 支持

```powershell
.venv\python.exe -m pip install -r requirements-ifc.txt
.venv\python.exe scripts\inspect_ifc.py --input model.ifc --config-dir configs --output-dir outputs\ifc
```

IFC 检查命令会输出标准构件 CSV 和诊断 JSON。复杂 IFC 几何、钢筋/幕墙/机电深化、碰撞检测和 IFC 写回不在当前范围内。

## 项目结构

```text
src/                 核心 schema、reader、清洗、计算、质量和 pipeline
scripts/             样例生成、清洗、报表和 IFC 检查命令
app/                 Streamlit 入口、页面和图表工具
configs/             字段、类别、楼层、材料、质量规则和教学单价
data/sample/         固定种子教学样例
tests/               TDD 契约、回归和 AppTest
docs/                设计规格、数据字典和技术路线
```

## 免责声明

样例数据、单价、图表、误差和质量状态仅用于程序演示与教学验证。本项目单价为教学示例数据，不用于正式工程造价。系统不对真实项目的精度、完整性、性能、合规性或验收结论作出承诺。
