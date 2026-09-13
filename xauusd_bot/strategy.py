"""
Technical condition engine for XAUUSD.

This ships with a starter strategy (trend filter + liquidity sweep +
break-of-structure confirmation + RSI filter) so the bot is usable out of
the box. Since your exact SMC rules aren't finalized yet, treat this as a
swappable module: replace `check_technical_conditions()` with your own
logic whenever you're ready — everything downstream (fundamentals,
Telegram alerts) stays the same.
"""

import pandas as pd
import config


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _find_swings(df: pd.DataFrame, lookback: int):
    """Return indices of confirmed swing highs and swing lows."""
    highs, lows = [], []
    for i in range(lookback, len(df) - lookback):
        window = df.iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == window["high"].max():
            highs.append(i)
        if df["low"].iloc[i] == window["low"].min():
            lows.append(i)
    return highs, lows


def check_technical_conditions(df: pd.DataFrame) -> dict:
    """
    Evaluate the starter strategy against the latest candles.

    Returns a dict:
        {
            "signal": "BUY" | "SELL" | None,
            "reason": str,
            "price": float,
        }
    """
    if df.empty or len(df) < max(config.EMA_TREND_PERIOD, config.RSI_PERIOD) + config.SWING_LOOKBACK * 2:
        return {"signal": None, "reason": "Not enough data yet", "price": None}

    df = df.copy()
    df["ema_trend"] = _ema(df["close"], config.EMA_TREND_PERIOD)
    df["rsi"] = _rsi(df["close"], config.RSI_PERIOD)

    highs, lows = _find_swings(df, config.SWING_LOOKBACK)
    last_close = df["close"].iloc[-1]
    last_ema = df["ema_trend"].iloc[-1]
    last_rsi = df["rsi"].iloc[-1]
    last_low = df["low"].iloc[-1]
    last_high = df["high"].iloc[-1]

    uptrend = last_close > last_ema
    downtrend = last_close < last_ema

    # --- Bullish setup: sweep of a recent swing low, then close back above it,
    #     while price is in an EMA uptrend and RSI is not overbought ---
    if lows and uptrend and last_rsi < config.RSI_OVERBOUGHT:
        recent_low_idx = lows[-1]
        recent_low_price = df["low"].iloc[recent_low_idx]
        swept = last_low < (recent_low_price - config.MIN_SWEEP_PIPS) and last_close > recent_low_price
        if swept:
            return {
                "signal": "BUY",
                "reason": (
                    f"Liquidity sweep below swing low ({recent_low_price:.2f}) with close back above, "
                    f"price above EMA{config.EMA_TREND_PERIOD} (uptrend), RSI {last_rsi:.1f}"
                ),
                "price": last_close,
            }

    # --- Bearish setup: sweep of a recent swing high, then close back below it,
    #     while price is in an EMA downtrend and RSI is not oversold ---
    if highs and downtrend and last_rsi > config.RSI_OVERSOLD:
        recent_high_idx = highs[-1]
        recent_high_price = df["high"].iloc[recent_high_idx]
        swept = last_high > (recent_high_price + config.MIN_SWEEP_PIPS) and last_close < recent_high_price
        if swept:
            return {
                "signal": "SELL",
                "reason": (
                    f"Liquidity sweep above swing high ({recent_high_price:.2f}) with close back below, "
                    f"price below EMA{config.EMA_TREND_PERIOD} (downtrend), RSI {last_rsi:.1f}"
                ),
                "price": last_close,
            }

    return {"signal": None, "reason": "No technical setup met", "price": last_close}
