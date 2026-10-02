# 阶段 3.5 Task 1+2 Reader 报告

## 交付

- `src/ifc_reader.py`：延迟导入 `ifcopenshell`，提供 `IfcReaderUnavailable`、`IfcReaderError`、冻结的 `IfcReadResult`，并读取六类受支持实体。
- `tests/test_ifc_reader.py`：覆盖可选依赖、路径错误、冻结结果、六类实体、字段排序、basename/raw row、坏量与坏实体续读。
- `tests/fixtures/fake_ifc.py`：最小 fake IfcOpenShell module/model/entity graph，无需真实 IFC 二进制或安装可选依赖。
- `tests/test_config_loader.py`：移除已经过时的 `src/ifc_reader.py` 禁止存在断言；`import src` 仍不加载 IfcOpenShell。

## 诊断与边界

无单位或无法识别单位时不按类别猜测，受影响的 SI 工程量与 `quantity_source` 保持缺失；异常实体保留行标记为 `quantity_source=Missing`。

诊断统一使用 `Error: `、`Warning: `Info: ` 前缀。未知 IFC 类、缺失 GUID/楼层、坏 Base Quantity、未知单位和多材料会保留可追溯行并记录 warning；文件路径、依赖缺失、打开失败转换为中文 reader 异常。模型在 `finally` 中调用可用的 `close`/`release`/`dispose`。
