"""
XAUUSD Telegram Signal Bot — single-run entry point.

Unlike a traditional always-on bot, this is designed to be triggered
repeatedly by GitHub Actions' cron scheduler (see .github/workflows/
signal_bot.yml) — every run does ONE check and exits. Cooldown state
(so you don't get the same alert spammed every 15 minutes) is persisted
in state.json, which the workflow commits back to the repo after each run.

Flow:
  1. Load state.json (last alert time/direction)
  2. Pull latest XAU/USD candles (price_data.py, free API)
  3. Check technical conditions (strategy.py)
  4. If a setup fires and we're not in cooldown, check fundamentals
  5. Send a Telegram alert
  6. Save updated state.json
"""

import json
import logging
import os
import datetime as dt

import config
import price_data
import strategy
import fundamentals
import telegram_alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def load_state() -> dict:
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Could not read state file, starting fresh: %s", e)
    return {"last_alert_time": None, "last_alert_direction": None}


def save_state(state: dict):
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f)


def cooldown_active(state: dict, direction: str) -> bool:
    if not state.get("last_alert_time"):
        return False
    if state.get("last_alert_direction") != direction:
        return False
    last_time = dt.datetime.fromisoformat(state["last_alert_time"])
    elapsed = (dt.datetime.utcnow() - last_time).total_seconds() / 60
    return elapsed < config.COOLDOWN_MINUTES


def run():
    state = load_state()

    df = price_data.get_candles()
    if df.empty:
        log.warning("No candle data this run — exiting without alert.")
        return

    result = strategy.check_technical_conditions(df)
    log.info("Technical check: %s", result["reason"])

    if result["signal"] is None:
        return

    if cooldown_active(state, result["signal"]):
        log.info("Signal %s suppressed — within cooldown window.", result["signal"])
        return

    fund = fundamentals.evaluate_fundamentals()
    log.info(
        "Fundamentals: news_blackout=%s dxy=%s headline_bias=%s",
        fund["news_blackout"], fund["dxy_bias"], fund["headline_bias"],
    )

    message = telegram_alerts.format_signal(result, fund)
    sent = telegram_alerts.send_message(message)

    if sent:
        state["last_alert_time"] = dt.datetime.utcnow().isoformat()
        state["last_alert_direction"] = result["signal"]
        save_state(state)
        log.info("Alert sent: %s", result["signal"])
    else:
        log.error("Alert generation succeeded but Telegram send failed.")


if __name__ == "__main__":
    run()
