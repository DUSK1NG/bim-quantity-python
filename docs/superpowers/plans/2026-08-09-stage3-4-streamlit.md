# 阶段 3.4 Streamlit 与 Plotly 实施计划

> **For agentic workers:** 必须使用 `superpowers:subagent-driven-development` 按任务执行。每个任务使用复选框跟踪，写生产代码前先观察测试失败。

**目标：** 基于阶段 3.3 `PipelineArtifacts` 实现六个 Streamlit 页面、七类 Plotly 图表、CSV 上传和 Excel/CSV 下载。

**架构：** `app/utils/data.py` 负责缓存 Pipeline 结果，`app/utils/charts.py` 只生成 Figure，`app/streamlit_app.py` 负责导航和共享状态，六个 `app/app_pages/*.py` 只负责展示与筛选。业务规则继续由 `src.pipeline` 提供。

**技术栈：** Python 3.10/3.11、Streamlit 1.60、Plotly 6.9、pandas、pytest、streamlit.testing.v1.AppTest；不导入 IfcOpenShell，不使用 deprecated `use_container_width`，不使用自定义 CSS 或旧 `pages/` 自动发现。

## 全局约束

- 使用 `st.navigation` + `st.Page`，页面目录固定为 `app/app_pages/`。
- Pipeline 通过 `st.cache_data(ttl="15m", max_entries=20)` 缓存，页面不得复制 calculator、映射、质量规则或单价逻辑。
- 空数据返回可展示 Figure；无输入、编码错误、全坏行和 IFC 未启用必须有中文可操作提示。
- 所有追溯只保留 `source_file` 文件名和 `raw_row_number`，不得展示绝对临时路径。
- 图表统一中文标题、单位、排序和 hover 信息；页面使用 `width="stretch"` 或默认宽度。
- 阶段末必须运行全量 pytest、AppTest、图表测试、两个报表 CLI、`pip check` 和 `git diff --check`。

## 文件地图

- 创建 `app/streamlit_app.py`：导航、session state 和入口配置。
- 创建 `app/utils/data.py`：样例/上传 CSV 到 PipelineArtifacts 的缓存加载。
- 创建 `app/utils/charts.py`：七类 Plotly Figure。
- 创建 `app/app_pages/overview.py`、`quantity_analysis.py`、`element_query.py`、`quality_check.py`、`error_analysis.py`、`report_export.py`。
- 创建 `tests/test_charts.py`、`tests/test_app_data.py`、`tests/test_streamlit_app.py`。
- 修改 `README.md`：增加中文 Streamlit 启动、页面和 CSV/IFC 边界说明。

---

### Task 1：Plotly 图表工具

**Files:**

- Create: `app/utils/charts.py`
- Test: `tests/test_charts.py`

**Interfaces:**

```python
fig_elements_by_level(by_level: pd.DataFrame) -> go.Figure
fig_concrete_volume_by_level(by_level: pd.DataFrame) -> go.Figure
fig_quantity_share_by_category(by_category: pd.DataFrame) -> go.Figure
fig_material_usage(by_material: pd.DataFrame) -> go.Figure
fig_cost_distribution(cost_summary: pd.DataFrame) -> go.Figure
fig_quality_issue_counts(report: QualityReport) -> go.Figure
fig_validation_error(validation: ValidationResult) -> go.Figure
```

- [ ] **Step 1: Write the failing test**

先写固定小表和空表测试，断言 7 个函数返回 `plotly.graph_objects.Figure`，非空图包含中文标题、轴名/单位和稳定排序，空图包含“暂无可展示数据”注释且不抛异常。

运行：

```powershell
.venv\python.exe -m pytest tests/test_charts.py -q --basetemp=.pytest_cache\stage34-charts-red
```

预期：因 `app.utils.charts` 不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

仅使用输入汇总 DataFrame 和 QualityReport/ValidationResult 生成 Plotly Figure；不重新聚合工程量；数值列缺失或空数据走统一空图 helper；图例和 hover 使用中文字段。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_charts.py -q --basetemp=.pytest_cache\stage34-charts-green
```

- [ ] **Step 4: Commit**

```powershell
git add app/utils/charts.py tests/test_charts.py
git commit -m "feat: add plotly chart utilities"
```

---

### Task 2：数据加载、缓存与应用入口

**Files:**

- Create: `app/streamlit_app.py`
- Create: `app/utils/data.py`
- Test: `tests/test_app_data.py`

**Interfaces:**

```python
load_artifacts_from_bytes(
    content: bytes,
    source_name: str,
    config_dir: Path,
    manual_content: bytes | None = None,
) -> PipelineArtifacts
```

- [ ] **Step 1: Write the failing test**

先测试样例 CSV bytes 和上传 bytes 生成相同的 `PipelineArtifacts` 摘要；测试手工表可选、来源文件只保留 basename、临时文件清理；错误字节抛出带中文修复提示的 `DataLoadError`。

运行：

```powershell
.venv\python.exe -m pytest tests/test_app_data.py -q --basetemp=.pytest_cache\stage34-data-red
```

预期：因 `app.utils.data` 不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

用 `tempfile.TemporaryDirectory` 保存输入和人工 CSV，调用现有 `run_pipeline`；使用 `st.cache_data(ttl="15m", max_entries=20)` 包装可序列化的加载 helper；`streamlit_app.py` 用 `st.set_page_config`、`st.navigation`、`st.Page` 注册六页，并初始化 `st.session_state`。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_app_data.py -q --basetemp=.pytest_cache\stage34-data-green
```

