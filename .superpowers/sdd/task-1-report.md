# 阶段 3.5 Task 1+2 Reader 报告

## 交付

- `src/ifc_reader.py`：延迟导入 `ifcopenshell`，提供 `IfcReaderUnavailable`、`IfcReaderError`、冻结的 `IfcReadResult`，并读取六类受支持实体。
- `tests/test_ifc_reader.py`：覆盖可选依赖、路径错误、冻结结果、六类实体、字段排序、basename/raw row、坏量与坏实体续读。
- `tests/fixtures/fake_ifc.py`：最小 fake IfcOpenShell module/model/entity graph，无需真实 IFC 二进制或安装可选依赖。
- `tests/test_config_loader.py`：移除已经过时的 `src/ifc_reader.py` 禁止存在断言；`import src` 仍不加载 IfcOpenShell。

## TDD 证据

- RED：初跑 `tests/test_ifc_reader.py` 得到 `6 failed`，均为预期的 `ModuleNotFoundError: No module named 'src.ifc_reader'`。
- GREEN：reader 专项 `6 passed`；全量 `142 passed`。
- 依赖与格式：`pip check` 输出 `No broken requirements found.`；`git diff --check` 无错误。

## 诊断与边界

诊断统一使用 `Error: `、`Warning: `Info: ` 前缀。未知 IFC 类、缺失 GUID/楼层、坏 Base Quantity、未知单位和多材料会保留可追溯行并记录 warning；文件路径、依赖缺失、打开失败转换为中文 reader 异常。模型在 `finally` 中调用可用的 `close`/`release`/`dispose`。

## Concern

未使用真实 IfcOpenShell 或二进制 IFC smoke；测试只依赖 fake object protocol，这是可选依赖边界的预期限制。

