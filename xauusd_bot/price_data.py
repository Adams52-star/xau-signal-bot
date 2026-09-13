"""
Fetches XAU/USD OHLC candle data from TwelveData's free API — no broker
terminal required, works from any machine (including GitHub Actions'
Linux runners).

Free tier limits: 800 requests/day, 8/minute. A check every 15 minutes
uses ~96 requests/day, well within that.
"""

import logging
import pandas as pd
import requests

import config

log = logging.getLogger("price_data")

BASE_URL = "https://api.twelvedata.com/time_series"


def get_candles(symbol: str = None, interval: str = None, count: int = None) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: time, open, high, low, close
    sorted oldest → newest. Empty DataFrame on failure.
    """
    symbol = symbol or config.SYMBOL
    interval = interval or config.INTERVAL
    count = count or config.CANDLES_TO_FETCH

    if not config.TWELVEDATA_API_KEY:
        log.error("TWELVEDATA_API_KEY is not set (check your environment/GitHub secret).")
        return pd.DataFrame()

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": count,
        "apikey": config.TWELVEDATA_API_KEY,
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        log.error("Request to TwelveData failed: %s", e)
        return pd.DataFrame()

    if data.get("status") == "error" or "values" not in data:
        log.error("TwelveData error: %s", data.get("message", data))
        return pd.DataFrame()

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={"datetime": "time"})
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def get_current_price(symbol: str = None) -> float:
    df = get_candles(symbol=symbol, count=1)
    if df.empty:
        return None
    return float(df["close"].iloc[-1])