确认入口导入不执行 Pipeline，不导入 IfcOpenShell。

- [ ] **Step 4: Commit**

```powershell
git add app/streamlit_app.py app/utils/data.py tests/test_app_data.py
git commit -m "feat: add streamlit data loader"
```

---

### Task 3：六个 Streamlit 页面

**Files:**

- Create: `app/app_pages/overview.py`
- Create: `app/app_pages/quantity_analysis.py`
- Create: `app/app_pages/element_query.py`
- Create: `app/app_pages/quality_check.py`
- Create: `app/app_pages/error_analysis.py`
- Create: `app/app_pages/report_export.py`

**Interfaces:**

页面只读取 `st.session_state.get("artifacts")`，无结果时显示中文引导；有结果时使用 Task1 图表和 Task2 数据加载器。

- [ ] **Step 1: Write the failing test**

先写页面静态契约测试，确认六个文件存在、每页不导入 calculator/reader、使用 `st.dataframe` 或图表、没有 `use_container_width`；再为筛选/查询 helper 写小测试，确认空筛选不会报错。

运行：

```powershell
.venv\python.exe -m pytest tests/test_streamlit_app.py -q --basetemp=.pytest_cache\stage34-pages-red
```

预期：因页面文件不存在而 RED。

- [ ] **Step 2: Write minimal implementation**

按设计实现六页：概览 KPI；工程量侧栏筛选和三图；构件组合查询；质量规则/严重度筛选和建议；误差明细/汇总和误差图；Excel/CSV 下载按钮。每页显示免责声明；IFC 只显示明确不可用提示。

- [ ] **Step 3: Verify GREEN**

```powershell
.venv\python.exe -m pytest tests/test_streamlit_app.py -q --basetemp=.pytest_cache\stage34-pages-green
```

保持页面为直接脚本，不包装 render 函数；不使用 legacy `pages/` 目录和 deprecated `use_container_width`。

- [ ] **Step 4: Commit**

```powershell
git add app/app_pages tests/test_streamlit_app.py
git commit -m "feat: add streamlit dashboard pages"
```

---

### Task 4：AppTest、启动文档与阶段回归

**Files:**

- Modify: `tests/test_streamlit_app.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

使用 `streamlit.testing.v1.AppTest.from_file("app/streamlit_app.py")` 测试：入口可启动、六个页面可导航、无输入提示、样例数据加载后出现 KPI、工程量筛选可操作、报表下载按钮存在；测试坏输入显示中文错误而非 traceback。

运行：

```powershell
.venv\python.exe -m pytest tests/test_streamlit_app.py -q --basetemp=.pytest_cache\stage34-app-red
```

预期：页面入口或交互断言失败，不能是测试语法错误。

- [ ] **Step 2: Write minimal implementation**

补齐 AppTest 所需的样例加载入口、稳定 widget key、表单提交和下载按钮；README 增加：

```powershell
.venv\python.exe -m streamlit run app\streamlit_app.py
```

同时说明六个页面、七类图表、CSV 已支持、IFC reader 尚未启用，以及完整免责声明。

- [ ] **Step 3: Verify GREEN and full regression**

```powershell
.venv\python.exe -m pytest tests/test_charts.py tests/test_app_data.py tests/test_streamlit_app.py -q --basetemp=.pytest_cache\stage34-ui-green
.venv\python.exe -m pytest -q --basetemp=.pytest_cache\stage34-full
.venv\python.exe -m pip check
```

使用 `streamlit run app/streamlit_app.py --server.headless true --server.port 8501` 做启动冒烟；运行阶段 3.3 两个 CLI、`git diff --check`，不把 Streamlit 进程留在后台。

- [ ] **Step 4: Commit**

```powershell
git add tests/test_streamlit_app.py README.md
git commit -m "feat: document streamlit dashboard"
```

---

## 计划自审

- 四项任务覆盖七类图表、缓存数据、六页导航、AppTest、上传/筛选/下载和中文文档。
- 页面不复制业务规则；IFC 不在本阶段伪造支持；无自定义 CSS、旧多页面 API 或废弃参数。
- 所有测试步骤有明确 RED、GREEN、全量回归和提交边界；计划不含未完成占位词和绝对用户路径。

