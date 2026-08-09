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

## 使用说明

以下命令均从项目根目录执行：

```powershell
Set-Location C:\path\to\bim-quantity-python
```

如果项目路径包含空格，请使用 `Set-Location "C:\path with spaces\bim-quantity-python"`。本项目不要求激活虚拟环境，直接调用 `.venv\python.exe` 更稳定。

### 1. 创建环境并安装依赖

项目支持两种环境形式。标准 Python venv 的解释器通常位于 `.venv\Scripts\python.exe`；Conda prefix 环境的解释器位于 `.venv\python.exe`。下面的命令按当前项目使用的 Conda prefix 写法：

```powershell
$ProjectRoot = (Resolve-Path ".").Path
conda create --prefix "$ProjectRoot\.venv" python=3.11 pip -y
& ".\.venv\python.exe" -m pip install --upgrade pip
& ".\.venv\python.exe" -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
& ".\.venv\python.exe" -m pip check
```

如果使用标准 venv，则执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

检查解释器和库版本：

```powershell
.venv\python.exe --version
.venv\python.exe -c "import sys, pandas; print(sys.executable); print('pandas', pandas.__version__)"
.venv\python.exe -m pip check
```

版本属性必须写成 `numpy.__version__` 和 `pandas.__version__`；`numpy.**version**`、`pandas.**version**` 是错误语法。NumPy 不是本项目的基础直接依赖，未安装时可跳过 NumPy 检查。

### 2. 生成教学样例

```powershell
.venv\python.exe scripts\generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data\sample
```

脚本路径为 `scripts/generate_sample_data.py`。固定样例使用种子 `20260804`，生成 240 行数据，覆盖 `一层`、`二层`、`三层` 和 `IfcBeam`、`IfcColumn`、`IfcSlab`、`IfcWall`、`IfcDoor`、`IfcWindow` 六类构件。

成功后应看到：

- `data/sample/sample_elements.csv`
- `data/sample/sample_manual_validation.csv`

样例中的金额和异常是教学数据，不代表真实工程数据。

### 3. 清洗 CSV 并查看质量报告

```powershell
.venv\python.exe scripts\clean_sample_data.py `
  --input data\sample\sample_elements.csv `
  --output-dir data\processed `
  --report-dir outputs\reports `
  --config-dir configs
```

清洗不会删除问题行，会写出标准明细和质量报告。若不想使用 PowerShell 的续行符 `` ` ``，也可以写成一行：

```powershell
.venv\python.exe scripts\clean_sample_data.py --input data\sample\sample_elements.csv --output-dir data\processed --report-dir outputs\reports --config-dir configs
```

### 4. 运行 Pipeline 和导出报表

```powershell
.venv\python.exe scripts\run_pipeline.py `
  --input data\sample\sample_elements.csv `
  --config-dir configs `
  --manual data\sample\sample_manual_validation.csv `
  --output-dir outputs\pipeline

.venv\python.exe scripts\export_report.py `
  --input data\sample\sample_elements.csv `
  --config-dir configs `
  --manual data\sample\sample_manual_validation.csv `
  --output-dir outputs\reports
```

Pipeline 输出包括标准明细、质量报告和汇总 CSV；报表命令额外生成一个 Excel 文件和六个 UTF-8-SIG CSV。退出码含义如下：

| 退出码 | 含义 |
|---:|---|
| `0` | 处理完成，未发现 Error 级质量问题 |
| `2` | 文件已经生成，但存在 Error 级质量问题 |
| `1` | 输入、配置、依赖或输出目录失败 |

### 5. 启动 Streamlit 看板

```powershell
.venv\python.exe -m streamlit run app\streamlit_app.py
```

浏览器打开 Streamlit 显示的本地地址后：

1. 在左侧选择输入类型：CSV（默认）或 IFC。
2. 上传构件明细文件；如需人工复核，再上传人工复核 CSV。
3. 点击“加载数据”。
4. 使用六个页面查看概览、工程量、构件、质量、误差和报表。
5. 在“报表导出”页面下载 Excel 和 CSV 文件。

没有加载数据时，页面只显示操作提示，不会产生计算结果。IFC 缺少可选依赖时，页面会显示中文安装提示，CSV 仍然可用。

### 6. 使用可选 IFC reader

基础安装不包含 IfcOpenShell。需要读取 IFC 时执行：

```powershell
.venv\python.exe -m pip install -r requirements-ifc.txt
.venv\python.exe scripts\inspect_ifc.py `
  --input model.ifc `
  --config-dir configs `
  --output-dir outputs\ifc
```

该命令会生成标准构件 CSV 和诊断 JSON；也可以直接在 Streamlit 输入面板选择 IFC。IFC reader 只提取六类常见构件和可识别属性，不实现复杂几何、钢筋/幕墙/机电深化、碰撞检测或 IFC 写回。

### 7. 测试与验收

```powershell
.venv\python.exe -m pytest -q
.venv\python.exe -m pip check
```

受限环境如果默认临时目录不可写，可指定仓库内临时目录：

```powershell
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\audit
```

验收重点包括固定样例可复现、标准字段顺序、CSV/IFC 来源追溯、报表输出、Streamlit AppTest 和可选依赖降级行为。

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
