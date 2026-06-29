"""Tests for AG Grid models and configuration.

Tests:
- ColDef, ColGroupDef, DefaultColDef serialization
- RowSelection configuration
- GridOptions with conditional field inclusion
- normalize_data() for DataFrame, dict, list inputs
- _detect_column_types() for various dtypes
- build_column_defs() with ColDef objects and dicts
- build_grid_config() main entry point
- MultiIndex column/row handling
"""

from __future__ import annotations

import json

from typing import Any

import pytest

from pydantic import ValidationError

from pywry.grid import (
    ColDef,
    ColGroupDef,
    DefaultColDef,
    GridConfig,
    GridData,
    GridOptions,
    PyWryGridContext,
    RowSelection,
    _detect_column_types,
    build_column_defs,
    build_grid_config,
    normalize_data,
    to_js_grid_config,
)


# =============================================================================
# AGGridModel Base Class Tests
# =============================================================================


class TestAGGridModel:
    """Tests for AGGridModel base class serialization."""

    def test_to_dict_uses_alias(self):
        """to_dict() uses camelCase alias when Field alias is defined."""
        # AGGridModel requires Field(alias=...) to use aliases.
        # Fields without aliases serialize with their Python names.
        # This test verifies that ColDef (which has aliases) works correctly.
        col = ColDef(field="test", header_name="My Header")
        result = col.to_dict()
        # Should have camelCase keys
        assert "headerName" in result
        assert result["headerName"] == "My Header"

    def test_to_dict_excludes_none(self):
        """to_dict() excludes None values by default."""
        col = ColDef(field="test", header_name=None)
        result = col.to_dict()
        assert "headerName" not in result


# =============================================================================
# ColDef Tests
# =============================================================================


class TestColDef:
    """Tests for ColDef column definition model."""

    def test_field_only(self):
        """Minimal ColDef with just field."""
        col = ColDef(field="myField")
        result = col.to_dict()
        assert result["field"] == "myField"
        assert "headerName" not in result

    def test_camel_case_serialization(self):
        """Python snake_case fields serialize to camelCase."""
        col = ColDef(
            field="test",
            header_name="Test Header",
            value_getter="data.x + data.y",
            value_formatter="value.toFixed(2)",
            cell_data_type="number",
            span_rows=True,
        )
        result = col.to_dict()

        assert "headerName" in result
        assert result["headerName"] == "Test Header"
        assert "valueGetter" in result
        assert result["valueGetter"] == "data.x + data.y"
        assert "valueFormatter" in result
        assert result["valueFormatter"] == "value.toFixed(2)"
        assert "cellDataType" in result
        assert result["cellDataType"] == "number"
        assert "spanRows" in result
        assert result["spanRows"] is True

        # Ensure snake_case NOT in output
        assert "header_name" not in result
        assert "value_getter" not in result
        assert "value_formatter" not in result
        assert "cell_data_type" not in result
        assert "span_rows" not in result

    def test_pinned_values(self):
        """Pinned accepts 'left' or 'right' (AG Grid v35 doesn't support bool)."""
        col_left = ColDef(field="a", pinned="left")
        assert col_left.to_dict()["pinned"] == "left"

        col_right = ColDef(field="b", pinned="right")
        assert col_right.to_dict()["pinned"] == "right"

        # Note: AG Grid v35 requires 'left' or 'right' strings, not booleans

    def test_filter_options(self):
        """Filter can be string or bool."""
        col_text = ColDef(field="a", filter="agTextColumnFilter")
        assert col_text.to_dict()["filter"] == "agTextColumnFilter"

        col_bool = ColDef(field="b", filter=True)
        assert col_bool.to_dict()["filter"] is True

    def test_width_fields(self):
        """Width, minWidth, maxWidth serialization."""
        col = ColDef(field="test", width=150, min_width=100, max_width=300)
        result = col.to_dict()
        assert result["width"] == 150
        assert result["minWidth"] == 100
        assert result["maxWidth"] == 300

    def test_checkboxes_column(self):
        """Checkboxes field for row selection column."""
        col = ColDef(field="test", checkboxes=True)
        result = col.to_dict()
        assert result["checkboxes"] is True


class TestColGroupDef:
    """Tests for ColGroupDef column group model."""

    def test_basic_group(self):
        """Column group with children."""
        group = ColGroupDef(
            header_name="My Group",
            children=[{"field": "a"}, {"field": "b"}],
        )
        result = group.to_dict()

        assert result["headerName"] == "My Group"
        assert len(result["children"]) == 2
        assert result["children"][0]["field"] == "a"

    def test_marry_children(self):
        """marryChildren keeps columns together during resize."""
        group = ColGroupDef(
            header_name="Group",
            children=[{"field": "x"}],
            marry_children=True,
        )
        result = group.to_dict()
        assert result["marryChildren"] is True


class TestDefaultColDef:
    """Tests for DefaultColDef model."""

    def test_sensible_defaults(self):
        """DefaultColDef has good defaults for UX."""
        default = DefaultColDef()
        result = default.to_dict()

        # Should be sortable, filterable, resizable
        assert result.get("sortable") is True
        assert result.get("filter") is True
        assert result.get("resizable") is True
        # floatingFilter defaults to False in the actual implementation
        assert "floatingFilter" in result


# =============================================================================
# RowSelection Tests
# =============================================================================


class TestRowSelection:
    """Tests for RowSelection configuration."""

    def test_default_is_multi_row(self):
        """Default mode is multiRow."""
        sel = RowSelection()
        result = sel.to_dict()
        assert result["mode"] == "multiRow"

    def test_single_row_mode(self):
        """Single row selection mode."""
        sel = RowSelection(mode="singleRow")
        result = sel.to_dict()
        assert result["mode"] == "singleRow"

    def test_checkboxes_enabled_by_default(self):
        """Checkboxes enabled by default for multiRow."""
        sel = RowSelection(mode="multiRow")
        result = sel.to_dict()
        assert result.get("checkboxes") is True

    def test_hide_disabled_checkboxes(self):
        """hideDisabledCheckboxes option."""
        sel = RowSelection(hide_disabled_checkboxes=True)
        result = sel.to_dict()
        assert result.get("hideDisabledCheckboxes") is True

    def test_header_checkbox(self):
        """Header checkbox for select-all."""
        sel = RowSelection(header_checkbox=True)
        result = sel.to_dict()
        assert result.get("headerCheckbox") is True

    def test_camel_case_output(self):
        """All fields serialize to camelCase."""
        sel = RowSelection(
            mode="multiRow",
            checkboxes=True,
            header_checkbox=True,
            hide_disabled_checkboxes=False,
        )
        result = sel.to_dict()

        # Check camelCase keys exist
        assert "mode" in result
        assert "checkboxes" in result
        assert "headerCheckbox" in result

        # Ensure snake_case NOT in output
        assert "header_checkbox" not in result
        assert "hide_disabled_checkboxes" not in result


# =============================================================================
# GridOptions Tests
# =============================================================================


