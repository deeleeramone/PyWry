"""TradingView chart data normalization.

Converts various Python data formats (DataFrames, lists of dicts,
dicts of lists) into the normalized format expected by TradingView
Lightweight Charts.

Features:

- Duck typing for DataFrame detection (no hard pandas import)
- Column alias resolution for flexible input formats
- Value serialization (NaN, numpy scalars, Decimal, etc.)
- Multi-series detection (narrow/long and wide formats)
- MultiIndex columns (e.g. yfinance output)

Usage::

    from pywry.tvchart import normalize_ohlcv

    chart_data = normalize_ohlcv(df)
    chart_data = normalize_ohlcv(
        [
            {"time": 1700000000, "open": 100, "high": 105, "low": 99, "close": 103},
        ]
    )
"""

from __future__ import annotations

import math

from datetime import datetime, timezone
from typing import Any

from ..log import debug, info, warn
from .config import SeriesType
from .models import TVChartData, TVChartSeriesData


_TIME_ALIASES: set[str] = {
    "time",
    "date",
    "Date",
    "datetime",
    "Datetime",
    "timestamp",
    "Timestamp",
    "t",
}

_OPEN_ALIASES: set[str] = {"open", "Open", "o", "OPEN"}
_HIGH_ALIASES: set[str] = {"high", "High", "h", "HIGH"}
_LOW_ALIASES: set[str] = {"low", "Low", "l", "LOW"}
_CLOSE_ALIASES: set[str] = {
    "close",
    "Close",
    "c",
    "CLOSE",
    "adj_close",
    "Adj Close",
    "adjclose",
    "adjClose",
}
_VOLUME_ALIASES: set[str] = {"volume", "Volume", "vol", "Vol", "v", "VOLUME"}

_ALL_OHLCV_ALIASES: set[str] = (
    _TIME_ALIASES | _OPEN_ALIASES | _HIGH_ALIASES | _LOW_ALIASES | _CLOSE_ALIASES | _VOLUME_ALIASES
)
_SYMBOL_ALIASES: set[str] = {
    "symbol",
    "Symbol",
    "ticker",
    "Ticker",
    "name",
    "Name",
    "asset",
    "id",
    "identifier",
    "series",
    "SYMBOL",
    "TICKER",
    "series_id",
}


