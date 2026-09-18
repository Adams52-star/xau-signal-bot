"""
Points of interest (POI): Fair Value Gaps and Order Blocks, with
mitigation/breaker tracking.

Definitions used:
- FVG (Fair Value Gap): a 3-candle imbalance. Bullish FVG at candle i
  exists when candle[i-1].high < candle[i+1].low (a gap nothing traded
  through). Bearish FVG: candle[i-1].low > candle[i+1].high.
- Order Block (OB): the last opposite-colored candle before the
  impulsive move that caused a BOS/CHoCH. Bullish OB = last down-close
  candle before an up-impulse. Bearish OB = last up-close candle before
  a down-impulse.
- Mitigated: price has traded back into the zone at least once since it
  formed (before the current/last candle).
- Breaker: an OB that price later closed all the way through (invalidating
  it as support/resistance) — it then acts with the opposite bias.
"""

import pandas as pd


def find_fvgs(df: pd.DataFrame) -> list:
    """
    Scans all 3-candle windows for Fair Value Gaps.
    Returns a list of:
        {"index": i, "type": "bullish"|"bearish", "top": float, "bottom": float}
    `index` is the middle candle of the 3-candle pattern (the imbalance candle).
    """
    fvgs = []
    n = len(df)
    for i in range(1, n - 1):
        prev_high = float(df["high"].iloc[i - 1])
        prev_low = float(df["low"].iloc[i - 1])
        next_high = float(df["high"].iloc[i + 1])
        next_low = float(df["low"].iloc[i + 1])

        if prev_high < next_low:
            fvgs.append({"index": i, "type": "bullish", "top": next_low, "bottom": prev_high})
        elif prev_low > next_high:
            fvgs.append({"index": i, "type": "bearish", "top": prev_low, "bottom": next_high})
    return fvgs


def _is_mitigated(df: pd.DataFrame, zone_index: int, top: float, bottom: float, up_to_index: int) -> bool:
    """Has any candle from zone_index+1 up to (but not including) up_to_index traded into [bottom, top]?"""
    for j in range(zone_index + 1, up_to_index):
        if float(df["low"].iloc[j]) <= top and float(df["high"].iloc[j]) >= bottom:
            return True
    return False


def find_order_block(df: pd.DataFrame, impulse_index: int, direction: str, max_lookback: int = 10) -> dict:
    """
    Given the candle index that caused a BOS/CHoCH (`impulse_index`) and
    its `direction` ("bullish" or "bearish"), searches backward for the
    nearest opposite-colored candle — that candle's range is the OB.

    Returns {"found": bool, "index": int, "top": float, "bottom": float,
             "type": "bullish"|"bearish"} or {"found": False} if none found
    within max_lookback candles.
    """
    want_bearish_candle = direction == "bullish"  # bullish OB = last DOWN candle
    start = max(0, impulse_index - max_lookback)

    for j in range(impulse_index - 1, start - 1, -1):
        open_j = float(df["open"].iloc[j])
        close_j = float(df["close"].iloc[j])
        is_bearish_candle = close_j < open_j
        is_bullish_candle = close_j > open_j

        if want_bearish_candle and is_bearish_candle:
            return {
                "found": True, "index": j,
                "top": float(df["high"].iloc[j]), "bottom": float(df["low"].iloc[j]),
                "type": "bullish",
            }
        if (not want_bearish_candle) and is_bullish_candle:
            return {
                "found": True, "index": j,
                "top": float(df["high"].iloc[j]), "bottom": float(df["low"].iloc[j]),
                "type": "bearish",
            }
    return {"found": False}


def price_in_zone(price: float, top: float, bottom: float) -> bool:
    return bottom <= price <= top


def is_broken(df: pd.DataFrame, ob: dict, up_to_index: int) -> bool:
    """
    Has price closed all the way through this OB since it formed,
    invalidating it (it would then act as a breaker block instead)?
    Bullish OB is broken if a later candle CLOSES below its bottom.
    Bearish OB is broken if a later candle CLOSES above its top.
    """
    for j in range(ob["index"] + 1, up_to_index):
        close_j = float(df["close"].iloc[j])
        if ob["type"] == "bullish" and close_j < ob["bottom"]:
            return True
        if ob["type"] == "bearish" and close_j > ob["top"]:
            return True
    return False


def annotate_ob(df: pd.DataFrame, ob: dict, current_index: int) -> dict:
    """
    Adds mitigation and breaker status to an order block dict.
    """
    ob = dict(ob)
    ob["mitigated"] = _is_mitigated(df, ob["index"], ob["top"], ob["bottom"], current_index)
    ob["broken"] = is_broken(df, ob, current_index)
    return ob