class TestGridOptions:
    """Tests for GridOptions model."""

    def test_column_defs_required(self):
        """columnDefs is a required field."""
        opts = GridOptions(columnDefs=[{"field": "a"}])
        result = opts.to_dict()
        assert "columnDefs" in result

    def test_row_data_serialization(self):
        """rowData serializes correctly."""
        data = [{"a": 1}, {"a": 2}]
        opts = GridOptions(columnDefs=[{"field": "a"}], rowData=data)
        result = opts.to_dict()
        assert result["rowData"] == data

    def test_pagination_none_excluded(self):
        """pagination=None is excluded from output."""
        opts = GridOptions(columnDefs=[], pagination=None)
        result = opts.to_dict()
        assert "pagination" not in result

    def test_pagination_false_included(self):
        """pagination=False IS included in output."""
        opts = GridOptions(columnDefs=[], pagination=False)
        result = opts.to_dict()
        assert result["pagination"] is False

    def test_pagination_true_included(self):
        """pagination=True IS included in output."""
        opts = GridOptions(columnDefs=[], pagination=True)
        result = opts.to_dict()
        assert result["pagination"] is True

    def test_row_selection_dict(self):
        """rowSelection as dict passthrough."""
        sel = {"mode": "singleRow", "checkboxes": False}
        opts = GridOptions(columnDefs=[], rowSelection=sel)
        result = opts.to_dict()
        assert result["rowSelection"] == sel

    def test_row_model_type(self):
        """rowModelType serialization."""
        opts = GridOptions(columnDefs=[], rowModelType="infinite")
        result = opts.to_dict()
        assert result["rowModelType"] == "infinite"


# =============================================================================
# _detect_column_types Tests
# =============================================================================


class TestDetectColumnTypes:
    """Tests for _detect_column_types() function."""

    def test_returns_empty_without_pandas(self):
        """Returns empty dict if pandas not available or input isn't DataFrame."""
        result = _detect_column_types([{"a": 1}])
        assert not result

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_datetime_detection(self):
        """Detects datetime64 columns as 'dateTimeString'."""
        import pandas as pd

        df = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"])})
        result = _detect_column_types(df)
        # Implementation uses 'dateTimeString' (with Time) for full datetime
        assert result.get("timestamp") == "dateTimeString"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_numeric_detection(self):
        """Detects numeric columns as 'number'."""
        import pandas as pd

        df = pd.DataFrame({"value": [1.5, 2.5, 3.5], "count": [1, 2, 3]})
        result = _detect_column_types(df)
        assert result.get("value") == "number"
        assert result.get("count") == "number"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_boolean_detection(self):
        """Detects boolean columns as 'boolean'."""
        import pandas as pd

        df = pd.DataFrame({"active": [True, False, True]})
        result = _detect_column_types(df)
        assert result.get("active") == "boolean"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_leading_zero_string_detection(self):
        """Strings with leading zeros should be detected as 'text'."""
        import pandas as pd

        df = pd.DataFrame({"zip": ["00501", "01234", "07302"]})
        result = _detect_column_types(df)
        assert result.get("zip") == "text"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_regular_string_not_marked_as_text(self):
        """Regular strings without leading zeros are not marked as 'text'."""
        import pandas as pd

        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        result = _detect_column_types(df)
        # Regular strings should NOT have 'text' type (let AG Grid auto-detect)
        assert "name" not in result or result.get("name") != "text"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_numeric_string_with_leading_zero(self):
        """Numeric strings like '007' should be 'text' to preserve zeros."""
        import pandas as pd

        df = pd.DataFrame({"code": ["007", "042", "123"]})
        result = _detect_column_types(df)
        assert result.get("code") == "text"


# =============================================================================
# normalize_data Tests
# =============================================================================


class TestNormalizeData:
    """Tests for normalize_data() function."""

    def test_list_of_dicts(self):
        """Handles list of dicts input."""
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = normalize_data(data)

        assert isinstance(result, GridData)
        assert result.row_data == data
        assert set(result.columns) == {"a", "b"}
        assert result.total_rows == 2

    def test_dict_of_lists(self):
        """Handles dict of lists (column-oriented)."""
        data = {"x": [1, 2, 3], "y": [4, 5, 6]}
        result = normalize_data(data)

        assert result.total_rows == 3
        assert set(result.columns) == {"x", "y"}
        # Should be converted to list of dicts
        assert result.row_data[0] == {"x": 1, "y": 4}

    def test_empty_list(self):
        """Handles empty list."""
        result = normalize_data([])
        assert result.row_data == []
        assert result.columns == []
        assert result.total_rows == 0

    def test_single_row(self):
        """Handles single row dict (not in list)."""
        data = {"name": "Alice", "age": 30}
        result = normalize_data(data)
        # Should interpret as column-oriented with 1 row each
        # or as a single row - depends on implementation
        assert result is not None  # Just verify it doesn't crash

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_pandas_dataframe(self):
        """Handles pandas DataFrame."""
        import pandas as pd

        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = normalize_data(df)

        assert result.total_rows == 2
        assert set(result.columns) == {"a", "b"}
        assert len(result.row_data) == 2

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_dataframe_with_datetime(self):
        """DataFrame with datetime converts to ISO strings."""
        import pandas as pd

        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01"])})
        result = normalize_data(df)

        # Datetime should be serialized as string
        assert isinstance(result.row_data[0]["ts"], str)

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_dataframe_with_nan(self):
        """DataFrame NaN values become None."""
        import numpy as np
        import pandas as pd

        df = pd.DataFrame({"a": [1.0, np.nan, 3.0]})
        result = normalize_data(df)

        assert result.row_data[1]["a"] is None

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_multiindex_columns(self):
        """DataFrame with MultiIndex columns creates column groups."""
        import pandas as pd

        cols = pd.MultiIndex.from_tuples([("A", "x"), ("A", "y"), ("B", "z")])
        df = pd.DataFrame([[1, 2, 3]], columns=cols)
        result = normalize_data(df)

        # Should have column_groups for grouped headers
        assert result.column_groups is not None
        assert len(result.column_groups) > 0

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_multiindex_rows(self):
        """DataFrame with MultiIndex rows creates index columns."""
        import pandas as pd

        idx = pd.MultiIndex.from_tuples([("A", 1), ("A", 2), ("B", 1)])
        df = pd.DataFrame({"val": [10, 20, 30]}, index=idx)
        result = normalize_data(df)

        # Should have index_columns
        assert result.index_columns is not None
        assert len(result.index_columns) == 2  # 2-level MultiIndex


# =============================================================================
# build_column_defs Tests
# =============================================================================