def _serialize_timestamp(value: Any) -> int | None:  # noqa: C901, PLR0911, PLR0912
    """Convert a timestamp to Unix epoch seconds.

    Parameters
    ----------
    value : Any
        pd.Timestamp, datetime, np.datetime64, ISO string, or numeric.

    Returns
    -------
    int or None
        Epoch seconds, or None if conversion fails.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return int(value)

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return int(value.astimezone(timezone.utc).timestamp())
        return int(value.replace(tzinfo=timezone.utc).timestamp())

    if hasattr(value, "item"):
        try:
            py_val = value.item()
            if isinstance(py_val, datetime):
                return int(py_val.replace(tzinfo=timezone.utc).timestamp())
            if isinstance(py_val, (int, float)):
                return int(py_val)
        except (AttributeError, ValueError, OverflowError):
            pass

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                return int(dt.astimezone(timezone.utc).timestamp())
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass

    if hasattr(value, "timestamp"):
        try:
            return int(value.timestamp())
        except (OSError, OverflowError, ValueError):
            pass

    warn(f"Could not convert timestamp value: {value!r}")
    return None


def _serialize_ohlcv_value(value: Any) -> float | None:  # noqa: PLR0911
    """Convert a price or volume value to float.

    Parameters
    ----------
    value : Any
        Numeric, numpy scalar, Decimal, or pandas NA.

    Returns
    -------
    float or None
        Native float, or None for NaN/NA/invalid values.
    """
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, int):
        return float(value)

    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except (ImportError, TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            native = value.item()
            if isinstance(native, float) and (math.isnan(native) or math.isinf(native)):
                return None
            return float(native)
        except (AttributeError, ValueError):
            pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_column(columns: list[str], aliases: set[str]) -> str | None:
    """Find the first column name matching any alias."""
    for col in columns:
        if col in aliases:
            return col
    return None


def _resolve_ohlcv_columns(
    columns: list[str],
) -> dict[str, str | None]:
    """Map canonical OHLCV field names to actual column names.

    Returns
    -------
    dict
        Keys: 'time', 'open', 'high', 'low', 'close', 'volume'.
        Values: actual column name or None if not found.
    """
    return {
        "time": _resolve_column(columns, _TIME_ALIASES),
        "open": _resolve_column(columns, _OPEN_ALIASES),
        "high": _resolve_column(columns, _HIGH_ALIASES),
        "low": _resolve_column(columns, _LOW_ALIASES),
        "close": _resolve_column(columns, _CLOSE_ALIASES),
        "volume": _resolve_column(columns, _VOLUME_ALIASES),
    }


def _detect_ohlcv_column_types(data: Any) -> dict[str, str]:
    """Detect column dtypes from a DataFrame-like object.

    Returns
    -------
    dict[str, str]
        Column name to dtype string mapping.
    """
    if not hasattr(data, "dtypes"):
        return {}
    return {str(col): str(dtype) for col, dtype in data.dtypes.items()}


def _detect_symbol_column(  # noqa: C901
    columns: list[str],
    data: Any,
    symbol_col: str | None = None,
) -> str | None:
    """Detect the identifier column for narrow/long-format multi-series data.

    Parameters
    ----------
    columns : list[str]
        Column names in the data.
    data : Any
        DataFrame-like object (for cardinality check).
    symbol_col : str or None
        Explicit override from user.

    Returns
    -------
    str or None
        The column to group by, or None if single-series.
    """
    if symbol_col is not None:
        if symbol_col in columns:
            return symbol_col
        warn(f"Explicit symbol_col={symbol_col!r} not found in columns")
        return None

    for col in columns:
        if col not in _SYMBOL_ALIASES:
            continue
        if col in _ALL_OHLCV_ALIASES:
            continue
        if hasattr(data, "__getitem__") and hasattr(data, "__len__"):
            try:
                col_data = data[col]
                if hasattr(col_data, "dtype"):
                    dtype_kind = getattr(col_data.dtype, "kind", "")
                    if dtype_kind not in ("O", "U", "S"):
                        dtype_name = str(col_data.dtype)
                        if "category" not in dtype_name and "string" not in dtype_name:
                            continue
                if hasattr(col_data, "nunique"):
                    n_unique = col_data.nunique()
                    n_rows = len(data)
                    if 0 < n_unique < n_rows * 0.1:
                        return col
            except (KeyError, TypeError):
                continue

    return None


def _is_wide_format(
    columns: list[str],
    ohlcv_map: dict[str, str | None],
    data: Any,
) -> bool:
    """Detect wide-format multi-series data.

    Returns True when the data has a time column and two or more
    remaining numeric columns (e.g. date | AAPL | MSFT | GOOG).
    """
    time_col = ohlcv_map.get("time")
    if time_col is None:
        return False

    mapped_cols = {v for v in ohlcv_map.values() if v is not None}
    remaining = [c for c in columns if c not in mapped_cols]

    if len(remaining) < 2:
        return False

    if hasattr(data, "dtypes"):
        for col in remaining:
            try:
                dtype_str = str(data[col].dtype)
                if "int" not in dtype_str and "float" not in dtype_str:
                    return False
            except (KeyError, TypeError):
                return False
    else:
        return False

    return True


def _has_multiindex_columns(data: Any) -> bool:
    """Check if the DataFrame has MultiIndex columns."""
    return (
        hasattr(data, "columns") and hasattr(data.columns, "nlevels") and data.columns.nlevels > 1
    )


def _serialize_bar(
    row: dict[str, Any],
    ohlcv_map: dict[str, str | None],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Serialize one row into a bar dict and an optional volume dict.

    Returns
    -------
    tuple[dict or None, dict or None]
        (bar, volume) where either may be None if the row is invalid.
    """
    time_col = ohlcv_map["time"]
    close_col = ohlcv_map["close"]

    if time_col is None or close_col is None:
        return None, None

    time_val = _serialize_timestamp(row.get(time_col))
    if time_val is None:
        return None, None

    close_val = _serialize_ohlcv_value(row.get(close_col))
    if close_val is None:
        return None, None

    bar_dict: dict[str, Any] = {"time": time_val}

    open_col = ohlcv_map["open"]
    high_col = ohlcv_map["high"]
    low_col = ohlcv_map["low"]

    if open_col and high_col and low_col:
        o = _serialize_ohlcv_value(row.get(open_col))
        h = _serialize_ohlcv_value(row.get(high_col))
        lo = _serialize_ohlcv_value(row.get(low_col))
        if o is not None and h is not None and lo is not None:
            bar_dict["open"] = o
            bar_dict["high"] = h
            bar_dict["low"] = lo
            bar_dict["close"] = close_val
        else:
            bar_dict["value"] = close_val
    else:
        bar_dict["value"] = close_val

    vol_dict: dict[str, Any] | None = None
    vol_col = ohlcv_map["volume"]
    if vol_col:
        vol_val = _serialize_ohlcv_value(row.get(vol_col))
        if vol_val is not None:
            vol_dict = {"time": time_val, "value": vol_val}

    return bar_dict, vol_dict


