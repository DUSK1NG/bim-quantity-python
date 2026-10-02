# 开发

Python 解释器须满足 [pyproject.toml](../pyproject.toml) 的 `requires-python` 范围。在仓库根目录安装 `requirements.txt` 后，运行测试和依赖检查；Windows 的 Python UTF-8 模式确保子进程输出与读取使用相同编码：

```powershell
$env:PYTHONUTF8 = '1'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
```

一次实测输出：

```text
153 passed in 25.64s
No broken requirements found.
```

测试覆盖数据读取、清洗、计算、报表、Streamlit 页面及 IFC reader。需要 IFC 依赖时，按 [使用指南](usage.md) 安装 `requirements-ifc.txt`。
