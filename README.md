# BIM Quantity Foundation (Phase 2)

This repository currently provides the stable schema contract for a beginner-
friendly BIM quantity workflow. It targets Python 3.10 or 3.11 on Windows 10
or 11.

## Install

From the repository root, create an environment and install the foundation
dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the schema tests

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config_loader.py -q
```

The tests cover the standard column order, quantity-source and quality-status
enums, and reporting of missing required columns. The sample-data generator is
planned for Task 3 and is not available in this task; do not run a generator
command until that task has been delivered.

IfcOpenShell is optional and is intentionally excluded from the base install.
Install `requirements-ifc.txt` only when the later IFC adapter work is needed.

Sample prices and generated rows, when added in a later task, are teaching
examples only and are not suitable for formal construction estimating.

