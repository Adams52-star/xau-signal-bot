"""
Central configuration for the XAUUSD Telegram Signal Bot.

This bot is designed to run as a free scheduled GitHub Actions job in a
PUBLIC repo. That means secrets (API keys, bot tokens) must NEVER be
hardcoded here — they're read from environment variables, which you set
as GitHub Actions "Secrets" (Settings → Secrets and variables → Actions).
Anyone can see this file's code, but not your actual key values.

For local testing, export the variables in your terminal session before
running, e.g.:
    export TWELVEDATA_API_KEY=xxxx
    export TELEGRAM_BOT_TOKEN=xxxx
    export TELEGRAM_CHAT_ID=xxxx
"""

import os

# ── TWELVE DATA (free gold price API) ──────────────────────────────────
# Sign up free at https://twelvedata.com (free tier: 800 requests/day,
# 8/minute — plenty for a check every 15 minutes).
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
SYMBOL = "XAU/USD"
INTERVAL = "15min"          # options: 1min, 5min, 15min, 30min, 1h, 4h, 1day
CANDLES_TO_FETCH = 200

# ── TELEGRAM ─────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── STATE FILE (used for cooldown tracking between GitHub Actions runs) ─
STATE_FILE = "state.json"
COOLDOWN_MINUTES = 30       # don't re-alert the same setup within this window

# ── TECHNICAL STRATEGY PARAMETERS ──────────────────────────────────────
SWING_LOOKBACK = 5
EMA_TREND_PERIOD = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MIN_SWEEP_PIPS = 1.5

# ── FUNDAMENTAL FILTER PARAMETERS ──────────────────────────────────────
NEWS_BLACKOUT_MINUTES_BEFORE = 30
NEWS_BLACKOUT_MINUTES_AFTER = 30
HIGH_IMPACT_KEYWORDS = [
    "Non-Farm", "NFP", "FOMC", "Interest Rate", "CPI",
    "Federal Funds", "Fed Chair", "PCE", "Unemployment Rate"
]

GOLD_NEWS_RSS_FEEDS = [
    "https://www.investing.com/rss/news_285.rss",   # commodities news
    "https://www.kitco.com/rss/KitcoNews.xml",
]
GOLD_BULLISH_KEYWORDS = ["safe haven", "rate cut", "dollar weak", "inflation fear", "geopolitical tension", "gold rally", "gold surge"]
GOLD_BEARISH_KEYWORDS = ["rate hike", "dollar strength", "risk-on", "gold falls", "gold drops", "hawkish"]
