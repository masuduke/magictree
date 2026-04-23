"""
config.py  —  All settings. Edit via Render environment variables.
"""
import os

# ─────────────────────────────────────────
# TRADING SETTINGS
# ─────────────────────────────────────────
PAPER_TRADE        = os.getenv('PAPER_TRADE', 'true').lower() == 'true'
INITIAL_CAPITAL    = float(os.getenv('INITIAL_CAPITAL', '500'))
RISK_PER_TRADE_PCT = float(os.getenv('RISK_PER_TRADE_PCT', '0.01'))   # 2% risk
TAKE_PROFIT_PCT    = float(os.getenv('TAKE_PROFIT_PCT', '0.02'))   # 1% TP
STOP_LOSS_PCT      = float(os.getenv('STOP_LOSS_PCT',     '0.01'))   # 1% SL
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY', '2'))

# ─────────────────────────────────────────
# ASSETS TO SCAN
# ─────────────────────────────────────────

# Crypto — scanned 24/7 via Binance
CRYPTO_ASSETS = ['BTC/USDT', 'ETH/USDT']

# Stocks — scanned during market hours (14:00–21:00 UTC Mon–Fri)
# All executable on eToro
STOCK_ASSETS = {
    'AAPL':  'Apple',
    'TSLA':  'Tesla',
    'NVDA':  'Nvidia',
    'AMZN':  'Amazon',
    'META':  'Meta',
    'MSFT':  'Microsoft',
}

# Commodities — scanned 24/5 via yfinance futures
# All executable on eToro
COMMODITY_ASSETS = {
    'GC=F': 'GOLD',
    #'SI=F': 'SILVER',  # Blocked - too volatile
    #'CL=F': 'OIL',  # Blocked - Middle East war
}

# ─────────────────────────────────────────
# TECHNICAL INDICATOR SETTINGS
# ─────────────────────────────────────────
EMA_FAST        = 9
EMA_SLOW        = 21
RSI_PERIOD      = 14
RSI_LOWER_BAND  = 45
RSI_UPPER_BAND  = 55
MIN_CONFIDENCE  = 70   # only trade signals above this %

# ─────────────────────────────────────────
# API KEYS  (set all in Render dashboard)
# ─────────────────────────────────────────

ANTHROPIC_API_KEY      = os.getenv('ANTHROPIC_API_KEY', '')

# ── eToro (main broker — handles ALL asset types) ──────────────────────────
ETORO_API_KEY          = os.getenv('ETORO_API_KEY', '')
# NOTE: Create an "Agent Portfolio" in eToro settings and fund it with £500
# The API key is scoped ONLY to that portfolio — your main account is safe

# ── Binance (optional — only needed if you want crypto on Binance instead) ──
BINANCE_API_KEY        = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY     = os.getenv('BINANCE_SECRET_KEY', '')

# ── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN     = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID       = os.getenv('TELEGRAM_CHAT_ID', '')

# ── Social media ────────────────────────────────────────────────────────────
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
INSTAGRAM_ACCOUNT_ID   = os.getenv('INSTAGRAM_ACCOUNT_ID', '')
YOUTUBE_REFRESH_TOKEN  = os.getenv('YOUTUBE_REFRESH_TOKEN', '')
YOUTUBE_CLIENT_ID      = os.getenv('YOUTUBE_CLIENT_ID', '')
YOUTUBE_CLIENT_SECRET  = os.getenv('YOUTUBE_CLIENT_SECRET', '')
TIKTOK_ACCESS_TOKEN    = os.getenv('TIKTOK_ACCESS_TOKEN', '')
CLOUDINARY_URL         = os.getenv('CLOUDINARY_URL', '')

# ─────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────
SCAN_INTERVAL_MINUTES  = int(os.getenv('SCAN_INTERVAL_MINUTES', '15'))
DAILY_POST_HOUR        = int(os.getenv('DAILY_POST_HOUR', '20'))

# ─────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────
DATA_FILE    = 'data/trades.json'
EQUITY_FILE  = 'data/equity.json'
SLIDES_DIR   = 'outputs/slides'
VIDEOS_DIR   = 'outputs/videos'

# ─────────────────────────────────────────
# BRANDING
# ─────────────────────────────────────────
CHANNEL_NAME    = os.getenv('CHANNEL_NAME',    '£500 Trading Challenge')
CHANNEL_HANDLE  = os.getenv('CHANNEL_HANDLE',  '@TradingFromZero')
CURRENCY_SYMBOL = '£'
