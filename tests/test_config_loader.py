import pandas as pd

from src.schema import (
    QUALITY_STATUSES,
    QUANTITY_SOURCES,
    STANDARD_COLUMNS,
    validate_standard_dataframe,
)


def test_schema_constants_are_exact():
    assert STANDARD_COLUMNS == (
        "element_id",
        "guid",
        "source",
        "ifc_class",
        "category",
        "element_name",
        "type_name",
        "level",
        "material",
        "length_m",
        "area_m2",
        "volume_m3",
        "quantity",
        "unit",
        "unit_price",
        "total_cost",
        "quantity_source",
        "quality_status",
    )
    assert QUANTITY_SOURCES == (
        "IFC BaseQuantity",
        "Parameter Calculation",
        "CSV Schedule",
        "Missing",
    )
    assert QUALITY_STATUSES == ("Pass", "Warning", "Error")


def test_validate_standard_dataframe_reports_missing_columns():
    result = validate_standard_dataframe(pd.DataFrame({"guid": ["x"]}))
    assert result.valid is False
    assert "element_id" in result.missing_columns
