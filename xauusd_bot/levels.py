"""
Key levels: previous day's high/low (derived from the fetched intraday
candles, no extra API call needed), round numbers, and CRT (Candle Range
Theory) base range.

CRT as implemented here: the previous COMPLETE day's candle (built by
resampling the intraday data we already have) is treated as the "base
range". If recent price manipulates outside that range (sweeps one side)
and reverses back through it, that's flagged as a CRT-aligned confluence
— the same sweep/reclaim logic used elsewhere, just anchored to this
specific higher-timeframe range rather than a local swing point.

Honest limitation: this is a simplified reading of CRT (one prior-day
base candle), not the full multi-model CRT framework some traders use
with multiple nested ranges. Treat it as one extra piece of confluence,
not a standalone signal.
"""

import pandas as pd


def previous_day_high_low(df: pd.DataFrame) -> dict:
    """
    Resamples the fetched candles by calendar date and returns the
    most recently COMPLETED day's high and low (not the still-forming
    current day). Returns {"high": float, "low": float, "date": str} or
    {"high": None, "low": None, "date": None} if there isn't at least
    one prior complete day in the data.
    """
    if df.empty:
        return {"high": None, "low": None, "date": None}

    working = df.copy()
    working["date"] = working["time"].dt.date
    today = working["date"].iloc[-1]
    prior_days = working[working["date"] < today]

    if prior_days.empty:
        return {"high": None, "low": None, "date": None}

    last_complete_date = prior_days["date"].iloc[-1]
    day_rows = prior_days[prior_days["date"] == last_complete_date]
    return {
        "high": float(day_rows["high"].max()),
        "low": float(day_rows["low"].min()),
        "date": str(last_complete_date),
    }


def nearest_round_level(price: float, step: float) -> float:
    """Nearest round number to `price` at the given step (e.g. step=5 -> nearest $5 level)."""
    return round(price / step) * step


def crt_base_range(df: pd.DataFrame) -> dict:
    """
    Returns the previous complete day's high/low as the CRT base range,
    same data as previous_day_high_low (kept as a separate named function
    since conceptually it's used differently — as a range to be swept,
    not just a target level).
    """
    return previous_day_high_low(df)
