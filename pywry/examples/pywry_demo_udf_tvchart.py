"""PyWry UDF TradingView Chart Demo.

Connects to the TradingView public demo UDF server and displays a
live-data chart with symbol search, resolution switching, and marks.

Usage::

    python examples/pywry_demo_udf_tvchart.py
"""

from pywry import PyWry
from pywry.tvchart.udf import UDFAdapter


# BitMEX UDF Adapter for TradingView
UDF_URL = "https://www.bitmex.com/api/udf"

app = PyWry()

udf = UDFAdapter(UDF_URL, poll_interval=60)

udf.connect(
    app,
    symbol="XBTUSD",
    resolution="D",
    title="PyWry TradingView Lightweight Charts UDF Demo — Bitmex",
    width=1200,
    height=700,
)

app.block()
udf.close()
