"""
config.py v5 — Fixed
---------------------
Fixes applied:
1. EUR/GBP removed from FOREX_ASSETS (too low volatility)
2. MIN_CONFIDENCE raised to 70 (was 65)
3. MIN_STRATEGY_SCORE raised to 60 (was 55)
4. RSI bands widened slightly for more valid signals
"""
import os

# ────────────────────────────────────────────────────────────
# TRADING SETTINGS
# ────────────────────────────────────────────────────────────
PAPER_TRADE        = os.getenv('PAPER_TRADE', 'true').lower() == 'true'
INITIAL_CAPITAL    = float(os.getenv('INITIAL_CAPITAL', '500'))
RISK_PER_TRADE_PCT = float(os.getenv('RISK_PER_TRADE_PCT', '0.01'))
TAKE_PROFIT_PCT    = float(os.getenv('TAKE_PROFIT_PCT',   '0.005'))
STOP_LOSS_PCT      = float(os.getenv('STOP_LOSS_PCT',     '0.002'))
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY',   '5'))
MAX_DAILY_LOSS     = float(os.getenv('MAX_DAILY_LOSS',    '25'))
MAX_OPEN_TRADES    = int(os.getenv('MAX_OPEN_TRADES',      '3'))

# ────────────────────────────────────────────────────────────
# SIGNAL QUALITY — FIX: Raised thresholds
# ────────────────────────────────────────────────────────────
MIN_CONFIDENCE         = int(os.getenv('MIN_CONFIDENCE', '70'))      # FIX: was 65
MIN_STRATEGY_SCORE     = int(os.getenv('MIN_STRATEGY_SCORE', '60'))  # FIX: was 55
CONFIRM_HIGHER_TF      = os.getenv('CONFIRM_HIGHER_TF', 'true').lower() == 'true'
CORRELATION_CHECK      = True
MAX_SAME_DIRECTION     = 2

# ────────────────────────────────────────────────────────────
# TECHNICAL SETTINGS
# ────────────────────────────────────────────────────────────
EMA_FAST        = 9
EMA_SLOW        = 21
RSI_PERIOD      = 14
RSI_LOWER_BAND  = int(os.getenv('RSI_LOWER_BAND', '40'))   # FIX: was 42
RSI_UPPER_BAND  = int(os.getenv('RSI_UPPER_BAND', '60'))   # FIX: was 58

# ────────────────────────────────────────────────────────────
# ASSET UNIVERSE
# ────────────────────────────────────────────────────────────

# Crypto — 24/7
CRYPTO_ASSETS = {
    'BTC/USDT':  'BTC-USD',
    'ETH/USDT':  'ETH-USD',
    'SOL/USDT':  'SOL-USD',
    'BNB/USDT':  'BNB-USD',
    'DOGE/USDT': 'DOGE-USD',
    'AVAX/USDT': 'AVAX-USD',
}

# Forex — London+NY sessions (30x leverage)
# FIX: EUR/GBP REMOVED — daily range 0.2-0.3%, TP of 0.3% unreachable
FOREX_ASSETS = {
    'EURUSD=X': 'EUR/USD',
    'GBPUSD=X': 'GBP/USD',
    'USDJPY=X': 'USD/JPY',
    'AUDUSD=X': 'AUD/USD',
    'USDCAD=X': 'USD/CAD',
}

# Stocks — NY session only
STOCK_ASSETS = {
    'NVDA':  'Nvidia',
    'TSLA':  'Tesla',
    'AMD':   'AMD',
    'META':  'Meta',
    'AMZN':  'Amazon',
    'GOOGL': 'Google',
    'AAPL':  'Apple',
    'MSFT':  'Microsoft',
}

# ETFs
ETF_ASSETS = {
    'SPY': 'S&P 500 ETF',
    'QQQ': 'Nasdaq ETF',
    'GLD': 'Gold ETF',
    'SLV': 'Silver ETF',
}

# Commodities
COMMODITY_ASSETS = {
    'GC=F': 'GOLD',
    'SI=F': 'SILVER',
}

# ────────────────────────────────────────────────────────────
# SESSION HOURS (UTC)
# ────────────────────────────────────────────────────────────
LONDON_OPEN  = 8
LONDON_CLOSE = 17
NY_OPEN      = 14
NY_CLOSE     = 21

# ────────────────────────────────────────────────────────────
# TRAILING STOP
# ────────────────────────────────────────────────────────────
TRAILING_STOP_ENABLED = True
TRAILING_STOP_PCT     = 0.003

# ────────────────────────────────────────────────────────────
# API KEYS
# ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY      = os.getenv('ANTHROPIC_API_KEY', '')
ETORO_API_KEY          = os.getenv('ETORO_API_KEY', '')
CAPITAL_API_KEY        = os.getenv('CAPITAL_API_KEY', '')
CAPITAL_EMAIL          = os.getenv('CAPITAL_EMAIL', '')
CAPITAL_PASSWORD       = os.getenv('CAPITAL_PASSWORD', '')
BINANCE_API_KEY        = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY     = os.getenv('BINANCE_SECRET_KEY', '')
TELEGRAM_BOT_TOKEN     = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID       = os.getenv('TELEGRAM_CHAT_ID', '')
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
INSTAGRAM_ACCOUNT_ID   = os.getenv('INSTAGRAM_ACCOUNT_ID', '')
YOUTUBE_REFRESH_TOKEN  = os.getenv('YOUTUBE_REFRESH_TOKEN', '')
YOUTUBE_CLIENT_ID      = os.getenv('YOUTUBE_CLIENT_ID', '')
YOUTUBE_CLIENT_SECRET  = os.getenv('YOUTUBE_CLIENT_SECRET', '')
TIKTOK_ACCESS_TOKEN    = os.getenv('TIKTOK_ACCESS_TOKEN', '')
CLOUDINARY_URL         = os.getenv('CLOUDINARY_URL', '')

# ────────────────────────────────────────────────────────────
# SCHEDULER
# ────────────────────────────────────────────────────────────
SCAN_INTERVAL_MINUTES = int(os.getenv('SCAN_INTERVAL_MINUTES', '15'))
DAILY_POST_HOUR       = int(os.getenv('DAILY_POST_HOUR', '20'))

# ────────────────────────────────────────────────────────────
# PATHS + BRANDING
# ────────────────────────────────────────────────────────────
DATA_FILE       = 'data/trades.json'
EQUITY_FILE     = 'data/equity.json'
SLIDES_DIR      = 'outputs/slides'
VIDEOS_DIR      = 'outputs/videos'
CHANNEL_NAME    = os.getenv('CHANNEL_NAME',   '£500 Trading Challenge')
CHANNEL_HANDLE  = os.getenv('CHANNEL_HANDLE', '@TradingFromZero')
CURRENCY_SYMBOL = '£'
