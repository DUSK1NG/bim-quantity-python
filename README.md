# BIM 工程量分析
本项目读取 CSV 构件明细或可选 IFC 数据，进行字段清洗、工程量与教学示例造价计算、质量检查和报表导出，并提供 Streamlit 界面。

金额、误差、样例和单价均为教学演示数据，不用于正式工程造价、结算或真实项目验收。

## 快速开始

在仓库根目录创建环境并安装依赖：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 使用

启动看板后可上传构件 CSV，或选择可选 IFC 输入；仓库样例位于 `data/sample/`。

```powershell
.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

启动输出片段：

```text
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

命令行数据处理、报表导出和可选 IFC reader 的使用说明见 [使用指南](docs/usage.md)。

## 配置

字段、类别、楼层、材料、质量规则与教学单价通过 `configs/` 配置；字段含义见[数据字典](docs/data_dictionary.md)。

## 开发

测试和依赖检查命令见 [开发说明](docs/development.md)。字段定义见 [数据字典](docs/data_dictionary.md)。

## 许可证

本项目使用 [MIT 许可证](LICENSE)。
