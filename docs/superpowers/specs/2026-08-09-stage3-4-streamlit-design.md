# 阶段 3.4 Streamlit 与 Plotly 可视化设计

## 1. 目标与边界

阶段 3.4 在阶段 3.3 的 `PipelineArtifacts` 和报表生成器之上提供可演示的 Streamlit 应用。用户可以加载样例 CSV 或上传自己的 CSV，运行同一条 Pipeline，查看概览、工程量、构件查询、质量、误差和报表下载结果。

本阶段实现六个页面和七类 Plotly 图表；不实现 IFC 读取器、Revit 插件、数据库、登录权限或前端自定义组件。IFC 入口只显示“可选 IFC reader 尚未启用”的明确提示，不伪造支持。

当前运行环境已验证为 Streamlit 1.60.0、Plotly 6.9.0；实现使用当前版本的 `st.navigation`、`st.Page` 和 `streamlit.testing.v1.AppTest`。

## 2. 应用结构与状态

```text
streamlit_app.py
      ↓ st.navigation / st.Page
app/app_pages/*.py
      ↓
app/utils/data.py → src.pipeline.run_pipeline
      ↓
PipelineArtifacts
      ├─ app/utils/charts.py
      ├─ 页面筛选/查询
      └─ report_generator 下载
```

文件结构：

```text
app/
├─ streamlit_app.py
├─ app_pages/
│  ├─ overview.py
│  ├─ quantity_analysis.py
│  ├─ element_query.py
│  ├─ quality_check.py
│  ├─ error_analysis.py
│  └─ report_export.py
└─ utils/
   ├─ data.py
   └─ charts.py
```

### 2.1 共享状态

`streamlit_app.py` 只初始化页面导航和每用户 `st.session_state`：`uploaded_bytes`、`source_name`、`artifacts`、`pipeline_error`。输入处理集中在 `app/utils/data.py`：

```python
load_artifacts_from_bytes(
    content: bytes,
    source_name: str,
    config_dir: Path,
    manual_content: bytes | None = None,
) -> PipelineArtifacts
```

该函数将上传字节写入受控临时文件，调用现有 `run_pipeline`，完成后清理临时文件；样例数据通过同一函数加载。计算函数使用 `st.cache_data(ttl="15m", max_entries=20)`，筛选和查询在缓存结果上进行，不把可变 DataFrame 放入全局模块变量。

错误分为三类：无输入显示引导提示；编码/结构/Pipeline 错误显示中文修复建议；质量 Error 仍展示结果，并在页面顶部显示问题数量，不阻止下载。

## 3. 六个页面

使用 `st.navigation` 顶部导航和 `st.Page`，页面文件保持直接脚本，不使用旧版 `pages/` 自动发现。

1. **项目概览**：显示来源文件、构件数、类别数、楼层数、总面积、总体积、质量问题数和示例总价；展示免责声明和当前 IFC 不可用提示。
2. **工程量分析**：提供楼层、类别、材料筛选，展示过滤后的工程量表、楼层数量/体积图、类别占比图和材料用量图。
3. **构件查询**：通过 GUID、名称、类型、楼层、材料、类别组合筛选标准明细，显示 `source_file` 与 `raw_row_number` 追溯字段。
4. **数据质量检查**：按严重程度和规则 ID 筛选质量问题，展示问题计数、建议、行号、GUID 和来源文件；全坏行时仍显示问题表。
5. **误差分析**：显示人工复核明细、平均/最大绝对和相对误差、分类型汇总及误差图；人工值为零的记录显示留空提示。
6. **报表导出**：调用已有 `write_excel_report` 和 `write_csv_exports`，提供 Excel 和全部 CSV 下载按钮；未运行 Pipeline 时禁用下载并提示先加载数据。

每个页面只负责控件和展示，不调用 calculator，也不复制字段映射、公式、质量规则或单价匹配逻辑。

## 4. 七类 Plotly 图表

文件：`app/utils/charts.py`。每个函数接收已汇总 DataFrame 或 `PipelineArtifacts`，返回 `plotly.graph_objects.Figure`；空数据返回带中文标题和“暂无可展示数据”注释的空 Figure。

```python
fig_elements_by_level(by_level)
fig_concrete_volume_by_level(by_level)
fig_quantity_share_by_category(by_category)
fig_material_usage(by_material)
fig_cost_distribution(cost_summary)
fig_quality_issue_counts(quality_report)
fig_validation_error(validation_result)
```

图表统一设置中文标题、轴单位、图例、悬浮信息和稳定排序；不在页面中重新计算汇总。Plotly Figure 只在页面展示，不写入业务状态。

## 5. 交互与可访问性约束

- 使用 `st.container(border=True)` 分组 KPI 和结果；筛选放在侧栏或表单中；不使用空 label。
- 使用 `width="stretch"` 或默认宽度，不使用已废弃的 `use_container_width`。
- 使用 Material Symbols 图标，不依赖 emoji；页面标题和控件使用中文句式大小写。
- 页面加载顺序先渲染标题/控件，再执行缓存 Pipeline；无输入时不触发计算。
- 只展示安全的标准字段，不把临时路径、绝对路径或本机目录发送到浏览器。

## 6. 测试策略

- `tests/test_charts.py`：七个图表非空、空数据、标题/单位/排序和图例。
- `tests/test_app_data.py`：样例字节、上传 CSV、缓存结果、错误提示和临时文件清理。
- `tests/test_streamlit_app.py`：使用 `AppTest.from_file` 启动主入口，确认六个页面可导航、无输入提示、样例加载、筛选和下载按钮。
- 页面测试不重复验证业务计算；业务正确性继续由 Pipeline 和阶段 3.3 测试负责。
- 阶段末运行全量 pytest、`pip check`、Streamlit AppTest、Plotly 图表测试、两个报表 CLI 和 `git diff --check`。

阶段 3.4 的可视化只展示程序演示与教学数据，单价和误差不代表正式工程造价、结算、验收或真实项目精度。
