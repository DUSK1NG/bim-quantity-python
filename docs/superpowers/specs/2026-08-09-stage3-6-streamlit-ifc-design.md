# 阶段 3.6 Streamlit IFC 接入设计规格

## 目标

在现有六页 Streamlit 看板中增加 IFC 上传分支，同时保持 CSV 默认流程、来源追溯和可选依赖边界不变。IFC 文件经 `src.ifc_reader.read_ifc` 转换为标准 DataFrame 后，进入与 CSV 相同的 Pipeline 计算闭环。

## 关键架构

新增 `src.pipeline.run_pipeline_from_frame`，与现有 `run_pipeline` 共享清洗、工程量、造价、质量、人工复核和汇总逻辑。CSV 入口继续由 `run_pipeline` 读取；IFC 入口由 Streamlit 数据加载器调用 reader 后传入 DataFrame，禁止临时写 CSV 造成 `source=IFC` 被覆盖。

`app.utils.data.load_artifacts_from_ifc_bytes` 负责临时文件生命周期、basename、安全错误转换和可选人工复核；IfcOpenShell 仍只在 reader 内延迟导入。Streamlit 入口增加输入类型选择和对应上传控件，页面消费的仍是同一 `PipelineArtifacts`。

## 用户交互

- 输入类型：`CSV`（默认）或 `IFC`；
- CSV：沿用现有构件明细 CSV 和人工复核 CSV；
- IFC：上传 `.ifc`，可选人工复核 CSV；
- 未安装 IfcOpenShell：显示“请安装 requirements-ifc.txt；CSV 分支仍可使用”的中文提示；
- 成功后概览、查询、质量、误差和报表页面不区分输入分支，只通过来源字段显示 `IFC` 与 basename。

## 测试与非目标

TDD 覆盖 DataFrame pipeline 契约、IFC 字节加载、CSV/IFC 选择、成功/缺包/坏文件 AppTest，以及 CSV 回归。使用 fake reader/monkeypatch，不在基础测试安装 IfcOpenShell 或提交二进制 IFC。复杂 IFC 几何、Streamlit 中 IFC 报表语义扩展和 IfcOpenShell 版本兼容性不在本阶段范围内。
