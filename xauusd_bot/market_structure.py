"""
Market structure: swing points, and Break of Structure (BOS) vs
Change of Character (CHoCH) classification.

Definitions used (standard SMC usage):
- Swing high: a candle whose high is the max within `lookback` candles on
  both sides.
- Swing low: a candle whose low is the min within `lookback` candles on
  both sides.
- Uptrend structure = Higher Highs (HH) + Higher Lows (HL).
  Downtrend structure = Lower Highs (LH) + Lower Lows (LL).
- BOS (Break of Structure): price breaks the most recent swing point in
  the direction the trend is ALREADY going — confirms continuation.
- CHoCH (Change of Character): price breaks the most recent swing point
  AGAINST the current trend — the first sign of a possible reversal.
  This engine only trades CHoCH setups (reversals), not BOS continuations
  — that's a deliberate scope choice, not an oversight.
"""

import pandas as pd


def find_swings(df: pd.DataFrame, lookback: int) -> list:
    """
    Returns a chronological list of confirmed swing points:
    [{"index": i, "type": "high"|"low", "price": float}, ...]
    A swing needs `lookback` candles on BOTH sides to confirm, so the most
    recent `lookback` candles can never produce a confirmed swing yet.
    """
    swings = []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_high = df["high"].iloc[i - lookback: i + lookback + 1]
        window_low = df["low"].iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == window_high.max():
            swings.append({"index": i, "type": "high", "price": float(df["high"].iloc[i])})
        if df["low"].iloc[i] == window_low.min():
            swings.append({"index": i, "type": "low", "price": float(df["low"].iloc[i])})
    swings.sort(key=lambda s: s["index"])
    return swings


def filter_alternating(swings: list) -> list:
    """
    Raw swing detection can produce consecutive highs or consecutive lows
    (e.g. two nearby swing highs before the next swing low). For clean
    structure analysis we need strict alternation: when two same-type
    swings appear back to back, keep only the more extreme one (higher
    high wins between two highs, lower low wins between two lows).
    """
    if not swings:
        return []

    cleaned = [swings[0]]
    for s in swings[1:]:
        last = cleaned[-1]
        if s["type"] == last["type"]:
            if s["type"] == "high" and s["price"] > last["price"]:
                cleaned[-1] = s
            elif s["type"] == "low" and s["price"] < last["price"]:
                cleaned[-1] = s
            # else: keep the existing one, discard s
        else:
            cleaned.append(s)
    return cleaned


def get_current_structure(df: pd.DataFrame, filtered_swings: list) -> dict:
    """
    Determines the current trend from the two most recent confirmed
    swing highs and two most recent confirmed swing lows, then checks
    whether the LATEST candle's close just broke structure.

    Returns:
        {
            "trend": "bullish" | "bearish" | None,
            "event": "BOS" | "CHoCH" | None,
            "direction": "bullish" | "bearish" | None,   # direction of the event
            "broken_level": float | None,
            "reference_swing_high": float | None,
            "reference_swing_low": float | None,
            "reference_swing_low_index": int | None,
            "reference_swing_high_index": int | None,
        }
    """
    highs = [s for s in filtered_swings if s["type"] == "high"]
    lows = [s for s in filtered_swings if s["type"] == "low"]

    result = {
        "trend": None, "event": None, "direction": None, "broken_level": None,
        "reference_swing_high": None, "reference_swing_low": None,
        "reference_swing_low_index": None, "reference_swing_high_index": None,
    }

    if len(highs) < 2 or len(lows) < 2:
        return result

    last_high, prev_high = highs[-1], highs[-2]
    last_low, prev_low = lows[-1], lows[-2]

    if last_high["price"] > prev_high["price"] and last_low["price"] > prev_low["price"]:
        trend = "bullish"
    elif last_high["price"] < prev_high["price"] and last_low["price"] < prev_low["price"]:
        trend = "bearish"
    else:
        trend = None

    result["trend"] = trend
    result["reference_swing_high"] = last_high["price"]
    result["reference_swing_low"] = last_low["price"]
    result["reference_swing_high_index"] = last_high["index"]
    result["reference_swing_low_index"] = last_low["index"]

    if trend is None or df.empty:
        return result

    last_close = float(df["close"].iloc[-1])

    if trend == "bullish":
        if last_close < last_low["price"]:
            result["event"] = "CHoCH"
            result["direction"] = "bearish"
            result["broken_level"] = last_low["price"]
        elif last_close > last_high["price"]:
            result["event"] = "BOS"
            result["direction"] = "bullish"
            result["broken_level"] = last_high["price"]
    elif trend == "bearish":
        if last_close > last_high["price"]:
            result["event"] = "CHoCH"
            result["direction"] = "bullish"
            result["broken_level"] = last_high["price"]
        elif last_close < last_low["price"]:
            result["event"] = "BOS"
            result["direction"] = "bearish"
            result["broken_level"] = last_low["price"]

    return result


