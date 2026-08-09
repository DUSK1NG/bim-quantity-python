# BIM 工程量基础工程（阶段 3.2）

这是一个面向本科生的 BIM 工程量基础工程，采用路线 A：先以 CSV 样例固定数据契约，再逐步扩展后续流程。当前阶段支持 Windows 10/11 与 Python 3.10/3.11。

## 安装

从仓库根目录创建环境并安装基础依赖：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Windows PowerShell：Conda prefix `.venv`

如果使用 Conda prefix 重建环境，请在仓库根目录执行下面的命令。`$ProjectRoot` 从当前项目的相对路径 `.` 解析得到；Conda prefix 环境的解释器位于 `.venv\python.exe`，不需要 `conda activate`：

```powershell
$ProjectRoot = (Resolve-Path ".").Path
conda create --prefix "$ProjectRoot\.venv" python=3.11 -y
& ".\.venv\python.exe" -m pip install --upgrade pip
& ".\.venv\python.exe" -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
& ".\.venv\python.exe" -m pip check
& ".\.venv\python.exe" scripts/generate_sample_data.py --seed 20260804 --rows 240 --config-dir configs --output-dir data/sample
& ".\.venv\python.exe" -m pytest -q
```

需要核对解释器及已安装库版本时，可运行下面的诊断示例。版本属性必须写成 `numpy.__version__` 与 `pandas.__version__`；`numpy.**version**` 和 `pandas.**version**` 是错误语法。NumPy 不是本项目的直接依赖，若环境中未安装它，跳过 NumPy 检查即可：

```powershell
& ".\.venv\python.exe" -c "import sys, pandas; print(sys.version); print('pandas', pandas.__version__); import numpy; print('numpy', numpy.__version__)"
```

若受限环境的默认临时目录权限失败，可给 pytest 增加 `--basetemp=.pytest_cache\audit`：

```powershell
& ".\.venv\python.exe" -m pytest -q --basetemp=.pytest_cache\audit
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

测试覆盖 schema、七个显式配置、固定种子输出、字段顺序、CSV reader、data cleaner、质量报告、覆盖范围、异常数量、单价匹配、人工复核样例和阶段边界。

## 运行阶段 3.1 清洗闭环

从仓库根目录运行 CSV reader 与 data cleaner：

```powershell
.venv\python.exe scripts\clean_sample_data.py --input data\sample\sample_elements.csv --output-dir data\processed --report-dir outputs\reports --config-dir configs
```

命令会生成 `data/processed/sample_elements_clean.csv` 和 `outputs/reports/sample_elements_quality_report.json`。清洗不会删除问题行；质量报告记录原始行号、规则计数、严重级别和不适用规则。报告中的金额仅为教学示例。

## 阶段 3.2 工程量、造价、质量与人工复核

阶段 3.2 已交付四个可独立测试的模块：`quantity_calculator` 按固定规则记录工程量来源，`cost_calculator` 仅匹配配置中的教学单价，`quality_checker` 执行 14 类已配置质量规则，`validation` 通过 GUID、非空 `element_id` 或 `raw_row_number` 关联人工抽查表并计算绝对/相对误差。所有结果继续沿用标准字段和原始行号追溯约定；人工值为零时相对误差留空并给出中文提示，自动值不会被人工值覆盖。

阶段 3.2 的单价和 `data/sample` 复核表仍是程序演示数据，固定免责声明为“本项目单价为教学示例数据，不用于正式工程造价。”这些模块用于演示可追溯计算与复核流程，不对任何真实工程的精度、完整性或工程适用性作出承诺。

从仓库根目录运行阶段 3.2 的专项测试和回归检查：

```powershell
.venv\python.exe -m pytest tests/test_validation.py -q --basetemp=.pytest_cache\stage32-validation-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage32-full
.venv\python.exe -m pip check
```

阶段 3.1 清洗 CLI 仍可单独回归运行，输出目录和质量报告格式保持不变：

```powershell
.venv\python.exe scripts\clean_sample_data.py --input data\sample\sample_elements.csv --output-dir data\processed --report-dir outputs\reports --config-dir configs
```

## 阶段 3.3 Pipeline 与报表导出

阶段 3.3 将 CSV reader、清洗、工程量、教学单价、质量检查和人工复核串成同一条 `src.pipeline.run_pipeline` 流程。两个专用 CLI 只负责参数、输出和退出码，不在入口中重复计算规则。可从仓库根目录运行：

```powershell
.venv\python.exe scripts\run_pipeline.py --input data\sample\sample_elements.csv --config-dir configs --manual data\sample\sample_manual_validation.csv --output-dir outputs\pipeline
.venv\python.exe scripts\export_report.py --input data\sample\sample_elements.csv --config-dir configs --manual data\sample\sample_manual_validation.csv --output-dir outputs\reports
```

`run_pipeline.py` 会在指定目录写出中间标准明细 `sample_elements_standard.csv`、质量报告 `sample_elements_quality_report.json` 和示例造价汇总 `sample_elements_summary.csv`。`export_report.py` 会写出 `sample_elements_report.xlsx` 以及六个 UTF-8-SIG CSV：`_details`、`_by_level`、`_by_category`、`_by_material`、`_cost_summary` 和 `_quality_issues`。所有来源追溯字段只保留输入文件名，不写入本机绝对路径。

Excel 固定包含以下 8 个工作表，顺序保持不变：

1. `项目概览`
2. `全部构件明细`
3. `分楼层工程量`
4. `分构件工程量`
5. `分材料工程量`
6. `示例造价汇总`
7. `数据质量问题`
8. `人工复核结果`

退出码为：`0` 表示完成且没有 `Error` 质量问题，`2` 表示文件已生成但存在 `Error`，`1` 表示输入、配置或写出失败。金额、误差和报表仅用于程序演示与教学验证；本项目单价为教学示例数据，不用于正式工程造价，也不对真实项目的精度、完整性、性能或验收结论作出承诺。

## 当前范围与后续边界

当前已交付 schema、配置加载器、确定性样例生成器、样例 CSV、CSV reader、data cleaner、阶段 3.2 工程量/造价/质量/人工复核模块、阶段 3.3 Pipeline 与 Excel/CSV 报表 CLI，以及阶段 3.4 的 Plotly 图表和 Streamlit 六页界面。

## 阶段 3.4 Streamlit 看板

从仓库根目录启动中文 Streamlit 应用：

```powershell
.venv\python.exe -m streamlit run app\streamlit_app.py
```

入口支持上传构件明细 CSV 和可选人工复核 CSV；加载后可在六个页面之间切换：项目概览、工程量分析、构件查询、数据质量检查、误差分析、报表导出。工程量分析页提供七类 Plotly 图表，报表导出页提供 Excel 和六个 UTF-8-SIG CSV 下载。页面只编排既有 PipelineArtifacts，不在界面层复制计算规则。

当前仅支持 CSV 输入；IFC reader 尚未启用，界面会明确提示“IFC 直接读取暂不可用”，不会伪造 IFC 支持。上传数据、图表、金额和误差均用于程序演示与教学验证；本项目单价为教学示例数据，不用于正式工程造价，也不对真实项目的精度、完整性、性能或验收结论作出承诺。

以下边界仍未实现，当前命令不会调用它们：

- IFC reader（IfcOpenShell 仅作为后续可选适配器依赖）。

后续阶段必须复用本阶段的标准字段、配置接口和可追溯约定；人工复核结果需要有 BIM 经验的人员解释，不能把样例金额、误差摘要或质量状态当作正式工程造价、验收结论或真实项目精度证明。
