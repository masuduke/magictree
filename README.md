# £500 AI Trading Bot — Complete Setup Guide

## What This System Does (Fully Automatic)
```
Every 15 min → Scans BTC, ETH, Gold for signals
            → Opens trades automatically (paper or real)
            → Closes at Take Profit or Stop Loss
            → Sends Telegram alert

Every day 8pm → Claude AI writes script + captions
             → Creates slides + 30s Reel video
             → Posts to Instagram, YouTube, TikTok
             → Sends you a daily summary on Telegram
```

---

## STEP 1 — Get Your Accounts Ready

### 1A. GitHub (to host the code)
1. Go to https://github.com and create a free account
2. Click **New repository** → name it `trading-bot` → **Create**
3. Upload all these files into it (drag and drop)

### 1B. Render (to run the bot 24/7)
1. Go to https://render.com → sign up free
2. Connect your GitHub account
3. Click **New → Background Worker** → select your `trading-bot` repo
4. Render reads `render.yaml` automatically

---

## STEP 2 — Get Your API Keys

### 2A. Anthropic API Key (Claude AI for content)
1. Go to https://console.anthropic.com
2. Sign in → **API Keys** → **Create Key**
3. Copy it → paste in Render as `ANTHROPIC_API_KEY`
4. Add £5–£10 credit (content generation costs ~£0.10/day)

### 2B. Telegram Bot (for real-time alerts)
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Choose a name (e.g. "My Trading Bot") and username
3. BotFather gives you a **token** → copy it
4. Start a chat with your new bot → send any message
5. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
6. Find `"chat":{"id":...}` → that number is your `TELEGRAM_CHAT_ID`

### 2C. Cloudinary (hosts images for Instagram)
1. Go to https://cloudinary.com → free account (25GB storage)
2. Dashboard → **API Keys** → copy the `CLOUDINARY_URL` (format: `cloudinary://key:secret@cloudname`)

### 2D. Instagram Graph API
1. Go to https://developers.facebook.com → create app (type: **Business**)
2. Add **Instagram Graph API** product
3. Connect your Instagram **Creator or Business** account (not personal)
4. Generate a **long-lived token** (60 days):
   ```
   https://graph.facebook.com/oauth/access_token?
     client_id=YOUR_APP_ID
     &client_secret=YOUR_APP_SECRET
     &grant_type=fb_exchange_token
     &fb_exchange_token=SHORT_LIVED_TOKEN
   ```
5. Get your **Instagram Account ID**:
   ```
   https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_TOKEN
   ```

> ⚠️ Token expires in 60 days — set a reminder to refresh it

### 2E. YouTube Data API (for Shorts upload)
1. Go to https://console.cloud.google.com
2. Create project → Enable **YouTube Data API v3**
3. **Credentials → OAuth 2.0 Client ID** → Desktop app
4. Download the JSON, run this script once to get refresh token:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=['https://www.googleapis.com/auth/youtube.upload']
)
creds = flow.run_local_server(port=0)
print("REFRESH TOKEN:", creds.refresh_token)
print("CLIENT ID:", creds.client_id)
print("CLIENT SECRET:", creds.client_secret)
```

5. Copy the 3 values → paste in Render env vars

### 2F. TikTok Content Posting API
1. Go to https://developers.tiktok.com → create app
2. Apply for **Content Posting API** access (takes 1–3 days to approve)
3. Complete OAuth flow to get access token
4. Paste as `TIKTOK_ACCESS_TOKEN`

### 2G. Binance API (only needed for REAL trades — keep PAPER_TRADE=true until confident)
1. Go to https://binance.com → account → API Management
2. Create API key (enable Spot trading, disable withdrawals)
3. Copy Key + Secret → paste in Render

---

## STEP 3 — Deploy on Render

1. Go to your Render dashboard → Background Worker
2. Click **Environment** tab → add all your keys:

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | sk-ant-... |
| `TELEGRAM_BOT_TOKEN` | 123456:ABC... |
| `TELEGRAM_CHAT_ID` | -123456789 |
| `CLOUDINARY_URL` | cloudinary://key:secret@name |
| `INSTAGRAM_ACCESS_TOKEN` | EAAG... |
| `INSTAGRAM_ACCOUNT_ID` | 17841... |
| `YOUTUBE_CLIENT_ID` | ...apps.googleusercontent.com |
| `YOUTUBE_CLIENT_SECRET` | GOCSPX-... |
| `YOUTUBE_REFRESH_TOKEN` | 1//... |
| `TIKTOK_ACCESS_TOKEN` | ... |
| `PAPER_TRADE` | true |
| `INITIAL_CAPITAL` | 500 |
| `CHANNEL_NAME` | £500 Trading Challenge |
| `CHANNEL_HANDLE` | @YourHandle |

3. Click **Save Changes** → Render auto-deploys

4. Click **Logs** tab → you should see:
   ```
   🚀 Trading Bot starting…
   📝 PAPER TRADE | Capital: £500
   🔍 Scanning markets...
   ```

---

## STEP 4 — Go Live (When Ready)

When you have watched paper trades for 1–2 weeks and results look good:

1. Go to Render → Environment
2. Change `PAPER_TRADE` from `true` to `false`
3. Save — bot now trades real money on Binance

> ⚠️ Only change to live after verifying the paper results make sense

---

## STEP 5 — Monitor Everything

**Telegram** — you get instant alerts for:
- Every signal detected
- Every trade opened
- Every trade closed (win or loss)
- Daily summary + slide preview

**Instagram / YouTube / TikTok** — the bot posts automatically at 8pm every day

---

## Cost Breakdown (Monthly)

| Service | Cost |
|---------|------|
| Render Starter | $7/month (~£5.50) |
| Anthropic API | ~£3–5/month |
| Cloudinary | Free (25GB) |
| Everything else | Free |
| **Total** | **~£9–11/month** |

---

## Troubleshooting

**Bot not posting to Instagram?**
- Token may have expired → refresh it (valid 60 days)
- Account must be Business or Creator type, not personal

**No trades firing?**
- Markets may genuinely have no signals (normal)
- Check logs for "No signals this scan"

**Video creation failing?**
- ffmpeg must be installed (Render build command handles this)
- Check logs for moviepy errors

**Balance not updating?**
- Trades close at TP/SL based on next price scan
- In paper mode, prices are from live market data

---

## File Structure
```
trading-bot/
├── main.py                ← Brain (runs everything)
├── config.py              ← All settings
├── requirements.txt       ← Python packages
├── render.yaml            ← Render deployment config
├── modules/
│   ├── market_scanner.py  ← Finds trade signals
│   ├── trade_executor.py  ← Opens/closes trades
│   ├── trade_logger.py    ← Saves trade history
│   ├── content_generator.py ← Claude AI writes content
│   ├── slide_creator.py   ← Makes slides + video
│   ├── social_publisher.py ← Posts to platforms
│   └── notifier.py        ← Telegram alerts
├── data/
│   ├── trades.json        ← All trade history
│   └── equity.json        ← Balance + equity curve
└── outputs/
    ├── slides/            ← Generated PNG slides
    └── videos/            ← Generated MP4 Reels
```