def _serialize_series_from_rows(
    rows: list[dict[str, Any]],
    ohlcv_map: dict[str, str | None],
    series_id: str,
    max_bars: int = 10_000,
) -> TVChartSeriesData:
    """Convert a list of row dicts into a TVChartSeriesData."""
    total = len(rows)
    truncated = 0

    if total > max_bars:
        truncated = total - max_bars
        rows = rows[-max_bars:]  # Keep most recent
        info(f"Series '{series_id}': truncated {truncated:,} oldest bars (max_bars={max_bars:,})")

    bars: list[dict[str, Any]] = []
    volume: list[dict[str, Any]] = []

    for row in rows:
        bar_dict, vol = _serialize_bar(row, ohlcv_map)
        if bar_dict is not None:
            bars.append(bar_dict)
        if vol is not None:
            volume.append(vol)

    has_ohlc = len(bars) > 0 and "open" in bars[0]
    series_type = SeriesType.CANDLESTICK if has_ohlc else SeriesType.LINE

    return TVChartSeriesData(
        series_id=series_id,
        bars=bars,
        volume=volume,
        series_type=series_type,
        has_volume=len(volume) > 0,
        total_rows=total,
        truncated_rows=truncated,
    )


def _df_to_records(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert a DataFrame-like object to records, handling DatetimeIndex.

    Returns
    -------
    tuple[list[dict], list[str]]
        (records, columns).
    """
    if hasattr(data, "index"):
        index = data.index
        is_datetime_index = hasattr(index, "dtype") and "datetime" in str(index.dtype)
        is_named_index = getattr(index, "name", None) is not None

        if is_datetime_index or is_named_index:
            index_name = getattr(index, "name", None) or "time"
            data = data.reset_index()
            debug(f"Extracted DatetimeIndex as column '{index_name}'")

    records = data.to_dict(orient="records")
    columns = [str(c) for c in data.columns]
    return records, columns


def _handle_multiindex_columns(data: Any) -> tuple[Any, str]:  # noqa: PLR0912
    """Flatten MultiIndex columns for multi-series detection.

    For yfinance-style MultiIndex like ('Close', 'AAPL'):
    if all level-0 values are OHLCV fields, group by level-1 (symbols).
    Otherwise flatten with underscore join.

    Returns
    -------
    tuple[Any, str]
        (transformed_data, source_format).
    """
    level_0_vals = set()
    level_1_vals = set()

    for col_tuple in data.columns:
        if isinstance(col_tuple, tuple) and len(col_tuple) >= 2:
            level_0_vals.add(str(col_tuple[0]))
            level_1_vals.add(str(col_tuple[1]))

    ohlcv_field_names = _ALL_OHLCV_ALIASES - _TIME_ALIASES
    if level_0_vals and level_0_vals.issubset(ohlcv_field_names | _TIME_ALIASES):
        all_rows: list[dict[str, Any]] = []

        if hasattr(data.index, "dtype") and "datetime" in str(data.index.dtype):
            time_values = data.index
        else:
            time_values = None

        for symbol in sorted(level_1_vals):
            for i in range(len(data)):
                row: dict[str, Any] = {"symbol": symbol}
                if time_values is not None:
                    row["time"] = time_values[i]
                for field in level_0_vals:
                    try:
                        val = data[(field, symbol)].iloc[i]
                        row[field.lower()] = val
                    except (KeyError, IndexError):
                        pass
                all_rows.append(row)

        return all_rows, "multiindex"

    flat_columns = []
    for col_tuple in data.columns:
        if isinstance(col_tuple, tuple):
            flat_columns.append("_".join(str(level) for level in col_tuple))
        else:
            flat_columns.append(str(col_tuple))

    data_copy = data.copy()
    data_copy.columns = flat_columns
    return data_copy, "single"


def normalize_ohlcv(  # noqa: C901, PLR0912, PLR0915
    data: Any,
    *,
    symbol_col: str | None = None,
    max_bars: int = 10_000,
) -> TVChartData:
    """Convert Python data formats to normalized TVChartData.

    Parameters
    ----------
    data : Any
        DataFrame, list of dicts, or dict of lists.
    symbol_col : str or None
        Column name for multi-series grouping.
    max_bars : int
        Maximum bars per series.

    Returns
    -------
    TVChartData

    Raises
    ------
    ValueError
        If required columns cannot be resolved.
    """
    if isinstance(data, TVChartData):
        return data

    records: list[dict[str, Any]] = []
    columns: list[str] = []
    column_types: dict[str, str] = {}
    source_format = "single"
    detected_symbol_col: str | None = None

    if hasattr(data, "to_dict") and hasattr(data, "columns"):
        column_types = _detect_ohlcv_column_types(data)

        if _has_multiindex_columns(data):
            result, source_format = _handle_multiindex_columns(data)
            if isinstance(result, list):
                records = result
                columns = list(records[0].keys()) if records else []
                detected_symbol_col = "symbol"
            else:
                records, columns = _df_to_records(result)
        else:
            records, columns = _df_to_records(data)

    elif isinstance(data, dict):
        first_value = next(iter(data.values()), None)
        if isinstance(first_value, (list, tuple)):
            columns = [str(k) for k in data]
            num_rows = len(first_value) if first_value else 0
            records = [{col: data[col][i] for col in columns} for i in range(num_rows)]
        else:
            columns = [str(k) for k in data]
            records = [data]

    elif isinstance(data, list):
        records = list(data)
        if records and isinstance(records[0], dict):
            columns = list(records[0].keys())

    else:
        msg = f"Unsupported data type: {type(data).__name__}"
        raise TypeError(msg)

    if not records:
        return TVChartData(
            series=[TVChartSeriesData(series_id="main", bars=[], total_rows=0)],
            columns=columns,
            column_types=column_types,
        )

    ohlcv_map = _resolve_ohlcv_columns(columns)

    if ohlcv_map["time"] is None:
        for fallback in ("index", "level_0"):
            if fallback in columns:
                ohlcv_map["time"] = fallback
                break

    if ohlcv_map["time"] is None:
        msg = (
            f"Could not resolve time column. Available columns: {columns}. "
            f"Expected one of: {sorted(_TIME_ALIASES)}"
        )
        raise ValueError(msg)

    if ohlcv_map["close"] is None:
        if "value" in columns:
            ohlcv_map["close"] = "value"
        else:
            msg = (
                f"Could not resolve close/value column. Available columns: {columns}. "
                f"Expected one of: {sorted(_CLOSE_ALIASES)}"
            )
            raise ValueError(msg)

    time_column = ohlcv_map["time"] or "time"

    if detected_symbol_col is None and source_format != "multiindex":
        detected_symbol_col = _detect_symbol_column(
            columns,
            _ColumnsProxy(records, columns) if not hasattr(data, "to_dict") else data,
            symbol_col=symbol_col,
        )

    if detected_symbol_col:
        return _build_narrow_multi_series(
            records,
            columns,
            ohlcv_map,
            detected_symbol_col,
            column_types,
            time_column,
            max_bars,
            source_format,
        )

    if hasattr(data, "to_dict") and _is_wide_format(columns, ohlcv_map, data):
        return _build_wide_multi_series(
            records,
            columns,
            ohlcv_map,
            column_types,
            time_column,
            max_bars,
        )

    series_data = _serialize_series_from_rows(records, ohlcv_map, "main", max_bars)

    debug(
        f"Normalized single series: {series_data.total_rows} rows, "
        f"type={series_data.series_type.value}, has_volume={series_data.has_volume}"
    )

    return TVChartData(
        series=[series_data],
        columns=columns,
        time_column=time_column,
        column_types=column_types,
        source_format=source_format,
    )


def _build_narrow_multi_series(
    records: list[dict[str, Any]],
    columns: list[str],
    ohlcv_map: dict[str, str | None],
    symbol_col: str,
    column_types: dict[str, str],
    time_column: str,
    max_bars: int,
    source_format: str,
) -> TVChartData:
    """Build multi-series data from narrow/long format (groupby identifier)."""
    from collections import defaultdict

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        key = str(row.get(symbol_col, "unknown"))
        groups[key] = groups.get(key, [])
        groups[key].append(row)

    all_series: list[TVChartSeriesData] = []
    for sym, rows in groups.items():
        series_data = _serialize_series_from_rows(rows, ohlcv_map, sym, max_bars)
        all_series.append(series_data)

    if not all_series:
        all_series.append(TVChartSeriesData(series_id="main", bars=[], total_rows=0))

    fmt = "multiindex" if source_format == "multiindex" else "narrow"
    debug(f"Normalized {len(all_series)} series from {fmt} format (symbol_col='{symbol_col}')")

    return TVChartData(
        series=all_series,
        columns=columns,
        time_column=time_column,
        symbol_column=symbol_col,
        is_multi_series=True,
        source_format=fmt,
        column_types=column_types,
    )


def _build_wide_multi_series(
    records: list[dict[str, Any]],
    columns: list[str],
    ohlcv_map: dict[str, str | None],
    column_types: dict[str, str],
    time_column: str,
    max_bars: int,
) -> TVChartData:
    """Build multi-series data from wide format (each column is a series)."""
    mapped_cols = {v for v in ohlcv_map.values() if v is not None}
    series_cols = [c for c in columns if c not in mapped_cols]

    all_series: list[TVChartSeriesData] = []
    for col in series_cols:
        col_map: dict[str, str | None] = {
            "time": ohlcv_map["time"],
            "open": None,
            "high": None,
            "low": None,
            "close": col,  # The column IS the close/value
            "volume": None,
        }
        series_data = _serialize_series_from_rows(records, col_map, col, max_bars)
        series_data.series_type = SeriesType.LINE
        all_series.append(series_data)

    if not all_series:
        all_series.append(TVChartSeriesData(series_id="main", bars=[], total_rows=0))

    debug(f"Normalized {len(all_series)} series from wide format")

    return TVChartData(
        series=all_series,
        columns=columns,
        time_column=time_column,
        is_multi_series=True,
        source_format="wide",
        column_types=column_types,
    )


class _ColumnsProxy:
    """Minimal DataFrame-like proxy over list[dict] for column access."""

    def __init__(self, records: list[dict[str, Any]], columns: list[str]) -> None:
        self._records = records
        self._columns = columns

    def __len__(self) -> int:
        return len(self._records)

    def __getitem__(self, key: str) -> _ColumnProxy:
        return _ColumnProxy(self._records, key)


class _ColumnProxy:
    """Single column accessor over a list of dicts."""

    def __init__(self, records: list[dict[str, Any]], key: str) -> None:
        self._records = records
        self._key = key

    @property
    def dtype(self) -> _FakeDtype:
        """Infer dtype from the first non-None value in the column."""
        for row in self._records[:100]:
            val = row.get(self._key)
            if val is not None:
                if isinstance(val, str):
                    return _FakeDtype("O")
                if isinstance(val, (int, float)):
                    return _FakeDtype("f")
                break
        return _FakeDtype("O")

    def nunique(self) -> int:
        """Count unique values in the column."""
        return len({row.get(self._key) for row in self._records})


class _FakeDtype:
    """Minimal dtype proxy for _detect_symbol_column cardinality checks."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
