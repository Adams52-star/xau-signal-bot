"""
Full SMC confluence engine for XAUUSD.

Implements the exact 7-step top-down process, condensed to a single
timeframe (since this bot only has one data feed) as a strict pipeline:

  1. Determine trend + find the most recent CHoCH within the lookback
     window (structure shift = the core trigger for a reversal setup).
  2. Confirm a liquidity sweep happened just before that CHoCH.
  3. Find the order block that caused the CHoCH impulse.
  4. Require CURRENT price to actually be retraced back into that OB
     right now (the entry trigger) — not broken, not stale.
  5. Add bonus confluence where present: FVG overlap, key-level proximity,
     QML shape, CRT range alignment. These strengthen the read but never
     gate the signal on their own.
  6. Compute entry / stop loss / take profit and the resulting R:R.
  7. Only return a signal if R:R clears the configured minimum — no
     R:R, no trade, even with every other piece aligned.

Honest scope note: this treats every candle in CANDLES_TO_FETCH as one
timeframe (no true multi-timeframe HTF/LTF split, since the bot has a
single data feed). It is the LTF half of the 7-step process running on
its own — the more rigorous version would confirm HTF bias separately.
"""

import pandas as pd
import config
import market_structure as ms
import poi
import levels
import patterns


def check_technical_conditions(df: pd.DataFrame) -> dict:
    """
    Returns:
        {
            "signal": "BUY" | "SELL" | None,
            "reason": str,            # one-line summary for logs
            "price": float | None,
            "confluences": [str, ...],  # only present when signal is not None
            "entry": float | None,
            "stop_loss": float | None,
            "take_profit": float | None,
            "risk_reward": float | None,
        }
    """
    empty_result = {
        "signal": None, "reason": "", "price": None, "confluences": [],
        "entry": None, "stop_loss": None, "take_profit": None, "risk_reward": None,
    }

    min_needed = config.SWING_LOOKBACK * 2 + config.STRUCTURE_LOOKBACK_WINDOW + 5
    if df.empty or len(df) < min_needed:
        empty_result["reason"] = "Not enough data yet"
        return empty_result

    last_index = len(df) - 1
    current_price = float(df["close"].iloc[-1])

    # Step 1: structure + most recent CHoCH
    swings = ms.find_swings(df, config.SWING_LOOKBACK)
    filtered_swings = ms.filter_alternating(swings)
    choch = ms.find_recent_choch(df, filtered_swings, config.STRUCTURE_LOOKBACK_WINDOW)

    if not choch["found"]:
        empty_result["reason"] = "No recent change of character — no reversal setup"
        return empty_result

    direction = choch["direction"]
    choch_index = choch["index"]

    if last_index - choch_index > config.MAX_RETRACEMENT_WAIT_CANDLES:
        empty_result["reason"] = f"CHoCH found but too old ({last_index - choch_index} candles ago) — structure gone stale"
        return empty_result

    # Step 2: liquidity sweep just before the CHoCH
    sweep_side = "low" if direction == "bullish" else "high"
    sweep = ms.detect_sweep(
        df, level=choch["swept_level"], side=sweep_side,
        min_sweep=config.MIN_SWEEP_PIPS, lookback_candles=8, end_index=choch_index,
    )
    if not sweep["swept"]:
        empty_result["reason"] = "CHoCH found but no liquidity sweep preceded it — skipping (low quality reversal)"
        return empty_result

    # Step 3: order block from the CHoCH impulse
    ob_raw = poi.find_order_block(df, choch_index, direction, config.OB_LOOKBACK)
    if not ob_raw["found"]:
        empty_result["reason"] = "CHoCH + sweep confirmed but no clean order block found behind it"
        return empty_result

    ob = poi.annotate_ob(df, ob_raw, last_index)
    if ob["broken"]:
        empty_result["reason"] = "Order block already invalidated (price closed through it) — setup no longer valid"
        return empty_result

    # Step 4: is price retraced into the OB right now?
    last_low = float(df["low"].iloc[-1])
    last_high = float(df["high"].iloc[-1])
    in_zone = (last_low <= ob["top"]) and (last_high >= ob["bottom"])
    if not in_zone:
        empty_result["reason"] = f"CHoCH + sweep confirmed, order block at [{ob['bottom']:.2f}-{ob['top']:.2f}] not yet retested"
        return empty_result

    confluences = [
        f"Liquidity sweep of {choch['swept_level']:.2f} (extreme {sweep['extreme']:.2f})",
        f"CHoCH confirmed, breaking {choch['broken_level']:.2f}",
        f"Price retraced into {'bullish' if direction == 'bullish' else 'bearish'} order block "
        f"[{ob['bottom']:.2f}-{ob['top']:.2f}]{' (previously mitigated)' if ob['mitigated'] else ' (fresh, unmitigated)'}",
    ]

    # Step 5: bonus confluences (never gate the signal)
    fvgs = poi.find_fvgs(df)
    for fvg in fvgs:
        if fvg["type"] == ob["type"] and fvg["index"] <= last_index:
            overlap = min(fvg["top"], ob["top"]) - max(fvg["bottom"], ob["bottom"])
            if overlap > 0:
                confluences.append(f"FVG overlaps the order block ({fvg['bottom']:.2f}-{fvg['top']:.2f})")
                break

    day_levels = levels.previous_day_high_low(df)
    if day_levels["high"] is not None:
        target_level = day_levels["high"] if direction == "bullish" else day_levels["low"]
        if abs(current_price - target_level) <= config.ROUND_LEVEL_TOLERANCE * 2:
            confluences.append(f"Near previous day's {'high' if direction == 'bullish' else 'low'} ({target_level:.2f})")

    round_level = levels.nearest_round_level(current_price, config.ROUND_LEVEL_STEP)
    if abs(current_price - round_level) <= config.ROUND_LEVEL_TOLERANCE:
        confluences.append(f"Near round key level ({round_level:.2f})")

    qml = patterns.check_qml(filtered_swings, current_price, config.QML_PROXIMITY)
    if qml["found"] and qml["direction"] == direction:
        confluences.append(f"QML neckline retest near {qml['neckline']:.2f}")

    crt = levels.crt_base_range(df)
    if crt["high"] is not None:
        crt_sweep = ms.detect_sweep(
            df, level=crt["high"] if direction == "bearish" else crt["low"],
            side="high" if direction == "bearish" else "low",
            min_sweep=config.MIN_SWEEP_PIPS, lookback_candles=8, end_index=choch_index,
        )
        if crt_sweep["swept"]:
            confluences.append(f"CRT: swept outside previous day's range ({crt['date']}) before reversing")

    # Step 6: entry / stop / target / R:R
    entry = current_price
    if direction == "bullish":
        stop_loss = min(sweep["extreme"], ob["bottom"]) - config.SL_BUFFER
        candidate_targets = [s["price"] for s in filtered_swings if s["type"] == "high" and s["price"] > entry]
        if day_levels["high"] is not None and day_levels["high"] > entry:
            candidate_targets.append(day_levels["high"])
        take_profit = min(candidate_targets) if candidate_targets else None
    else:
        stop_loss = max(sweep["extreme"], ob["top"]) + config.SL_BUFFER
        candidate_targets = [s["price"] for s in filtered_swings if s["type"] == "low" and s["price"] < entry]
        if day_levels["low"] is not None and day_levels["low"] < entry:
            candidate_targets.append(day_levels["low"])
        take_profit = max(candidate_targets) if candidate_targets else None

    if take_profit is None:
        empty_result["reason"] = "Setup confirmed but no clear liquidity target found for take-profit — skipping"
        return empty_result

    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    risk_reward = (reward / risk) if risk > 0 else 0

    # Step 7: R:R gate
    if risk_reward < config.MIN_RISK_REWARD:
        empty_result["reason"] = (
            f"Full setup confirmed but R:R only {risk_reward:.2f} "
            f"(need {config.MIN_RISK_REWARD}) — skipping per rule"
        )
        return empty_result

    return {
        "signal": "BUY" if direction == "bullish" else "SELL",
        "reason": f"Full SMC confluence: {len(confluences)} factors aligned, R:R {risk_reward:.2f}",
        "price": current_price,
        "confluences": confluences,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": risk_reward,
    }