class TestBuildColumnDefs:
    """Tests for build_column_defs() function."""

    def test_simple_columns(self):
        """Creates basic field definitions for column names."""
        result = build_column_defs(["a", "b", "c"], column_defs=None)

        assert len(result) == 3
        assert result[0]["field"] == "a"
        assert result[1]["field"] == "b"
        assert result[2]["field"] == "c"

    def test_custom_column_defs_as_dicts(self):
        """Accepts custom column defs as plain dicts."""
        custom = [
            {"field": "x", "headerName": "X Value"},
            {"field": "y", "width": 200},
        ]
        result = build_column_defs(["x", "y"], column_defs=custom)

        assert result == custom

    def test_custom_column_defs_as_coldef_objects(self):
        """Accepts custom column defs as ColDef objects."""
        custom = [
            ColDef(field="x", header_name="X Value"),
            ColDef(field="y", value_getter="data.y * 2"),
        ]
        result = build_column_defs(["x", "y"], column_defs=custom)

        # Should have camelCase keys from ColDef.to_dict()
        assert result[0]["field"] == "x"
        assert result[0]["headerName"] == "X Value"
        assert result[1]["valueGetter"] == "data.y * 2"

    def test_hasattr_duck_typing(self):
        """Uses hasattr() duck typing instead of isinstance()."""
        # This tests the fix for module reload issues
        # Create an object that has to_dict() but isn't actually ColDef

        class MockColDef:
            """Mock column definition for duck typing test."""

            def to_dict(self) -> dict[str, Any]:
                """Return mock column definition dict."""
                return {"field": "mock", "customKey": "value"}

        custom = [MockColDef()]
        result = build_column_defs(["mock"], column_defs=custom)

        # Should call to_dict() on the mock object
        assert result[0]["field"] == "mock"
        assert result[0]["customKey"] == "value"

    def test_index_columns_pinned_left(self):
        """Index columns are pinned left with special styling."""
        result = build_column_defs(
            ["data_col"],
            column_defs=None,
            index_columns=["idx"],
        )

        # First column should be the index
        assert result[0]["field"] == "idx"
        assert result[0]["pinned"] == "left"
        assert result[0].get("lockPosition") is True

    def test_enable_cell_span_on_index(self):
        """enable_cell_span=True adds spanRows to index columns."""
        result = build_column_defs(
            ["value"],
            column_defs=None,
            index_columns=["category"],
            enable_cell_span=True,
        )

        # Index column should have spanRows=True
        idx_col = result[0]
        assert idx_col["field"] == "category"
        assert idx_col.get("spanRows") is True

    def test_column_types_add_cell_data_type(self):
        """column_types dict adds cellDataType to columns."""
        result = build_column_defs(
            ["ts", "val"],
            column_defs=None,
            column_types={"ts": "dateString", "val": "number"},
        )

        ts_col = next(c for c in result if c["field"] == "ts")
        val_col = next(c for c in result if c["field"] == "val")

        assert ts_col["cellDataType"] == "dateString"
        assert val_col["cellDataType"] == "number"

    def test_column_groups_from_multiindex(self):
        """column_groups creates hierarchical headers."""
        groups = [
            {
                "headerName": "Group A",
                "children": [{"field": "a1"}, {"field": "a2"}],
            },
            {"field": "standalone"},
        ]
        result = build_column_defs(
            ["a1", "a2", "standalone"],
            column_defs=None,
            column_groups=groups,
        )

        # Should have group structure
        assert result[0]["headerName"] == "Group A"
        assert "children" in result[0]
        assert len(result[0]["children"]) == 2


# =============================================================================
# build_grid_config Tests
# =============================================================================


class TestBuildGridConfig:
    """Tests for build_grid_config() main entry point."""

    def test_returns_grid_config(self):
        """Returns GridConfig with options and context."""
        data = [{"a": 1}]
        result = build_grid_config(data)

        assert isinstance(result, GridConfig)
        assert isinstance(result.options, GridOptions)
        assert isinstance(result.context, PyWryGridContext)

    def test_generates_grid_id(self):
        """Auto-generates unique grid ID."""
        result = build_grid_config([{"a": 1}])
        assert result.context.grid_id.startswith("grid-")

    def test_custom_grid_id(self):
        """Uses custom grid_id when provided."""
        result = build_grid_config([{"a": 1}], grid_id="my-grid")
        assert result.context.grid_id == "my-grid"

    def test_pagination_none_default(self):
        """pagination=None by default (lets JS auto-enable)."""
        result = build_grid_config([{"a": 1}])
        # pagination should not be in the dict when None
        opts_dict = result.options.to_dict()
        assert "pagination" not in opts_dict

    def test_pagination_explicit_true(self):
        """pagination=True explicitly enables."""
        result = build_grid_config([{"a": 1}], pagination=True)
        opts_dict = result.options.to_dict()
        assert opts_dict["pagination"] is True

    def test_pagination_explicit_false(self):
        """pagination=False explicitly disables."""
        result = build_grid_config([{"a": 1}], pagination=False)
        opts_dict = result.options.to_dict()
        assert opts_dict["pagination"] is False

    def test_pagination_page_size(self):
        """paginationPageSize is configurable."""
        # pagination_page_size is only included when pagination is enabled
        result = build_grid_config([{"a": 1}], pagination=True, pagination_page_size=50)
        opts_dict = result.options.to_dict()
        assert opts_dict["paginationPageSize"] == 50

    def test_row_selection_true_default(self):
        """row_selection=True creates multiRow selection with checkboxes."""
        result = build_grid_config([{"a": 1}], row_selection=True)
        opts_dict = result.options.to_dict()

        assert "rowSelection" in opts_dict
        assert opts_dict["rowSelection"]["mode"] == "multiRow"
        assert opts_dict["rowSelection"]["checkboxes"] is True

    def test_row_selection_false(self):
        """row_selection=False disables selection."""
        result = build_grid_config([{"a": 1}], row_selection=False)
        opts_dict = result.options.to_dict()

        # False is passed explicitly to disable selection (not None which would use default)
        assert opts_dict.get("rowSelection") is False

    def test_row_selection_custom_object(self):
        """row_selection accepts RowSelection object."""
        sel = RowSelection(mode="singleRow", checkboxes=False)
        result = build_grid_config([{"a": 1}], row_selection=sel)
        opts_dict = result.options.to_dict()

        assert opts_dict["rowSelection"]["mode"] == "singleRow"
        assert opts_dict["rowSelection"]["checkboxes"] is False

    def test_dark_theme_class(self):
        """theme='dark' adds -dark suffix to theme class."""
        result = build_grid_config([{"a": 1}], theme="dark", aggrid_theme="alpine")
        assert result.context.theme_class == "ag-theme-alpine-dark"

    def test_light_theme_class(self):
        """theme='light' uses theme without -dark suffix."""
        result = build_grid_config([{"a": 1}], theme="light", aggrid_theme="alpine")
        assert result.context.theme_class == "ag-theme-alpine"

    def test_different_aggrid_themes(self):
        """Supports different AG Grid themes."""
        for theme_name in ["quartz", "alpine", "balham", "material"]:
            result = build_grid_config([{"a": 1}], aggrid_theme=theme_name)
            assert theme_name in result.context.theme_class

    def test_custom_column_defs_applied(self):
        """Custom column_defs are used in output."""
        cols = [ColDef(field="x", header_name="Custom X")]
        result = build_grid_config([{"x": 1}], column_defs=cols)
        opts_dict = result.options.to_dict()

        assert opts_dict["columnDefs"][0]["headerName"] == "Custom X"

    def test_row_model_type(self):
        """row_model_type is configurable."""
        result = build_grid_config([{"a": 1}], row_model_type="infinite")
        opts_dict = result.options.to_dict()
        assert opts_dict["rowModelType"] == "infinite"

    def test_grid_options_merge(self):
        """Additional grid_options are merged."""
        extra = {"animateRows": True, "suppressMenuHide": True}
        result = build_grid_config([{"a": 1}], grid_options=extra)
        opts_dict = result.options.to_dict()

        assert opts_dict["animateRows"] is True
        assert opts_dict["suppressMenuHide"] is True

    def test_grid_options_row_selection_no_duplicate_error(self):
        """grid_options.rowSelection is honored without duplicate kwargs error."""
        extra = {"rowSelection": {"mode": "singleRow", "checkboxes": False}}
        result = build_grid_config([{"a": 1}], grid_options=extra)
        opts_dict = result.options.to_dict()

        assert opts_dict["rowSelection"]["mode"] == "singleRow"
        assert opts_dict["rowSelection"]["checkboxes"] is False

    def test_explicit_row_selection_overrides_grid_options(self):
        """Explicit row_selection argument overrides grid_options.rowSelection."""
        extra = {"rowSelection": {"mode": "singleRow", "checkboxes": False}}
        result = build_grid_config([{"a": 1}], grid_options=extra, row_selection=True)
        opts_dict = result.options.to_dict()

        assert opts_dict["rowSelection"]["mode"] == "multiRow"
        assert opts_dict["rowSelection"]["checkboxes"] is True

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_auto_enable_cell_span_with_multiindex(self):
        """Cell span auto-enables for MultiIndex rows."""
        import pandas as pd

        idx = pd.MultiIndex.from_tuples([("A", 1), ("A", 2)])
        df = pd.DataFrame({"val": [10, 20]}, index=idx)
        result = build_grid_config(df)
        opts_dict = result.options.to_dict()

        # Should have enableCellSpan=True
        assert opts_dict.get("enableCellSpan") is True