def find_recent_choch(df: pd.DataFrame, filtered_swings: list, max_window: int = 20) -> dict:
    """
    Finds the most recent CHoCH within the last `max_window` candles —
    not just the very last candle — since price needs time AFTER the
    CHoCH to retrace into the resulting order block before an entry is
    valid. The trend/reference swings used are the same for every candle
    in this window (swings this recent haven't been re-confirmed yet, by
    definition), so a single backward scan for the first breaking close
    is valid.

    Returns:
        {"found": False} or
        {
            "found": True, "index": int, "direction": "bullish"|"bearish",
            "broken_level": float,   # the swing point that was broken (CHoCH)
            "swept_level": float,    # the opposite-side swing swept just before
        }
    """
    highs = [s for s in filtered_swings if s["type"] == "high"]
    lows = [s for s in filtered_swings if s["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return {"found": False}

    last_high, prev_high = highs[-1], highs[-2]
    last_low, prev_low = lows[-1], lows[-2]

    if last_high["price"] > prev_high["price"] and last_low["price"] > prev_low["price"]:
        trend = "bullish"
    elif last_high["price"] < prev_high["price"] and last_low["price"] < prev_low["price"]:
        trend = "bearish"
    else:
        return {"found": False}

    n = len(df)
    ref_index = max(last_high["index"], last_low["index"])
    start = max(ref_index + 1, n - max_window)

    for i in range(start, n):
        close_i = float(df["close"].iloc[i])
        if trend == "bullish" and close_i < last_low["price"]:
            return {"found": True, "index": i, "direction": "bearish",
                     "broken_level": last_low["price"], "swept_level": last_high["price"]}
        if trend == "bearish" and close_i > last_high["price"]:
            return {"found": True, "index": i, "direction": "bullish",
                     "broken_level": last_high["price"], "swept_level": last_low["price"]}

    return {"found": False}


def find_equal_levels(filtered_swings: list, tolerance: float) -> dict:
    """
    Groups nearby swing highs/lows into equal-level liquidity clusters.
    Returns {"equal_highs": [...], "equal_lows": [...]} where each entry
    is a list of swing dicts that cluster within `tolerance` of each other.
    Only clusters of 2+ are returned (a lone swing isn't "equal" anything).
    """
    def cluster(points):
        points = sorted(points, key=lambda s: s["price"])
        clusters, current = [], []
        for p in points:
            if not current or abs(p["price"] - current[-1]["price"]) <= tolerance:
                current.append(p)
            else:
                if len(current) >= 2:
                    clusters.append(current)
                current = [p]
        if len(current) >= 2:
            clusters.append(current)
        return clusters

    highs = [s for s in filtered_swings if s["type"] == "high"]
    lows = [s for s in filtered_swings if s["type"] == "low"]
    return {"equal_highs": cluster(highs), "equal_lows": cluster(lows)}


def detect_sweep(df: pd.DataFrame, level: float, side: str, min_sweep: float,
                  lookback_candles: int = 5, end_index: int = None) -> dict:
    """
    Checks the `lookback_candles` immediately before `end_index` (defaults
    to the end of the dataframe) for a liquidity sweep of `level`.
    side="low": expects a candle to wick BELOW level by >= min_sweep then
                close back ABOVE level (bullish reclaim).
    side="high": expects a candle to wick ABOVE level by >= min_sweep then
                 close back BELOW level (bearish reclaim).
    Returns {"swept": bool, "index": int|None, "extreme": float|None}
    """
    n = len(df)
    end_index = n if end_index is None else min(end_index + 1, n)
    start = max(0, end_index - lookback_candles)
    for i in range(start, end_index):
        low_i = float(df["low"].iloc[i])
        high_i = float(df["high"].iloc[i])
        close_i = float(df["close"].iloc[i])
        if side == "low":
            if low_i < (level - min_sweep) and close_i > level:
                return {"swept": True, "index": i, "extreme": low_i}
        elif side == "high":
            if high_i > (level + min_sweep) and close_i < level:
                return {"swept": True, "index": i, "extreme": high_i}
    return {"swept": False, "index": None, "extreme": None}
