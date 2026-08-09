# 阶段 3.6 Streamlit IFC 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 接入 IFC 上传分支，让 IFC reader 输出进入既有 Pipeline 与六页 Streamlit 看板，同时保留 `source=IFC` 追溯。

**Architecture:** Pipeline 增加 DataFrame 入口并复用现有计算链；数据加载器负责 CSV/IFC 两种字节边界；Streamlit 只负责输入选择、调用和错误提示。IfcOpenShell 始终延迟导入。

**Tech Stack:** Python 3.10/3.11、pandas、pytest、Streamlit AppTest、可选 IfcOpenShell。

## Global Constraints

- CSV 路径行为和现有 145 个测试不得回归。
- IFC 结果必须保留 `source=IFC`、`source_file` basename、`raw_row_number` 和标准字段顺序。
- 缺少 IfcOpenShell 只能阻止 IFC 分支，不能阻止 `import src`、CSV、Pipeline 或 Streamlit 启动。
- 不临时转换 IFC DataFrame 为 CSV，不复制计算/清洗/质量规则。

### Task 1: Pipeline DataFrame entry

**Files:** `src/pipeline.py`, `tests/test_pipeline.py`

- [ ] 先写 RED：构造含 `source=IFC` 的标准 DataFrame，断言 `run_pipeline_from_frame` 返回完整 `PipelineArtifacts`、保留 source/source_file，并拒绝缺少标准列的输入。
- [ ] 实现 `run_pipeline_from_frame(raw_frame, config_dir, source_file, manual_frame=None)`，内部复用现有阶段；让 `run_pipeline` 读取 CSV 后委托该函数。
- [ ] 运行 pipeline 专项、全量、pip check、diff-check 并提交。

### Task 2: Byte loader IFC branch

**Files:** `app/utils/data.py`, `tests/test_app_data.py`

- [ ] 先写 RED：fake `read_ifc` 成功路径、缺包/reader 错误中文提示、basename/临时目录清理和 manual CSV 传递。
- [ ] 实现 `load_artifacts_from_ifc_bytes(content, source_name, config_dir, manual_content=None)`；临时写 IFC，调用 `read_ifc` 与 `run_pipeline_from_frame`，诊断 Error 转为可操作 `DataLoadError`，缓存键保持 bytes/字符串/路径原子化。
- [ ] 运行 data/pipeline/reader 专项、全量、pip check、diff-check 并提交。

### Task 3: Streamlit input selector and AppTest

**Files:** `app/streamlit_app.py`, `tests/test_streamlit_app.py`, `README.md`

- [ ] 先写 RED：AppTest 断言 CSV/IFC 选择器、IFC 上传控件、成功状态、缺包中文错误和 CSV 回归。
- [ ] 增加输入类型 radio/selectbox；根据类型显示 `.csv` 或 `.ifc` 上传器；IFC 分支只调用 `load_artifacts_from_ifc_bytes`，异常不显示 traceback；成功状态显示来源类型和文件名。
- [ ] 更新 README 的启动说明、IFC 可选依赖安装和 CSV/IFC 边界。
- [ ] 运行 Streamlit 专项、全量、AppTest、headless smoke、3.3 CLI 回归、pip check、diff-check 并提交。

## Completion Gate

全量测试、AppTest、Streamlit 启动冒烟和既有 CLI 均通过；`source=IFC` 在 PipelineArtifacts 和页面来源信息中保持；未安装 IfcOpenShell 时 CSV 入口仍可用。
