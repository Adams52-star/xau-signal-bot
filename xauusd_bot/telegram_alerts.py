"""
Sends formatted signal alerts to Telegram via the Bot API.
"""

import logging
import requests
import config

log = logging.getLogger("telegram_alerts")

API_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"


def send_message(text: str) -> bool:
    try:
        resp = requests.post(
            API_URL,
            data={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error("Failed to send Telegram message: %s", e)
        return False


def format_signal(signal: dict, fundamentals: dict) -> str:
    direction = signal["signal"]
    emoji = "🟢" if direction == "BUY" else "🔴"

    lines = [
        f"{emoji} <b>{direction} SIGNAL — XAUUSD</b>",
        f"Price: <b>{signal['price']:.2f}</b>",
        "",
        "<b>Confluences:</b>",
    ]
    for c in signal["confluences"]:
        lines.append(f"  • {c}")

    lines += [
        "",
        f"Entry: <b>{signal['entry']:.2f}</b>",
        f"Stop loss: <b>{signal['stop_loss']:.2f}</b>",
        f"Take profit: <b>{signal['take_profit']:.2f}</b>",
        f"Risk:Reward — <b>1:{signal['risk_reward']:.2f}</b>",
        "",
        f"<b>DXY bias:</b> {fundamentals['dxy_bias']}",
        f"<b>Gold headline bias:</b> {fundamentals['headline_bias']}",
    ]

    if fundamentals["matched_headlines"]:
        lines.append("Recent headlines:")
        for h in fundamentals["matched_headlines"]:
            lines.append(f"  • {h}")

    if fundamentals["news_blackout"]:
        lines.append("")
        lines.append("⚠️ <b>Caution:</b> high-impact USD news nearby —")
        for ev in fundamentals["flagged_news"]:
            lines.append(f"  • {ev['title']} at {ev['time']} UTC")

    return "\n".join(lines)
