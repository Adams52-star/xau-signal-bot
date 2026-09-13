"""
Fundamental condition checks for XAUUSD:
  1. High-impact USD news calendar (avoid/flag signals near NFP, FOMC, CPI, etc.)
  2. DXY (dollar index) trend correlation
  3. Gold-related headline scan for directional bias (keyword-based sentiment)

These are intentionally simple and transparent (keyword/threshold based)
rather than a black-box ML sentiment model, so you can see exactly why a
signal was flagged or allowed. Swap in a paid news/calendar API later if
you want more precision.
"""

import logging
import datetime as dt
import requests
import feedparser

import config

log = logging.getLogger("fundamentals")

FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def get_upcoming_high_impact_news():
    """
    Pulls this week's economic calendar (ForexFactory feed) and returns
    events matching HIGH_IMPACT_KEYWORDS that fall within the blackout
    window around now.
    """
    try:
        resp = requests.get(FF_CALENDAR_URL, timeout=10)
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        log.warning("Could not fetch economic calendar: %s", e)
        return []

    now = dt.datetime.utcnow()
    before = dt.timedelta(minutes=config.NEWS_BLACKOUT_MINUTES_BEFORE)
    after = dt.timedelta(minutes=config.NEWS_BLACKOUT_MINUTES_AFTER)

    flagged = []
    for ev in events:
        title = ev.get("title", "")
        currency = ev.get("currency", "")
        if currency != "USD":
            continue
        if not any(kw.lower() in title.lower() for kw in config.HIGH_IMPACT_KEYWORDS):
            continue
        try:
            event_time = dt.datetime.strptime(ev["date"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
        except Exception:
            continue
        if (now - before) <= event_time <= (now + after):
            flagged.append({"title": title, "time": event_time.isoformat()})

    return flagged


def get_dxy_bias() -> str:
    """
    Returns 'bullish_usd', 'bearish_usd', or 'neutral' based on DXY's
    short-term trend, using a free public quote (Stooq, daily granularity).
    """
    try:
        resp = requests.get("https://stooq.com/q/d/l/?s=dxy&i=d", timeout=10)
        lines = resp.text.strip().splitlines()
        if len(lines) > 5:
            closes = [float(line.split(",")[4]) for line in lines[-6:] if line and line[0].isdigit()]
            if len(closes) >= 2 and closes[-1] > closes[0]:
                return "bullish_usd"
            elif len(closes) >= 2 and closes[-1] < closes[0]:
                return "bearish_usd"
    except Exception as e:
        log.warning("DXY fallback fetch failed: %s", e)

    return "neutral"


def get_gold_headline_bias() -> dict:
    """
    Scans configured RSS feeds for recent gold-related headlines and
    tags overall bias by keyword matching. Returns:
        {"bias": "bullish"|"bearish"|"neutral", "matched_headlines": [...]}
    """
    bullish_hits, bearish_hits, matched = 0, 0, []

    for feed_url in config.GOLD_NEWS_RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            log.warning("Could not parse feed %s: %s", feed_url, e)
            continue

        for entry in parsed.entries[:15]:
            title = entry.get("title", "").lower()
            if "gold" not in title and "xau" not in title:
                continue
            hit = False
            if any(kw in title for kw in config.GOLD_BULLISH_KEYWORDS):
                bullish_hits += 1
                hit = True
            if any(kw in title for kw in config.GOLD_BEARISH_KEYWORDS):
                bearish_hits += 1
                hit = True
            if hit:
                matched.append(entry.get("title"))

    if bullish_hits > bearish_hits:
        bias = "bullish"
    elif bearish_hits > bullish_hits:
        bias = "bearish"
    else:
        bias = "neutral"

    return {"bias": bias, "matched_headlines": matched[:5]}


def evaluate_fundamentals() -> dict:
    """
    Aggregates all fundamental checks into one result used by main.py.
    """
    news = get_upcoming_high_impact_news()
    dxy_bias = get_dxy_bias()
    headline_bias = get_gold_headline_bias()

    return {
        "news_blackout": len(news) > 0,
        "flagged_news": news,
        "dxy_bias": dxy_bias,
        "headline_bias": headline_bias["bias"],
        "matched_headlines": headline_bias["matched_headlines"],
    }