# =============================================================================
# to_js_grid_config Tests
# =============================================================================


class TestToJsGridConfig:
    """Tests for to_js_grid_config() serialization."""

    def test_returns_dict(self):
        """Returns JSON-serializable dict."""
        config = build_grid_config([{"a": 1}])
        result = to_js_grid_config(config)

        assert isinstance(result, dict)
        # Should be JSON-serializable
        json.dumps(result)

    def test_adds_pywry_metadata_for_server_side(self):
        """Adds _pywry metadata for non-clientSide models."""
        config = build_grid_config([{"a": 1}], row_model_type="infinite")
        result = to_js_grid_config(config)

        assert "_pywry" in result
        assert "gridId" in result["_pywry"]
        assert "totalRows" in result["_pywry"]
        assert "blockSize" in result["_pywry"]

    def test_no_pywry_metadata_for_client_side(self):
        """No _pywry metadata for clientSide model."""
        config = build_grid_config([{"a": 1}], row_model_type="clientSide")
        result = to_js_grid_config(config)

        assert "_pywry" not in result


# =============================================================================
# GridConfig and Context Tests
# =============================================================================


class TestGridConfig:
    """Tests for GridConfig and PyWryGridContext."""

    def test_context_stores_grid_id(self):
        """PyWryGridContext stores grid_id."""
        ctx = PyWryGridContext(
            grid_id="test-123",
            theme_class="ag-theme-alpine-dark",
            total_rows=100,
        )
        assert ctx.grid_id == "test-123"

    def test_context_stores_truncated_rows(self):
        """PyWryGridContext tracks truncated rows."""
        ctx = PyWryGridContext(
            grid_id="test",
            theme_class="ag-theme-alpine",
            total_rows=1000,
            truncated_rows=500,
        )
        assert ctx.truncated_rows == 500


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_data(self):
        """Handles empty data gracefully."""
        result = build_grid_config([])
        assert result.context.total_rows == 0
        assert result.options.row_data == []

    def test_single_column(self):
        """Handles single column data."""
        result = build_grid_config([{"only_col": 1}])
        opts = result.options.to_dict()
        assert len(opts["columnDefs"]) == 1

    def test_unicode_column_names(self):
        """Handles unicode in column names."""
        data = [{"日本語": 1, "中文": 2, "emoji 🎉": 3}]
        result = build_grid_config(data)
        cols = [c["field"] for c in result.options.to_dict()["columnDefs"]]

        assert "日本語" in cols
        assert "中文" in cols
        assert "emoji 🎉" in cols

    def test_special_characters_in_values(self):
        """Handles special characters in cell values."""
        data = [{"text": "Line 1\nLine 2", "html": "<script>alert('xss')</script>"}]
        result = build_grid_config(data)

        # Values should be preserved
        assert result.options.row_data[0]["text"] == "Line 1\nLine 2"

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_mixed_types_in_column(self):
        """Handles columns with mixed types."""
        import pandas as pd

        df = pd.DataFrame({"mixed": [1, "two", 3.0, None]})
        result = build_grid_config(df)

        # Should not crash
        assert result.context.total_rows == 4

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_all_nan_column(self):
        """Handles column with all NaN values."""
        import numpy as np
        import pandas as pd

        df = pd.DataFrame({"empty": [np.nan, np.nan, np.nan]})
        result = build_grid_config(df)

        # Should convert NaN to None
        assert all(row["empty"] is None for row in result.options.row_data)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.skipif(
        not pytest.importorskip("pandas", reason="pandas required"),
        reason="pandas required",
    )
    def test_full_dataframe_workflow(self):
        """Complete workflow from DataFrame to JS config."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "name": ["Alice", "Bob"],
                "age": [30, 25],
                "active": [True, False],
                "created": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            }
        )

        config = build_grid_config(
            df,
            theme="dark",
            aggrid_theme="alpine",
            pagination=True,
            pagination_page_size=50,
        )

        js_config = to_js_grid_config(config)

        # Verify structure
        assert "columnDefs" in js_config
        assert "rowData" in js_config
        assert js_config["pagination"] is True
        assert js_config["paginationPageSize"] == 50
        assert len(js_config["rowData"]) == 2

        # Verify datetime serialization
        assert isinstance(js_config["rowData"][0]["created"], str)

    def test_value_getter_computed_column(self):
        """Value getter for computed columns."""
        cols = [
            ColDef(field="price"),
            ColDef(field="quantity"),
            ColDef(
                field="total",
                header_name="Total",
                value_getter="data.price * data.quantity",
            ),
        ]

        config = build_grid_config(
            [{"price": 10, "quantity": 5}],
            column_defs=cols,
        )

        js_config = to_js_grid_config(config)
        total_col = next(c for c in js_config["columnDefs"] if c["field"] == "total")

        assert total_col["headerName"] == "Total"
        assert total_col["valueGetter"] == "data.price * data.quantity"

    def test_value_formatter_custom_format(self):
        """Value formatter for custom display."""
        cols = [
            ColDef(
                field="amount",
                value_formatter="'$' + value.toFixed(2)",
            ),
        ]

        config = build_grid_config([{"amount": 1234.5}], column_defs=cols)
        js_config = to_js_grid_config(config)

        assert js_config["columnDefs"][0]["valueFormatter"] == "'$' + value.toFixed(2)"


# =============================================================================
# Row Pinning Transaction Tests (JavaScript Code Verification)
# =============================================================================


class TestRowPinningJavaScript:
    """Tests for AG Grid row pinning JavaScript implementation.

    These tests verify that the aggrid-defaults.js file contains the correct
    implementation for pin/unpin row transactions with original index restoration.
    """

    @pytest.fixture
    def aggrid_defaults_js(self) -> str:
        """Load the aggrid-defaults.js file content."""
        from pywry.assets import SRC_DIR

        js_path = SRC_DIR / "aggrid-defaults.js"
        return js_path.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Pin Row Tests - Transaction from main grid to pinned section
    # -------------------------------------------------------------------------

    def test_pin_to_top_stores_original_index(self, aggrid_defaults_js: str):
        """Pin to Top stores original index for later restoration."""
        # Verify that pinning stores the original row index
        assert "data._pywryOriginalIndex = node.rowIndex" in aggrid_defaults_js

    def test_pin_to_top_removes_from_main_grid(self, aggrid_defaults_js: str):
        """Pin to Top uses applyTransaction to remove row from main grid."""
        # Should remove the row from main grid before adding to pinned
        assert "applyTransaction({ remove: [data] })" in aggrid_defaults_js

    def test_pin_to_top_adds_to_pinned_array(self, aggrid_defaults_js: str):
        """Pin to Top adds row to pinnedTopRowData array."""
        # Should get current pinned rows and add new one
        assert "getGridOption('pinnedTopRowData')" in aggrid_defaults_js
        assert "pinnedTop.push(data)" in aggrid_defaults_js
        assert "setGridOption('pinnedTopRowData', pinnedTop)" in aggrid_defaults_js

    def test_pin_to_bottom_uses_correct_array(self, aggrid_defaults_js: str):
        """Pin to Bottom uses pinnedBottomRowData array."""
        assert "getGridOption('pinnedBottomRowData')" in aggrid_defaults_js
        assert "pinnedBottom.push(data)" in aggrid_defaults_js
        assert "setGridOption('pinnedBottomRowData', pinnedBottom)" in aggrid_defaults_js

    def test_pin_menu_has_submenu_structure(self, aggrid_defaults_js: str):
        """Pin Row menu shows submenu with Top and Bottom options."""
        assert "label: 'Pin Row'" in aggrid_defaults_js
        assert "label: 'Pin to Top'" in aggrid_defaults_js
        assert "label: 'Pin to Bottom'" in aggrid_defaults_js
        assert "submenu:" in aggrid_defaults_js

    # -------------------------------------------------------------------------
    # Unpin Row Tests - Transaction from pinned section back to main grid
    # -------------------------------------------------------------------------

    def test_unpin_restores_to_original_index(self, aggrid_defaults_js: str):
        """Unpin Row uses addIndex to restore row to original position."""
        # Should use applyTransaction with addIndex for position restoration
        assert "applyTransaction({ add: [data], addIndex: originalIndex })" in aggrid_defaults_js

    def test_unpin_reads_original_index(self, aggrid_defaults_js: str):
        """Unpin Row reads stored original index from row data."""
        assert "var originalIndex = data._pywryOriginalIndex" in aggrid_defaults_js

    def test_unpin_cleans_up_original_index(self, aggrid_defaults_js: str):
        """Unpin Row deletes the temporary _pywryOriginalIndex property."""
        assert "delete data._pywryOriginalIndex" in aggrid_defaults_js

    def test_unpin_handles_missing_index_gracefully(self, aggrid_defaults_js: str):
        """Unpin Row falls back to append if original index is missing."""
        # Should check if originalIndex is valid before using addIndex
        assert "typeof originalIndex === 'number'" in aggrid_defaults_js
        # Fallback to simple add without index
        assert "applyTransaction({ add: [data] })" in aggrid_defaults_js

    def test_unpin_removes_from_pinned_top(self, aggrid_defaults_js: str):
        """Unpin Row removes row from pinnedTopRowData when pinned='top'."""
        assert "pinned === 'top'" in aggrid_defaults_js
        # Filter removes the specific row from array
        assert "pinnedTop = pinnedTop.filter" in aggrid_defaults_js

    def test_unpin_removes_from_pinned_bottom(self, aggrid_defaults_js: str):
        """Unpin Row removes row from pinnedBottomRowData when pinned='bottom'."""
        assert "pinned === 'bottom'" in aggrid_defaults_js
        # Filter removes the specific row from array
        assert "pinnedBottom = pinnedBottom.filter" in aggrid_defaults_js

    def test_unpin_menu_is_simple_action(self, aggrid_defaults_js: str):
        """Unpin Row is a simple action, not a submenu."""
        assert "label: 'Unpin Row'" in aggrid_defaults_js
        # Should not have submenu for Unpin - it's a direct action

    # -------------------------------------------------------------------------
    # Context Menu State Tests
    # -------------------------------------------------------------------------

    def test_menu_shows_pin_for_unpinned_rows(self, aggrid_defaults_js: str):
        """Menu shows 'Pin Row' submenu for rows that are not pinned."""
        # The code checks if rowPinned is falsy to show Pin options
        assert "if (rowPinned)" in aggrid_defaults_js
        # else branch shows Pin Row submenu
        assert "} else {" in aggrid_defaults_js

    def test_menu_shows_unpin_for_pinned_rows(self, aggrid_defaults_js: str):
        """Menu shows 'Unpin Row' for rows that are already pinned."""
        # When rowPinned is truthy, show Unpin
        assert "// ROW IS ALREADY PINNED" in aggrid_defaults_js
        assert "// ROW IS NOT PINNED" in aggrid_defaults_js

    def test_checks_row_pinned_state(self, aggrid_defaults_js: str):
        """Menu checks rowNode.rowPinned to determine current state."""
        assert "var rowPinned = cellInfo.rowNode.rowPinned" in aggrid_defaults_js

    # -------------------------------------------------------------------------
    # Transaction Order Tests
    # -------------------------------------------------------------------------

    def test_pin_transaction_order(self, aggrid_defaults_js: str):
        """Pin operations: store index → remove from grid → add to pinned."""
        # Find the Pin to Top action and verify order
        js = aggrid_defaults_js

        # Store index should come before remove
        store_idx = js.find("data._pywryOriginalIndex = node.rowIndex")
        remove_idx = js.find("applyTransaction({ remove: [data] })")
        push_idx = js.find("pinnedTop.push(data)")

        # All should exist
        assert store_idx > 0
        assert remove_idx > 0
        assert push_idx > 0

        # Store should come before remove, remove should come before push
        # (At least in the first occurrence which is Pin to Top)
        assert store_idx < remove_idx, "Should store original index before removing"

    def test_unpin_transaction_order(self, aggrid_defaults_js: str):
        """Unpin operations: read index → remove from pinned → add to grid."""
        js = aggrid_defaults_js

        # Find the Unpin Row action section
        unpin_section_start = js.find("label: 'Unpin Row'")
        assert unpin_section_start > 0

        # Get the unpin action section
        unpin_section = js[unpin_section_start : unpin_section_start + 2000]

        # Original index should be read
        assert "var originalIndex = data._pywryOriginalIndex" in unpin_section

        # Should clean up the property
        assert "delete data._pywryOriginalIndex" in unpin_section

        # Should restore with addIndex
        assert "applyTransaction({ add: [data], addIndex: originalIndex })" in unpin_section

    # -------------------------------------------------------------------------
    # Guard Clause Tests
    # -------------------------------------------------------------------------

    def test_pin_action_has_guard_clauses(self, aggrid_defaults_js: str):
        """Pin actions have guard clauses for missing context/data."""
        assert "if (!ctx || !ctx.rowNode) return" in aggrid_defaults_js
        assert "if (!data) return" in aggrid_defaults_js

    def test_unpin_action_has_guard_clauses(self, aggrid_defaults_js: str):
        """Unpin action has guard clause for missing context/data."""
        assert "if (!ctx || !ctx.data) return" in aggrid_defaults_js


# =============================================================================
# ColDef Validation Tests
# =============================================================================


class TestInvalidGridModels:
    """Tests for Grid model validation."""

    def test_coldef_field_can_be_none(self) -> None:
        """None field is allowed (field is optional)."""
        col = ColDef(field=None)
        assert col.field is None

    def test_coldef_empty_field_allowed(self) -> None:
        """Empty string field is allowed (user's responsibility)."""
        col = ColDef(field="")
        assert col.field == ""

    def test_coldef_with_valid_field(self) -> None:
        """Valid field name works correctly."""
        col = ColDef(field="myColumn")
        assert col.field == "myColumn"

    def test_coldef_negative_width_raises(self) -> None:
        """Negative width raises validation error."""
        with pytest.raises(ValidationError):
            ColDef(field="test", width=-100)

    def test_coldef_negative_min_width_raises(self) -> None:
        """Negative min_width raises validation error."""
        with pytest.raises(ValidationError):
            ColDef(field="test", min_width=-50)

    def test_coldef_negative_max_width_raises(self) -> None:
        """Negative max_width raises validation error."""
        with pytest.raises(ValidationError):
            ColDef(field="test", max_width=-50)

    def test_coldef_zero_width_allowed(self) -> None:
        """Zero width is allowed (just not visible)."""
        col = ColDef(field="test", width=0)
        assert col.width == 0


# =============================================================================
# _serialize_value: pandas, datetime, numpy paths
# =============================================================================


class TestSerializeValue:
    """Tests for the _serialize_value helper (lines 75-76, 80-83, 91-96, 104-107)."""

    def test_pandas_isna_returns_none(self) -> None:
        """pandas NaN/NaT values are serialized as None."""
        import numpy as np

        from pywry.grid import _serialize_value

        assert _serialize_value(np.nan) is None

    def test_pandas_nat_returns_none(self) -> None:
        """pandas NaT is serialized as None."""
        import pandas as pd

        from pywry.grid import _serialize_value

        assert _serialize_value(pd.NaT) is None

    def test_isna_with_unhashable_object_falls_through(self) -> None:
        """pd.isna() that raises is caught (line 75-76)."""
        from pywry.grid import _serialize_value

        # Lists raise ValueError ("The truth value of an array..." / "Lengths must match")
        # in pd.isna, which the try/except in _serialize_value swallows.
        result = _serialize_value([1, 2, 3])
        assert result == [1, 2, 3]

    def test_pandas_timedelta_with_days(self) -> None:
        """pandas.Timedelta with days renders as 'Nd HH:MM:SS' (lines 80-82)."""
        import pandas as pd

        from pywry.grid import _serialize_value

        td = pd.Timedelta(days=2, hours=5, minutes=30, seconds=10)
        assert _serialize_value(td) == "2d 05:30:10"

    def test_pandas_timedelta_no_days(self) -> None:
        """pandas.Timedelta without days renders as 'HH:MM:SS' (line 83)."""
        import pandas as pd

        from pywry.grid import _serialize_value

        td = pd.Timedelta(hours=3, minutes=15, seconds=5)
        assert _serialize_value(td) == "03:15:05"

    def test_datetime_timedelta_with_days(self) -> None:
        """datetime.timedelta with days renders correctly (lines 91-95)."""
        import datetime

        from pywry.grid import _serialize_value

        td = datetime.timedelta(days=1, hours=4, minutes=15, seconds=20)
        # `value.days` is truthy, so 'Nd HH:MM:SS' branch is taken.
        assert _serialize_value(td) == "1d 04:15:20"

    def test_datetime_timedelta_no_days(self) -> None:
        """datetime.timedelta without days renders as 'HH:MM:SS' (line 96)."""
        import datetime

        from pywry.grid import _serialize_value

        td = datetime.timedelta(hours=2, minutes=20, seconds=5)
        assert _serialize_value(td) == "02:20:05"

    def test_numpy_scalar_uses_item(self) -> None:
        """numpy scalar types are converted via .item()."""
        import numpy as np

        from pywry.grid import _serialize_value

        result = _serialize_value(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_item_failure_returns_value(self) -> None:
        """When .item() raises, the original value is returned (lines 104-107)."""
        from pywry.grid import _serialize_value

        class WeirdScalar:
            def item(self):
                raise ValueError("nope")

        w = WeirdScalar()
        assert _serialize_value(w) is w

    def test_datetime_uses_isoformat(self) -> None:
        """datetime objects use .isoformat()."""
        import datetime

        from pywry.grid import _serialize_value

        dt = datetime.datetime(2024, 6, 15, 10, 30, 0)
        assert _serialize_value(dt) == "2024-06-15T10:30:00"


# =============================================================================
# GridOptions row_selection coercion
# =============================================================================


class TestGridOptionsRowSelectionCoercion:
    """Tests for the _coerce_row_selection field validator (lines 485, 490)."""

    def test_row_selection_with_rowselection_instance(self) -> None:
        """A RowSelection instance is coerced to its dict form (line 485)."""
        rs = RowSelection(mode="multiRow", check_boxes=True)
        opts = GridOptions(row_selection=rs)
        # Should be a dict after coercion.
        assert isinstance(opts.row_selection, dict)
        assert opts.row_selection["mode"] == "multiRow"
        assert opts.row_selection.get("checkboxes") is True

    def test_coerce_row_selection_unknown_type_passes_through(self) -> None:
        """Unknown types fall through to the final cast (line 490), exercised at the classmethod level."""
        # We exercise the validator directly because pydantic's outer type check
        # rejects unknown types — but the inner _coerce_row_selection still runs
        # in mode='before' and must return the value untouched.
        result = GridOptions._coerce_row_selection(("foo",))
        assert result == ("foo",)


# =============================================================================
# _detect_column_types: timedelta64
# =============================================================================


class TestDetectColumnTypesTimedelta:
    """timedelta64 dtype gets 'text' cell data type (line 667)."""

    def test_timedelta_column_is_text(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"diff": pd.to_timedelta(["1 days", "2 days", "3 days"])})
        types = _detect_column_types(df)
        assert types["diff"] == "text"


# =============================================================================
# _flatten_multiindex_columns / _flatten_multiindex_rows edge cases
# =============================================================================


class TestFlattenMultiindexColumns:
    """Tests for paths inside _flatten_multiindex_columns (lines 711, 726-728, 747)."""

    def test_no_columns_attribute_returns_input(self) -> None:
        """Data without .columns falls through (line 711 - first short-circuit)."""
        from pywry.grid import _flatten_multiindex_columns

        data = [{"a": 1}]
        result_data, groups = _flatten_multiindex_columns(data)
        assert result_data is data
        assert groups is None

    def test_non_tuple_column_treated_as_flat(self) -> None:
        """A column that is not a tuple uses flat-name/group/leaf=self (lines 726-728).

        We construct a custom container that exposes .columns with .nlevels > 1
        but iterates as plain strings, so we enter the loop and hit the else branch.
        """
        from pywry.grid import _flatten_multiindex_columns

        class FakeCols(list):
            nlevels = 2

        class FakeFrame:
            def __init__(self) -> None:
                self.columns = FakeCols(["a", "b"])

            def copy(self):
                # Return a shallow copy so the function can mutate .columns.
                clone = FakeFrame()
                clone.columns = FakeCols(self.columns)
                return clone

        _result_data, groups = _flatten_multiindex_columns(FakeFrame())
        # Each non-tuple column becomes its own single-child group with
        # leaf==group, which collapses to {"field": name} (line 747).
        assert groups is not None
        assert {"field": "a"} in groups
        assert {"field": "b"} in groups

    def test_single_child_group_collapses_to_field_only(self) -> None:
        """A group with one child whose headerName matches the group name collapses (line 747)."""
        import pandas as pd

        from pywry.grid import _flatten_multiindex_columns

        # MultiIndex where one group (Z) has a single child whose leaf-name
        # equals the group name 'Z' — flat_name='Z_Z', leaf='Z', group='Z'.
        cols = pd.MultiIndex.from_tuples([("Z", "Z"), ("W", "a"), ("W", "b")])
        df = pd.DataFrame([[1, 2, 3]], columns=cols)
        _, groups = _flatten_multiindex_columns(df)
        assert groups is not None
        # Z's single child collapses to {"field": "Z_Z"}.
        single = next(g for g in groups if g.get("field") == "Z_Z")
        assert single == {"field": "Z_Z"}


class TestFlattenMultiindexRows:
    """Tests for _flatten_multiindex_rows edge cases (lines 771, 791)."""

    def test_data_without_index_attribute_returns_empty(self) -> None:
        """Data without .index returns ([], []) early (line 771)."""
        from pywry.grid import _flatten_multiindex_rows

        data = [{"a": 1}]
        result_data, idx_names = _flatten_multiindex_rows(data)
        assert result_data is data
        assert idx_names == []

    def test_index_without_names_uses_single_name_fallback(self) -> None:
        """When index lacks .names, fallback to [index.name] (line 791).

        Achieved with a custom object exposing .index without .names.
        """
        from pywry.grid import _flatten_multiindex_rows

        class FakeIndex:
            name = "myidx"
            nlevels = 2  # > 1 to escape the is_default_index check

            def __iter__(self):
                yield from []

        class FakeFrame:
            index = FakeIndex()

            def reset_index(self):
                return self

        # The is_default_index check needs at least one of: name not None, names existing,
        # or nlevels > 1.  Our FakeIndex has name='myidx' so is_default_index is False.
        # But our FakeIndex has no `names` attribute, so the function falls through
        # to the else on line 791.
        _data, names = _flatten_multiindex_rows(FakeFrame())
        # Default to [index.name] -> ["myidx"]
        assert names == ["myidx"]


# =============================================================================
# normalize_data edge cases
# =============================================================================


class TestNormalizeDataEdgeCases:
    """Tests for normalize_data fallback/error branches (lines 871-877)."""

    def test_non_list_non_dict_iterable_fallback(self) -> None:
        """Non-list/non-dict iterable goes through the else branch (lines 871-873)."""
        # A tuple of dicts is not isinstance(data, list) but is iterable.
        data = ({"a": 1}, {"a": 2})
        result = normalize_data(data)
        assert result.total_rows == 2
        assert result.columns == ["a"]
        assert result.row_data == [{"a": 1}, {"a": 2}]

    def test_invalid_data_returns_empty_grid(self) -> None:
        """Data that raises during normalization yields empty rows (lines 874-877)."""

        class BadIterator:
            # Walks like a duck up to a point, then fails.
            def __iter__(self):
                raise ValueError("kaboom")

            # Not a DataFrame (no columns), not a dict, but list(...) will fail.

        result = normalize_data(BadIterator())
        assert result.total_rows == 0
        assert result.row_data == []
        assert result.columns == []


# =============================================================================
# _infer_column_types_from_values edge cases
# =============================================================================


class TestInferColumnTypesFromValues:
    """Tests for _infer_column_types_from_values branches (lines 918, 927, 933, 942)."""

    def test_empty_rows_returns_empty(self) -> None:
        """Empty row_data returns empty (line 918)."""
        from pywry.grid import _infer_column_types_from_values

        assert _infer_column_types_from_values([], ["a"]) == {}

    def test_all_none_in_column_skips(self) -> None:
        """Column with only None values is skipped (line 927)."""
        from pywry.grid import _infer_column_types_from_values

        rows = [{"a": None}, {"a": None}]
        result = _infer_column_types_from_values(rows, ["a"])
        assert "a" not in result

    def test_bool_first_value_marks_boolean(self) -> None:
        """A bool first value marks column as boolean (line 933)."""
        from pywry.grid import _infer_column_types_from_values

        rows = [{"flag": True}, {"flag": False}]
        result = _infer_column_types_from_values(rows, ["flag"])
        assert result["flag"] == "boolean"

    def test_string_with_leading_zero_marks_text(self) -> None:
        """Strings with leading zero get 'text' type (line 942)."""
        from pywry.grid import _infer_column_types_from_values

        rows = [{"code": "007"}, {"code": "0123"}]
        result = _infer_column_types_from_values(rows, ["code"])
        assert result["code"] == "text"


# =============================================================================
# _build_number_col_def: temporal patterns
# =============================================================================


class TestBuildNumberColDefTemporal:
    """Temporal-named number columns get cellDataType=False (line 986)."""

    def test_year_column_gets_cellDataType_false(self) -> None:
        from pywry.grid import _build_number_col_def

        col_def: dict[str, Any] = {"field": "year"}
        _build_number_col_def(col_def, "number")
        assert col_def["cellDataType"] is False

    def test_date_column_gets_cellDataType_false(self) -> None:
        from pywry.grid import _build_number_col_def

        col_def: dict[str, Any] = {"field": "report_date"}
        _build_number_col_def(col_def, "number")
        assert col_def["cellDataType"] is False

    def test_non_temporal_number_unchanged(self) -> None:
        from pywry.grid import _build_number_col_def

        col_def: dict[str, Any] = {"field": "price"}
        _build_number_col_def(col_def, "number")
        # No cellDataType key added for non-temporal fields.
        assert "cellDataType" not in col_def


# =============================================================================
# build_column_defs: user-supplied defs path
# =============================================================================


class TestBuildColumnDefsUserSupplied:
    """User column_defs + enable_cell_span + index_columns adds spanRows (line 1035)."""

    def test_user_coldef_in_index_gets_spanrows_when_cellspan(self) -> None:
        result = build_column_defs(
            columns=["region", "value"],
            column_defs=[ColDef(field="region"), ColDef(field="value")],
            index_columns=["region"],
            enable_cell_span=True,
        )
        region = next(c for c in result if c["field"] == "region")
        value = next(c for c in result if c["field"] == "value")
        assert region.get("spanRows") is True
        # Non-index columns are untouched.
        assert "spanRows" not in value

    def test_user_dict_in_index_gets_spanrows(self) -> None:
        result = build_column_defs(
            columns=["region", "value"],
            column_defs=[{"field": "region"}, {"field": "value"}],
            index_columns=["region"],
            enable_cell_span=True,
        )
        region = next(c for c in result if c["field"] == "region")
        assert region.get("spanRows") is True

    def test_user_coldef_no_cellspan_does_not_add_spanrows(self) -> None:
        result = build_column_defs(
            columns=["region"],
            column_defs=[ColDef(field="region")],
            index_columns=["region"],
            enable_cell_span=False,
        )
        region = next(c for c in result if c["field"] == "region")
        assert "spanRows" not in region


# =============================================================================
# build_column_defs: index columns with type hints
# =============================================================================


class TestBuildColumnDefsIndexTypes:
    """Index columns with detected types get cellDataType + filterParams (1056-1058)."""

    def test_datetime_index_gets_filter_params(self) -> None:
        result = build_column_defs(
            columns=["date", "val"],
            index_columns=["date"],
            column_types={"date": "dateTimeString"},
        )
        date_col = next(c for c in result if c["field"] == "date")
        assert date_col["cellDataType"] == "dateTimeString"
        assert date_col["filterParams"] == {"includeBlanksInEquals": True}

    def test_number_index_temporal_pattern(self) -> None:
        result = build_column_defs(
            columns=["year", "val"],
            index_columns=["year"],
            column_types={"year": "number"},
        )
        year_col = next(c for c in result if c["field"] == "year")
        assert year_col["cellDataType"] is False  # temporal -> False


# =============================================================================
# build_column_defs: column groups with types
# =============================================================================


class TestBuildColumnDefsGroupsWithTypes:
    """Column groups with child types attach cellDataType (1070-1073)."""

    def test_group_child_with_type(self) -> None:
        groups = [
            {
                "headerName": "Sales",
                "children": [
                    {"field": "Sales_2024", "headerName": "2024"},
                    {"field": "Sales_2025", "headerName": "2025"},
                ],
            }
        ]
        result = build_column_defs(
            columns=["Sales_2024", "Sales_2025"],
            column_groups=groups,
            column_types={"Sales_2024": "number"},
        )
        sales_group = next(g for g in result if g.get("headerName") == "Sales")
        c24 = next(c for c in sales_group["children"] if c["field"] == "Sales_2024")
        c25 = next(c for c in sales_group["children"] if c["field"] == "Sales_2025")
        assert c24["cellDataType"] == "number"
        # 2025 had no type -> unchanged
        assert "cellDataType" not in c25
        assert sales_group["marryChildren"] is True

    def test_group_single_field_with_type(self) -> None:
        """Single-field (collapsed) group entries with types add cellDataType (1087-1089)."""
        groups = [{"field": "amount"}]
        result = build_column_defs(
            columns=["amount"],
            column_groups=groups,
            column_types={"amount": "number"},
        )
        amount = result[0]
        # "amount" is not temporal -> cellDataType="number" should be set.
        assert amount["field"] == "amount"
        assert amount["cellDataType"] == "number"


# =============================================================================
# build_grid_config: truncation & dataset-size paths
# =============================================================================


class TestBuildGridConfigDatasetSize:
    """Tests for MAX_SAFE_ROWS / SERVER_SIDE_THRESHOLD branches (1214-1219, 1221-1225)."""

    def test_truncation_at_max_safe_rows(self, monkeypatch) -> None:
        """Datasets above MAX_SAFE_ROWS are truncated and recorded (lines 1214-1219)."""
        from pywry import grid as grid_module

        # Use a tiny threshold so we don't actually generate 100k rows.
        monkeypatch.setattr(grid_module, "MAX_SAFE_ROWS", 5)
        monkeypatch.setattr(grid_module, "SERVER_SIDE_THRESHOLD", 1)
        rows = [{"id": i} for i in range(8)]
        config = grid_module.build_grid_config(rows)
        assert config.context.total_rows == 8
        # 8 - 5 = 3 truncated rows
        assert config.context.truncated_rows == 3
        # row_data passed to AG Grid is truncated.
        assert len(config.options.row_data) == 5

    def test_server_side_threshold_warning_path(self, monkeypatch) -> None:
        """Datasets above SERVER_SIDE_THRESHOLD (but below MAX_SAFE_ROWS) hit the debug path."""
        from pywry import grid as grid_module

        monkeypatch.setattr(grid_module, "MAX_SAFE_ROWS", 1000)
        monkeypatch.setattr(grid_module, "SERVER_SIDE_THRESHOLD", 3)
        rows = [{"id": i} for i in range(5)]
        config = grid_module.build_grid_config(rows)
        # Above threshold (3) but below max (1000) -> no truncation.
        assert config.context.total_rows == 5
        assert config.context.truncated_rows == 0
        assert len(config.options.row_data) == 5


class TestBuildGridConfigRowSelection:
    """Tests for row_selection handling (lines 1237-1238, 1246)."""

    def test_row_selection_as_rowselection_instance(self) -> None:
        """A RowSelection instance is coerced into a dict via to_dict (line 1236-1237)."""
        rs = RowSelection(mode="singleRow", check_boxes=False)
        config = build_grid_config([{"a": 1}], row_selection=rs)
        assert isinstance(config.options.row_selection, dict)
        assert config.options.row_selection["mode"] == "singleRow"

    def test_row_selection_as_dict_is_passed_through(self) -> None:
        """A dict is passed through (line 1237-1238)."""
        config = build_grid_config(
            [{"a": 1}], row_selection={"mode": "multiRow", "checkboxes": True}
        )
        assert config.options.row_selection == {"mode": "multiRow", "checkboxes": True}

    def test_grid_options_snake_case_row_selection_picked_up(self) -> None:
        """A snake_case row_selection inside grid_options is consumed (line 1246)."""
        config = build_grid_config(
            [{"a": 1}],
            row_selection=False,  # explicit False so grid_options wins
            grid_options={"row_selection": {"mode": "singleRow"}},
        )
        # Should preserve the grid_options value (popped via the snake_case alias path).
        assert config.options.row_selection == {"mode": "singleRow"}


# =============================================================================
# build_grid_html
# =============================================================================


class TestBuildGridHtml:
    """Tests for build_grid_html (lines 1325-1337)."""

    def test_clientside_html_does_not_include_pywry_block(self) -> None:
        from pywry.grid import build_grid_html

        config = build_grid_config([{"a": 1}])  # clientSide by default
        html = build_grid_html(config)
        assert '<div id="myGrid"' in html
        assert "agGrid" in html
        # No _pywry IPC block for clientSide.
        assert "_pywry" not in html

    def test_infinite_model_html_embeds_pywry_metadata(self) -> None:
        """Non-clientSide row model adds _pywry metadata block (lines 1328-1333)."""
        from pywry.grid import build_grid_html

        config = build_grid_config(
            [{"a": i} for i in range(3)],
            row_model_type="infinite",
            cache_block_size=50,
        )
        html = build_grid_html(config)
        # The _pywry IPC block must reference the grid id and block size.
        assert "_pywry" in html
        assert config.context.grid_id in html
        assert "blockSize" in html
        # Theme class flows into the wrapper div.
        assert config.context.theme_class in html
