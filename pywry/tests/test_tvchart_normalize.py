"""Tests for ``pywry/tvchart/normalize.py``.

The normalization pipeline turns DataFrames / dicts / lists into the
:class:`TVChartData` shape that the JS frontend consumes.  The tests
cover every helper plus the four input shapes (single, narrow/long,
wide, MultiIndex) end-to-end.

Pandas + NumPy are imported because real DataFrame types exercise
code paths that synthetic objects cannot reach (e.g. ``pd.isna``,
``DatetimeIndex`` extraction, MultiIndex pivoting).
"""

from __future__ import annotations

import math

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pytest

from pywry.tvchart.config import SeriesType
from pywry.tvchart.models import TVChartData, TVChartSeriesData
from pywry.tvchart.normalize import (
    _ColumnProxy,
    _ColumnsProxy,
    _FakeDtype,
    _build_narrow_multi_series,
    _build_wide_multi_series,
    _detect_ohlcv_column_types,
    _detect_symbol_column,
    _df_to_records,
    _handle_multiindex_columns,
    _has_multiindex_columns,
    _is_wide_format,
    _resolve_column,
    _resolve_ohlcv_columns,
    _serialize_bar,
    _serialize_ohlcv_value,
    _serialize_series_from_rows,
    _serialize_timestamp,
    normalize_ohlcv,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_ohlcv_rows(n: int = 5) -> list[dict[str, Any]]:
    """Synthetic daily OHLCV rows starting 2023-11-15."""
    base_time = 1_700_000_000
    return [
        {
            "time": base_time + i * 86400,
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 98.0 + i,
            "close": 103.0 + i,
            "volume": 1_000_000 + i * 10_000,
        }
        for i in range(n)
    ]


@pytest.fixture()
def ohlcv_rows() -> list[dict[str, Any]]:
    return _make_ohlcv_rows(5)


@pytest.fixture()
def line_rows() -> list[dict[str, Any]]:
    return [{"time": 1_700_000_000 + i * 86400, "close": 100.0 + i} for i in range(3)]


@pytest.fixture()
def default_ohlcv_map() -> dict[str, str | None]:
    return {
        "time": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }


@pytest.fixture()
def close_only_map() -> dict[str, str | None]:
    return {
        "time": "time",
        "open": None,
        "high": None,
        "low": None,
        "close": "close",
        "volume": None,
    }


# =============================================================================
# _serialize_timestamp
# =============================================================================


class TestSerializeTimestampPrimitives:
    """Numeric, string, and datetime inputs."""

    def test_int_passthrough(self) -> None:
        assert _serialize_timestamp(1_700_000_000) == 1_700_000_000

    def test_float_truncates_to_int(self) -> None:
        assert _serialize_timestamp(1_700_000_000.5) == 1_700_000_000

    def test_nan_returns_none(self) -> None:
        assert _serialize_timestamp(float("nan")) is None

    def test_inf_returns_none(self) -> None:
        assert _serialize_timestamp(float("inf")) is None

    def test_none_returns_none(self) -> None:
        assert _serialize_timestamp(None) is None

    def test_aware_datetime(self) -> None:
        dt = datetime(2023, 11, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert _serialize_timestamp(dt) == int(dt.timestamp())

    def test_naive_datetime_assumed_utc(self) -> None:
        dt = datetime(2023, 11, 15, 0, 0, 0)
        assert _serialize_timestamp(dt) == int(dt.replace(tzinfo=timezone.utc).timestamp())

    def test_iso_string_naive(self) -> None:
        assert _serialize_timestamp("2023-11-15T00:00:00") == int(
            datetime(2023, 11, 15, tzinfo=timezone.utc).timestamp()
        )

    def test_iso_string_with_tz(self) -> None:
        assert _serialize_timestamp("2023-11-15T00:00:00+00:00") == int(
            datetime(2023, 11, 15, tzinfo=timezone.utc).timestamp()
        )

    def test_invalid_string(self) -> None:
        assert _serialize_timestamp("not-a-date") is None


class TestSerializeTimestampNumpyAndPandas:
    """numpy / pandas scalars go through the ``item()`` branch."""

    def test_numpy_int64(self) -> None:
        assert _serialize_timestamp(np.int64(1_700_000_000)) == 1_700_000_000

    def test_numpy_float64(self) -> None:
        assert _serialize_timestamp(np.float64(1_700_000_000.5)) == 1_700_000_000

    def test_numpy_datetime64(self) -> None:
        # np.datetime64.item() returns a python datetime, which we
        # then convert via the datetime branch.
        result = _serialize_timestamp(np.datetime64("2023-11-15T00:00:00"))
        assert result is not None

    def test_pandas_timestamp(self) -> None:
        result = _serialize_timestamp(pd.Timestamp("2023-11-15T00:00:00"))
        assert result is not None


class TestSerializeTimestampFallthrough:
    """Objects with broken / unhelpful ``item`` or ``timestamp`` methods."""

    def test_object_with_failing_timestamp_returns_none(self) -> None:
        class BadTimestamp:
            def timestamp(self) -> float:
                raise OSError("fail")

        assert _serialize_timestamp(BadTimestamp()) is None

    def test_unrecognised_object_returns_none(self) -> None:
        class Foo:
            pass

        assert _serialize_timestamp(Foo()) is None

    def test_item_returning_string_falls_through(self) -> None:
        class ItemReturnsString:
            def item(self) -> str:
                return "not-useful"

        assert _serialize_timestamp(ItemReturnsString()) is None

    def test_item_raises_continues(self) -> None:
        class ItemRaises:
            def item(self) -> int:
                raise ValueError("nope")

        assert _serialize_timestamp(ItemRaises()) is None


# =============================================================================
# _serialize_ohlcv_value
# =============================================================================


class TestSerializeOHLCVValue:
    """Numeric values + the various NA / NaN sentinels."""

    def test_float_passthrough(self) -> None:
        assert _serialize_ohlcv_value(100.5) == 100.5

    def test_int_to_float(self) -> None:
        assert _serialize_ohlcv_value(100) == 100.0

    def test_nan_returns_none(self) -> None:
        assert _serialize_ohlcv_value(float("nan")) is None

    def test_inf_returns_none(self) -> None:
        assert _serialize_ohlcv_value(float("inf")) is None

    def test_none_returns_none(self) -> None:
        assert _serialize_ohlcv_value(None) is None

    def test_string_number(self) -> None:
        assert _serialize_ohlcv_value("42.5") == 42.5

    def test_invalid_string_returns_none(self) -> None:
        assert _serialize_ohlcv_value("not_a_number") is None

    def test_numpy_float(self) -> None:
        assert _serialize_ohlcv_value(np.float64(100.5)) == 100.5

    def test_numpy_nan(self) -> None:
        assert _serialize_ohlcv_value(np.float64("nan")) is None

    def test_pandas_na(self) -> None:
        assert _serialize_ohlcv_value(pd.NA) is None

    def test_decimal(self) -> None:
        assert _serialize_ohlcv_value(Decimal("42.5")) == 42.5

    def test_object_with_item_method(self) -> None:
        class HasItem:
            def item(self) -> float:
                return 7.5

        assert _serialize_ohlcv_value(HasItem()) == 7.5

    def test_object_with_failing_item(self) -> None:
        class BadItem:
            def item(self) -> float:
                raise ValueError("boom")

        assert _serialize_ohlcv_value(BadItem()) is None

    def test_object_with_item_returning_inf(self) -> None:
        class InfItem:
            def item(self) -> float:
                return math.inf

        assert _serialize_ohlcv_value(InfItem()) is None

    def test_pd_isna_raises_swallowed(self) -> None:
        # When pd.isna can't handle the object it raises — the helper must
        # swallow that and fall through to float() (which also fails here).
        class BadObject:
            def __array__(self) -> Any:
                raise ValueError("boom")

        assert _serialize_ohlcv_value(BadObject()) is None


# =============================================================================
# Column resolution helpers
# =============================================================================


class TestResolveColumn:
    def test_match_first_alias(self) -> None:
        assert _resolve_column(["time", "close"], {"time"}) == "time"

    def test_no_match_returns_none(self) -> None:
        assert _resolve_column(["foo", "bar"], {"time"}) is None


class TestResolveOHLCVColumns:
    """Maps standard / alternate column names to canonical OHLCV field names."""

    def test_standard_lowercase(self) -> None:
        cols = ["time", "open", "high", "low", "close", "volume"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "time"
        assert result["close"] == "close"
        assert result["volume"] == "volume"

    def test_capitalized(self) -> None:
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "Date"
        assert result["open"] == "Open"
        assert result["volume"] == "Volume"

    def test_single_letter(self) -> None:
        cols = ["t", "o", "h", "l", "c", "v"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "t"
        assert result["close"] == "c"

    def test_adj_close_alias(self) -> None:
        cols = ["time", "adj_close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["close"] == "adj_close"

    def test_missing_columns_resolve_to_none(self) -> None:
        cols = ["time", "close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["open"] is None
        assert result["high"] is None
        assert result["low"] is None
        assert result["volume"] is None

    def test_timestamp_alias(self) -> None:
        cols = ["Timestamp", "close"]
        result = _resolve_ohlcv_columns(cols)
        assert result["time"] == "Timestamp"


class TestDetectOHLCVColumnTypes:
    def test_no_dtypes_returns_empty(self) -> None:
        assert _detect_ohlcv_column_types([]) == {}

    def test_dataframe_dtypes(self) -> None:
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = _detect_ohlcv_column_types(df)
        assert "a" in result
        assert "int" in result["a"]


class TestDetectSymbolColumn:
    """Picks the identifier column for narrow/long-format multi-series data."""

    def test_explicit_override_found(self) -> None:
        df = pd.DataFrame({"foo": ["a", "b"], "time": [1, 2]})
        assert _detect_symbol_column(["foo", "time"], df, symbol_col="foo") == "foo"

    def test_explicit_override_missing(self) -> None:
        df = pd.DataFrame({"time": [1, 2]})
        assert _detect_symbol_column(["time"], df, symbol_col="missing") is None

    def test_low_cardinality_string_column(self) -> None:
        df = pd.DataFrame({"symbol": ["A"] * 50 + ["B"] * 50, "time": list(range(100))})
        assert _detect_symbol_column(["symbol", "time"], df) == "symbol"

    def test_high_cardinality_skipped(self) -> None:
        df = pd.DataFrame({"symbol": [f"S{i}" for i in range(100)], "time": list(range(100))})
        assert _detect_symbol_column(["symbol", "time"], df) is None

    def test_int_column_skipped(self) -> None:
        df = pd.DataFrame({"id": [1, 2, 3], "time": [10, 20, 30]})
        assert _detect_symbol_column(["id", "time"], df) is None

    def test_no_alias_columns(self) -> None:
        assert _detect_symbol_column(["foo", "bar"], None) is None

    def test_categorical_dtype_accepted(self) -> None:
        df = pd.DataFrame(
            {"symbol": pd.Categorical(["A"] * 30 + ["B"] * 30), "time": list(range(60))}
        )
        assert _detect_symbol_column(["symbol", "time"], df) == "symbol"

    def test_pandas_string_dtype(self) -> None:
        df = pd.DataFrame({"ticker": pd.array(["A"] * 20 + ["B"] * 20, dtype="string")})
        df["time"] = list(range(40))
        assert _detect_symbol_column(["ticker", "time"], df) == "ticker"

    def test_keyerror_on_column_access_skipped(self) -> None:
        class BrokenDF:
            def __len__(self) -> int:
                return 100

            def __getitem__(self, key: str) -> Any:
                raise KeyError(key)

        assert _detect_symbol_column(["name", "time"], BrokenDF()) is None


class TestIsWideFormat:
    @pytest.fixture()
    def with_time(self) -> dict[str, str | None]:
        return {
            "time": "time",
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
        }

    @pytest.fixture()
    def no_time(self) -> dict[str, str | None]:
        return {
            "time": None,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
        }

    def test_no_time_column_false(self, no_time: dict[str, str | None]) -> None:
        assert _is_wide_format(["a", "b"], no_time, None) is False

    def test_too_few_remaining_columns_false(self, with_time: dict[str, str | None]) -> None:
        assert _is_wide_format(["time", "a"], with_time, None) is False

    def test_non_numeric_remaining_false(self, with_time: dict[str, str | None]) -> None:
        df = pd.DataFrame({"time": [1, 2], "AAPL": ["x", "y"], "MSFT": ["a", "b"]})
        assert _is_wide_format(["time", "AAPL", "MSFT"], with_time, df) is False

    def test_no_dtypes_attribute_false(self, with_time: dict[str, str | None]) -> None:
        assert (
            _is_wide_format(["time", "a", "b"], with_time, {"time": [1], "a": [2], "b": [3]})
            is False
        )

    def test_numeric_wide_format_true(self, with_time: dict[str, str | None]) -> None:
        df = pd.DataFrame({"time": [1, 2, 3], "AAPL": [1.0, 2.0, 3.0], "MSFT": [4.0, 5.0, 6.0]})
        assert _is_wide_format(["time", "AAPL", "MSFT"], with_time, df) is True

    def test_keyerror_on_dtype_access_false(self, with_time: dict[str, str | None]) -> None:
        class BrokenDF:
            dtypes: dict[str, Any] = {}  # noqa: RUF012

            def __getitem__(self, _key: str) -> Any:
                raise KeyError("nope")

        assert _is_wide_format(["time", "a", "b"], with_time, BrokenDF()) is False


class TestHasMultiindexColumns:
    def test_flat_columns_false(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert _has_multiindex_columns(df) is False

    def test_multiindex_columns_true(self) -> None:
        df = pd.DataFrame(
            np.random.rand(3, 4),
            columns=pd.MultiIndex.from_tuples(
                [("Open", "AAPL"), ("Close", "AAPL"), ("Open", "MSFT"), ("Close", "MSFT")]
            ),
        )
        assert _has_multiindex_columns(df) is True

    def test_object_without_columns_false(self) -> None:
        assert _has_multiindex_columns({}) is False


# =============================================================================
# _serialize_bar / _serialize_series_from_rows
# =============================================================================


class TestSerializeBar:
    def test_full_ohlcv_bar(self, default_ohlcv_map: dict[str, str | None]) -> None:
        row = {
            "time": 1_700_000_000,
            "open": 100,
            "high": 105,
            "low": 98,
            "close": 103,
            "volume": 1_000_000,
        }
        bar, vol = _serialize_bar(row, default_ohlcv_map)
        assert bar is not None
        assert bar["open"] == 100.0
        assert bar["close"] == 103.0
        assert vol is not None
        assert vol["value"] == 1_000_000.0

    def test_line_bar_close_only(self, close_only_map: dict[str, str | None]) -> None:
        bar, vol = _serialize_bar({"time": 1_700_000_000, "close": 103}, close_only_map)
        assert bar is not None
        assert bar["value"] == 103.0
        assert "open" not in bar
        assert vol is None

    def test_missing_time_returns_none(self, close_only_map: dict[str, str | None]) -> None:
        bar, vol = _serialize_bar({"close": 103}, close_only_map)
        assert bar is None
        assert vol is None

    def test_close_none_returns_none(self) -> None:
        m = {
            "time": None,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
        }
        bar, vol = _serialize_bar({"x": 1}, m)
        assert bar is None
        assert vol is None

    def test_nan_close_returns_none(self, close_only_map: dict[str, str | None]) -> None:
        bar, vol = _serialize_bar({"time": 100, "close": float("nan")}, close_only_map)
        assert bar is None
        assert vol is None

    def test_partial_ohlc_falls_back_to_value(self) -> None:
        m = {
            "time": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": None,
        }
        bar, _vol = _serialize_bar(
            {"time": 100, "open": float("nan"), "high": 5, "low": 1, "close": 3}, m
        )
        assert bar is not None
        assert "value" in bar
        assert "open" not in bar

    def test_volume_invalid_value_no_dict(self) -> None:
        m = {
            "time": "time",
            "open": None,
            "high": None,
            "low": None,
            "close": "close",
            "volume": "vol",
        }
        bar, vol = _serialize_bar({"time": 100, "close": 5, "vol": float("nan")}, m)
        assert bar is not None
        assert vol is None


class TestSerializeSeriesFromRows:
    def test_basic_ohlcv(
        self,
        ohlcv_rows: list[dict[str, Any]],
        default_ohlcv_map: dict[str, str | None],
    ) -> None:
        result = _serialize_series_from_rows(ohlcv_rows, default_ohlcv_map, "test")
        assert result.series_id == "test"
        assert len(result.bars) == 5
        assert result.series_type == SeriesType.CANDLESTICK
        assert result.has_volume is True

    def test_truncation_keeps_recent(self, close_only_map: dict[str, str | None]) -> None:
        rows = [{"time": i, "close": float(i)} for i in range(10)]
        result = _serialize_series_from_rows(rows, close_only_map, "main", max_bars=4)
        assert result.total_rows == 10
        assert result.truncated_rows == 6
        assert result.bars[0]["time"] == 6
        assert result.bars[-1]["time"] == 9

    def test_invalid_rows_skipped(self, close_only_map: dict[str, str | None]) -> None:
        rows = [
            {"time": 1, "close": 5.0},
            {"close": 6.0},  # missing time → skipped
            {"time": 3, "close": 7.0},
        ]
        result = _serialize_series_from_rows(rows, close_only_map, "x")
        assert len(result.bars) == 2


# =============================================================================
# _df_to_records (DatetimeIndex extraction)
# =============================================================================


class TestDfToRecords:
    def test_datetime_index_extracted(self) -> None:
        idx = pd.date_range("2023-11-15", periods=3, freq="D")
        df = pd.DataFrame({"close": [1, 2, 3]}, index=idx)
        records, columns = _df_to_records(df)
        assert len(records) == 3
        assert any("time" in c.lower() or "index" in c.lower() for c in columns)

    def test_named_index_extracted_under_its_name(self) -> None:
        df = pd.DataFrame({"close": [1, 2, 3]})
        df.index.name = "myidx"
        _records, columns = _df_to_records(df)
        assert "myidx" in columns

    def test_unnamed_default_index_kept(self) -> None:
        df = pd.DataFrame({"time": [1, 2], "close": [3, 4]})
        _records, columns = _df_to_records(df)
        assert "time" in columns


# =============================================================================
# _handle_multiindex_columns
# =============================================================================


class TestHandleMultiindexColumns:
    def test_yfinance_style_pivot(self) -> None:
        idx = pd.date_range("2023-11-15", periods=3, freq="D")
        df = pd.DataFrame(
            np.array(
                [
                    [100, 101, 102, 103, 105, 106, 107, 108],
                    [110, 111, 112, 113, 115, 116, 117, 118],
                    [120, 121, 122, 123, 125, 126, 127, 128],
                ],
                dtype=float,
            ),
            index=idx,
            columns=pd.MultiIndex.from_tuples(
                [
                    ("Open", "AAPL"),
                    ("High", "AAPL"),
                    ("Low", "AAPL"),
                    ("Close", "AAPL"),
                    ("Open", "MSFT"),
                    ("High", "MSFT"),
                    ("Low", "MSFT"),
                    ("Close", "MSFT"),
                ]
            ),
        )
        result, source_format = _handle_multiindex_columns(df)
        assert source_format == "multiindex"
        assert isinstance(result, list)
        assert len(result) == 6
        assert {row["symbol"] for row in result} == {"AAPL", "MSFT"}

    def test_non_yfinance_falls_to_flatten(self) -> None:
        df = pd.DataFrame(
            np.array([[1, 2, 3, 4]], dtype=float),
            columns=pd.MultiIndex.from_tuples(
                [("foo", "a"), ("foo", "b"), ("bar", "a"), ("bar", "b")]
            ),
        )
        result, source_format = _handle_multiindex_columns(df)
        assert source_format == "single"
        assert "foo_a" in [str(c) for c in result.columns]

    def test_no_datetime_index_skips_time_field(self) -> None:
        df = pd.DataFrame(
            np.array([[100.0, 103.0, 200.0, 203.0], [110.0, 113.0, 210.0, 213.0]]),
            columns=pd.MultiIndex.from_tuples(
                [("Open", "AAPL"), ("Close", "AAPL"), ("Open", "MSFT"), ("Close", "MSFT")]
            ),
        )
        result, source_format = _handle_multiindex_columns(df)
        assert source_format == "multiindex"
        assert isinstance(result, list)
        assert all("time" not in row for row in result)

    def test_missing_field_in_pivot(self) -> None:
        # Asymmetric coverage: AAPL has Open+Close, MSFT only Close.
        # When iterating MSFT's Open field the KeyError must be caught.
        idx = pd.date_range("2023-11-15", periods=2, freq="D")
        df = pd.DataFrame(
            np.array([[100.0, 103.0, 203.0], [110.0, 113.0, 213.0]]),
            index=idx,
            columns=pd.MultiIndex.from_tuples(
                [("Open", "AAPL"), ("Close", "AAPL"), ("Close", "MSFT")]
            ),
        )
        result, _ = _handle_multiindex_columns(df)
        assert isinstance(result, list)

    def test_non_tuple_column_in_flatten_path(self) -> None:
        df = pd.DataFrame({"a": [1.0]})
        df.columns = pd.Index(["plain_str"])
        result, source_format = _handle_multiindex_columns(df)
        assert source_format == "single"
        assert "plain_str" in [str(c) for c in result.columns]


# =============================================================================
# normalize_ohlcv — primary entry point
# =============================================================================


class TestNormalizeOhlcvHappyPath:
    def test_list_of_dicts_ohlcv(self, ohlcv_rows: list[dict[str, Any]]) -> None:
        result = normalize_ohlcv(ohlcv_rows)
        assert isinstance(result, TVChartData)
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"
        assert len(result.bars) == 5
        assert result.series[0].has_volume is True
        assert result.series[0].series_type == SeriesType.CANDLESTICK

    def test_list_of_dicts_line_only(self, line_rows: list[dict[str, Any]]) -> None:
        result = normalize_ohlcv(line_rows)
        assert len(result.bars) == 3
        assert "value" in result.bars[0]
        assert result.series[0].series_type == SeriesType.LINE

    def test_dict_of_lists(self) -> None:
        result = normalize_ohlcv({"time": [1700000000, 1700086400], "close": [100.0, 101.0]})
        assert len(result.bars) == 2

    def test_dict_of_scalars_single_record(self) -> None:
        result = normalize_ohlcv({"time": 1700000000, "close": 100.0})
        assert len(result.bars) == 1

    def test_dict_empty_lists(self) -> None:
        result = normalize_ohlcv({"time": [], "close": []})
        assert len(result.series) == 1
        assert len(result.bars) == 0

    def test_empty_list(self) -> None:
        result = normalize_ohlcv([])
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"
        assert len(result.bars) == 0

    def test_passthrough_tvchart_data(self) -> None:
        original = TVChartData(
            series=[
                TVChartSeriesData(series_id="test", bars=[{"time": 1, "value": 2}], total_rows=1)
            ]
        )
        assert normalize_ohlcv(original) is original

    def test_max_bars_truncation(self, ohlcv_rows: list[dict[str, Any]]) -> None:
        # Generate 20 rows so truncation is meaningful.
        rows = _make_ohlcv_rows(20)
        result = normalize_ohlcv(rows, max_bars=5)
        assert len(result.bars) == 5
        assert result.series[0].truncated_rows == 15
        assert result.series[0].total_rows == 20


class TestNormalizeOhlcvDataFrames:
    def test_simple_dataframe(self) -> None:
        df = pd.DataFrame(
            {
                "time": [1700000000, 1700086400],
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [103.0, 104.0],
                "volume": [1_000_000, 2_000_000],
            }
        )
        result = normalize_ohlcv(df)
        assert len(result.bars) == 2
        assert result.column_types  # populated for DataFrames
        assert result.source_format == "single"

    def test_dataframe_with_datetime_index(self) -> None:
        idx = pd.date_range("2023-11-15", periods=3, freq="D")
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [103, 104, 105],
            },
            index=idx,
        )
        result = normalize_ohlcv(df)
        assert len(result.bars) == 3

    def test_dataframe_wide_multi_series(self) -> None:
        df = pd.DataFrame(
            {
                "time": [1700000000, 1700086400, 1700172800],
                "value": [50.0, 51.0, 52.0],
                "AAPL": [100.0, 101.0, 102.0],
                "MSFT": [200.0, 201.0, 202.0],
            }
        )
        result = normalize_ohlcv(df)
        assert result.is_multi_series is True
        assert result.source_format == "wide"

    def test_dataframe_narrow_multi_series(self) -> None:
        # 30 rows per symbol so unique/rows < 0.1 triggers narrow detection.
        df = pd.DataFrame(
            {
                "time": list(range(1_700_000_000, 1_700_000_000 + 60 * 86400, 86400)) * 1,
                "symbol": pd.Categorical(["AAPL"] * 30 + ["MSFT"] * 30),
                "close": [100.0 + i for i in range(60)],
            }
        )
        result = normalize_ohlcv(df)
        assert result.is_multi_series is True
        assert result.source_format == "narrow"
        assert {s.series_id for s in result.series} == {"AAPL", "MSFT"}

    def test_dataframe_multiindex_columns(self) -> None:
        idx = pd.date_range("2023-11-15", periods=2, freq="D")
        df = pd.DataFrame(
            np.array([[100, 101, 200, 201], [110, 111, 210, 211]], dtype=float),
            index=idx,
            columns=pd.MultiIndex.from_tuples(
                [("Close", "AAPL"), ("Open", "AAPL"), ("Close", "MSFT"), ("Open", "MSFT")]
            ),
        )
        result = normalize_ohlcv(df)
        assert result.source_format == "multiindex"
        assert result.is_multi_series is True


class TestNormalizeOhlcvFallbacks:
    """Time-column fallbacks: 'index', 'level_0', and 'value' for close."""

    def test_index_fallback_for_time(self) -> None:
        result = normalize_ohlcv([{"index": 1700000000, "close": 100.0}])
        assert len(result.bars) == 1
        assert result.time_column == "index"

    def test_level_0_fallback_for_time(self) -> None:
        result = normalize_ohlcv([{"level_0": 1700000000, "close": 100.0}])
        assert len(result.bars) == 1
        assert result.time_column == "level_0"

    def test_value_column_fallback_for_close(self) -> None:
        result = normalize_ohlcv([{"time": 1700000000, "value": 50.5}])
        assert len(result.bars) == 1
        assert result.bars[0]["value"] == 50.5

    def test_capitalized_columns(self) -> None:
        rows = [
            {
                "Date": 1700000000,
                "Open": 100,
                "High": 105,
                "Low": 98,
                "Close": 103,
                "Volume": 1000,
            }
        ]
        result = normalize_ohlcv(rows)
        assert len(result.bars) == 1
        assert result.bars[0]["open"] == 100.0


class TestNormalizeOhlcvErrors:
    def test_unsupported_type(self) -> None:
        with pytest.raises(TypeError, match="Unsupported data type"):
            normalize_ohlcv("not_valid_data")

    def test_unsupported_int(self) -> None:
        with pytest.raises(TypeError, match="Unsupported"):
            normalize_ohlcv(42)

    def test_missing_time_column(self) -> None:
        with pytest.raises(ValueError, match="Could not resolve time column"):
            normalize_ohlcv([{"price": 100}])

    def test_missing_close_column(self) -> None:
        with pytest.raises(ValueError, match="Could not resolve close/value column"):
            normalize_ohlcv([{"time": 1700000000, "foo": 100}])

    def test_flattened_multiindex_dataframe_no_close(self) -> None:
        # MultiIndex columns where level_0 isn't all OHLCV-like → flatten →
        # _df_to_records → no close column → ValueError.
        idx = pd.date_range("2023-11-15", periods=3, freq="D")
        df = pd.DataFrame(
            np.array([[1.0, 2.0]] * 3),
            index=idx,
            columns=pd.MultiIndex.from_tuples([("foo", "x"), ("bar", "y")]),
        )
        with pytest.raises(ValueError, match="close/value"):
            normalize_ohlcv(df)


# =============================================================================
# _build_narrow_multi_series + _build_wide_multi_series (fallback empties)
# =============================================================================


class TestBuildNarrowMultiSeriesFallback:
    def test_empty_records_fallback_to_main(self, close_only_map: dict[str, str | None]) -> None:
        result = _build_narrow_multi_series(
            records=[],
            columns=["time", "symbol", "close"],
            ohlcv_map=close_only_map,
            symbol_col="symbol",
            column_types={},
            time_column="time",
            max_bars=10_000,
            source_format="narrow",
        )
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"


class TestBuildWideMultiSeriesFallback:
    def test_empty_records_fallback_to_main(self, close_only_map: dict[str, str | None]) -> None:
        # All columns mapped (no extra series cols) → fallback "main".
        result = _build_wide_multi_series(
            records=[],
            columns=["time", "close"],
            ohlcv_map=close_only_map,
            column_types={},
            time_column="time",
            max_bars=10_000,
        )
        assert len(result.series) == 1
        assert result.series[0].series_id == "main"


# =============================================================================
# _ColumnsProxy / _ColumnProxy / _FakeDtype helpers
# =============================================================================


class TestColumnsProxy:
    def test_len_and_getitem(self) -> None:
        records = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        proxy = _ColumnsProxy(records, ["a", "b"])
        assert len(proxy) == 2
        col = proxy["a"]
        assert isinstance(col, _ColumnProxy)


class TestColumnProxy:
    def test_dtype_string_values(self) -> None:
        col = _ColumnProxy([{"a": "x"}, {"a": "y"}], "a")
        assert col.dtype.kind == "O"

    def test_dtype_numeric_values(self) -> None:
        col = _ColumnProxy([{"a": 1}, {"a": 2}], "a")
        assert col.dtype.kind == "f"

    def test_dtype_only_none_defaults_object(self) -> None:
        col = _ColumnProxy([{"a": None}], "a")
        assert col.dtype.kind == "O"

    def test_dtype_unknown_value_type_defaults_object(self) -> None:
        col = _ColumnProxy([{"a": [1, 2, 3]}], "a")
        assert col.dtype.kind == "O"

    def test_nunique(self) -> None:
        col = _ColumnProxy([{"a": "x"}, {"a": "y"}, {"a": "x"}], "a")
        assert col.nunique() == 2


class TestFakeDtype:
    def test_kind_attribute(self) -> None:
        assert _FakeDtype("f").kind == "f"
        assert _FakeDtype("O").kind == "O"
