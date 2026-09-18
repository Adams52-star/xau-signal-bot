"""
QML (Quasimodo) pattern check.

Honest limitation up front: QML is a visually-judged pattern even for
experienced traders — the exact "shoulder" and "head" boundaries are
somewhat subjective. This function checks the strict structural
definition (head extends beyond both shoulders, the break of structure
after the head, then price returning toward the first shoulder's level)
on the last 4 alternating swing points. Treat a match as ONE extra piece
of supporting confluence, never as a standalone trigger — that's why
strategy.py only ever adds this to the confluence list, it never gates
a signal on its own.

Bearish QML (expect SELL near the return level):
  shoulder_high (H) -> low (L) -> head_high (H, > shoulder_high)
  -> break_low (L, < shoulder's preceding low) -> price rallies back
  toward shoulder_high.

Bullish QML is the exact mirror.
"""


def check_qml(filtered_swings: list, current_price: float, proximity: float) -> dict:
    """
    Looks at the last 4 alternating swings for a QML shape.
    Returns {"found": bool, "direction": "bullish"|"bearish"|None,
             "neckline": float|None} — "found" only True if the shape
    matches AND current price is within `proximity` of the neckline
    (the shoulder level being retested).
    """
    if len(filtered_swings) < 4:
        return {"found": False, "direction": None, "neckline": None}

    last4 = filtered_swings[-4:]
    types = [s["type"] for s in last4]

    # Bearish QML shape: H, L, H, L  where 3rd > 1st (head) and 4th < 2nd (structure break)
    if types == ["high", "low", "high", "low"]:
        shoulder_high, low1, head_high, break_low = last4[0]["price"], last4[1]["price"], last4[2]["price"], last4[3]["price"]
        if head_high > shoulder_high and break_low < low1:
            if abs(current_price - shoulder_high) <= proximity:
                return {"found": True, "direction": "bearish", "neckline": shoulder_high}

    # Bullish QML shape: L, H, L, H  where 3rd < 1st (head) and 4th > 2nd (structure break)
    if types == ["low", "high", "low", "high"]:
        shoulder_low, high1, head_low, break_high = last4[0]["price"], last4[1]["price"], last4[2]["price"], last4[3]["price"]
        if head_low < shoulder_low and break_high > high1:
            if abs(current_price - shoulder_low) <= proximity:
                return {"found": True, "direction": "bullish", "neckline": shoulder_low}

    return {"found": False, "direction": None, "neckline": None}
