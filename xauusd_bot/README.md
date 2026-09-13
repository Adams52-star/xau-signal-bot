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

`strategy.py` is a **starter setup**: EMA trend filter + liquidity sweep
of a recent swing high/low + RSI filter. Simple and readable on purpose,
so you can replace `check_technical_conditions()` with your own
SMC/liquidity-mapping rules later without touching anything else.

`fundamentals.py` checks:
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
