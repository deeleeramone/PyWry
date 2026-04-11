"""PyWry TradingView Chart Demo — static SPY OHLCV data from CSV files."""

from pathlib import Path

import pandas as pd

from pywry import PyWry, ThemeMode
from pywry.tvchart import build_tvchart_toolbars


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ET = "America/New_York"
_DATA_DIR = Path(__file__).parent

_CSV_FILES: dict[str, str] = {
    "1m": "SPY_1m.csv",
    "5m": "SPY_5m.csv",
    "15m": "SPY_15m.csv",
    "30m": "SPY_30m.csv",
    "1h": "SPY_60m.csv",
    "1d": "SPY_1d.csv",
}

# Intraday intervals get timezone-aware timestamps; daily and above do not.
_INTRADAY = {"1m", "5m", "15m", "30m", "1h"}


def _load_csv(interval: str, filename: str) -> pd.DataFrame:
    """Load a CSV into a DatetimeIndex DataFrame."""
    path = _DATA_DIR / filename
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    if interval in _INTRADAY:
        df.index = df.index.tz_localize(_ET)
    return df


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample a daily OHLCV DataFrame to a coarser period."""
    return (
        df.resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open"])
    )


def _df_to_bars(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to the list-of-dicts format the chart expects.

    Strips timezone so Lightweight Charts displays ET wall-clock times
    (the library renders timestamps as UTC).
    """
    idx = df.index
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    epoch = pd.Timestamp("1970-01-01")
    timestamps = ((idx - epoch) // pd.Timedelta("1s")).astype(int)
    records = []
    for t, (_, row) in zip(timestamps, df.iterrows(), strict=False):
        records.append(
            {
                "time": int(t),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(float(row["volume"])),
            }
        )
    return records


def _load_all_datasets() -> dict[str, list[dict]]:
    """Load CSV files and resample weekly/monthly from daily."""
    datasets: dict[str, list[dict]] = {}
    frames: dict[str, pd.DataFrame] = {}
    for interval, filename in _CSV_FILES.items():
        path = _DATA_DIR / filename
        if path.exists():
            frames[interval] = _load_csv(interval, filename)
            datasets[interval] = _df_to_bars(frames[interval])
    # Resample coarser intervals from daily
    if "1d" in frames:
        daily = frames["1d"]
        datasets["1w"] = _df_to_bars(_resample(daily, "W-FRI"))
        datasets["1M"] = _df_to_bars(_resample(daily, "MS"))
    return datasets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the PyWry TradingView chart demo."""
    datasets = _load_all_datasets()

    app = PyWry(theme=ThemeMode.DARK)
    state = {"interval": "1d"}

    def on_data_request(payload: dict, _et: str, _lb: str) -> None:
        interval = str(payload.get("resolution", payload.get("interval", state["interval"])))
        print(f"[data-request] raw payload keys: {list(payload.keys())}")
        print(
            f"[data-request] resolution={payload.get('resolution')!r}, interval={payload.get('interval')!r} → resolved={interval!r}"
        )
        if interval not in datasets:
            print(
                f"[data-request] {interval!r} NOT in datasets {list(datasets.keys())}, falling back to 1d"
            )
            interval = "1d"
        state["interval"] = interval
        bars = datasets[interval]
        print(f"[data-request] sending {len(bars)} bars for interval={interval!r}")
        app.emit(
            "tvchart:data-response",
            {
                "chartId": payload.get("chartId", "main"),
                "seriesId": "main",
                "bars": bars,
                "fitContent": True,
                "interval": interval,
            },
        )

    toolbars = build_tvchart_toolbars(
        intervals=list(datasets),
        selected_interval="1d",
    )

    app.show_tvchart(
        data=datasets["1d"],
        title="SPY",
        width=1200,
        height=700,
        chart_options={"timeScale": {"secondsVisible": False}},
        toolbars=toolbars,
        callbacks={"tvchart:data-request": on_data_request},
    )
    app.block()


if __name__ == "__main__":
    main()
