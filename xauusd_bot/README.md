# XAUUSD Telegram Signal Bot (Zero-Cost Version)

A signal-only bot for XAU/USD (gold) that checks a technical setup plus
fundamental filters (USD news, DXY trend, gold headlines) and sends
alerts to Telegram — running entirely on **free infrastructure**, no VPS,
no server, nothing installed on your own machine.

## How it works

```
GitHub Actions (free scheduled cron, every 15 min)
      │
      ▼
price_data.py  →  free XAU/USD candles from TwelveData
      │
      ▼
strategy.py (technical check)
      │
      ▼ (if a setup fires and not in cooldown)
fundamentals.py (news calendar + DXY + gold headlines)
      │
      ▼
telegram_alerts.py  →  your Telegram
```

Every 15 minutes, GitHub spins up a temporary free Linux runner, runs
`main.py` once, and shuts it down. No always-on machine required — GitHub
is doing that part for free. Cooldown tracking between runs is stored in
`state.json`, which the workflow commits back to your repo automatically.

## Cost: $0

- **TwelveData** free tier: 800 requests/day (this uses ~96/day) — no card required
- **GitHub Actions**: unlimited free minutes on a **public** repository
- **Telegram Bot API**: free
- Economic calendar + RSS news feeds: free, no key required

## 1. Get a free TwelveData API key

1. Go to twelvedata.com and sign up for the free plan.
2. Copy your API key from the dashboard.

## 2. Create your Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts.
2. Copy the token it gives you.
3. Message your new bot once (anything), then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   and find your `chat.id` in the JSON response.

## 3. Put this code on GitHub

1. Create a **public** GitHub repository (public = unlimited free Actions
   minutes; private also works but is capped at 2,000 free min/month,
   which is tight at a 15-min interval).
2. Upload everything in this folder to that repo (keep the `.github`
   folder — that's what makes the schedule work).

## 4. Add your secrets

In your repo: **Settings → Secrets and variables → Actions → New
repository secret**. Add three:
- `TWELVEDATA_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

These stay encrypted and are never visible in your code, even though the
repo itself is public.

## 5. Turn it on

The workflow (`.github/workflows/signal_bot.yml`) is already set to run
every 15 minutes automatically once it's on GitHub. To test it
immediately instead of waiting:
- Go to the **Actions** tab → "XAUUSD Signal Check" → **Run workflow**
  (this uses the `workflow_dispatch` trigger built into the file).
- Check the run logs there, and check your Telegram.

## About the current strategy

`strategy.py` now runs a full SMC confluence engine (`market_structure.py`,
`poi.py`, `levels.py`, `patterns.py`), following this exact pipeline:

1. **Structure**: finds swing highs/lows, classifies trend (HH+HL vs
   LH+LL), and looks for a recent CHoCH (Change of Character) — the
   trend reversing.
2. **Liquidity sweep**: requires a sweep-and-reclaim of the opposing
   swing point right before that CHoCH.
3. **Order block**: finds the last opposite-colored candle before the
   CHoCH's impulsive move — this is the entry zone.
4. **Entry trigger**: only fires once price has actually retraced back
   into that order block, and only if the block hasn't been invalidated.
5. **Bonus confluence** (strengthens the read, never gates the signal
   alone): FVG overlap with the order block, proximity to the previous
   day's high/low, a round-number key level, a matching QML pattern
   shape, or a CRT-style sweep of the previous day's range.
6. **R:R gate**: computes entry/stop/target and only sends the alert if
   risk:reward clears `MIN_RISK_REWARD` (1.5 by default) — a fully
   confirmed setup with poor R:R is skipped, not sent.

This scans REVERSAL setups only (CHoCH-based) — trend-continuation (BOS)
trades are deliberately out of scope for this engine.

Honest limitations, stated plainly:
- Single timeframe only — this bot has one data feed, so it runs the
  "LTF" half of a proper top-down HTF→LTF process. A stricter version
  would confirm higher-timeframe bias on a separate feed first.
- QML and CRT detection are simplified, rule-based approximations of
  concepts that are partly subjective even for experienced traders —
  they're treated as bonus confluence, never a standalone trigger.
- Breaker blocks are tracked as an invalidation check (an order block
  that gets closed through is treated as broken, not silently reused),
  but the engine doesn't yet trade breaker blocks as their own setup.

Because this requires several conditions to align at once (sweep + CHoCH
+ untouched order block + acceptable R:R, all within a recent window),
it will fire far less often than the old starter logic — that's
intentional, not a bug. Check the Actions run logs any time to see the
`reason` field explaining exactly which step a given cycle failed at.
1. Upcoming high-impact USD news (NFP, FOMC, CPI, etc.) via a free
   economic calendar feed — flags nearby signals rather than blocking
   them outright.
2. DXY short-term trend (bullish/bearish/neutral for the dollar) via a
   free public quote.
3. Recent gold-related headlines from RSS feeds, keyword-tagged
   bullish/bearish.

## Important notes

- This bot **only sends alerts** — no trade execution.
- GitHub's free cron scheduler can lag a few minutes under load; fine for
  a 15-minute-interval alert bot, not fine for latency-sensitive
  execution.
- The free price feed and news sources can occasionally be rate-limited
  or briefly unavailable — the bot logs a warning and simply skips that
  cycle rather than crashing; the next scheduled run tries again.
- No warranty on trading outcomes — this is infrastructure, not
  financial advice.
