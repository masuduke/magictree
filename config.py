"""
config.py v6.1 - Added EUR/JPY and USO oil ETF
-----------------------------------------------
Fixes from v6:
  - FIX 20: Added EUR/JPY (forex cross pair, 30x leverage)
  - FIX 20: Added USO oil ETF (5x leverage, US session only)
    Total assets now 27: 6 crypto, 6 forex, 8 stocks, 5 ETFs, 2 commodities

Inherited from v6:
  - DATA_DIR + persistent disk paths
  - CURRENCY_SYMBOL = 'GBP' (was corrupted)
"""
import os

# -- TRADING SETTINGS --------------------------------------------------------
PAPER_TRADE        = os.getenv('PAPER_TRADE', 'true').lower() == 'true'
INITIAL_CAPITAL    = float(os.getenv('INITIAL_CAPITAL', '500'))
RISK_PER_TRADE_PCT = float(os.getenv('RISK_PER_TRADE_PCT', '0.01'))
TAKE_PROFIT_PCT    = float(os.getenv('TAKE_PROFIT_PCT',   '0.005'))
STOP_LOSS_PCT      = float(os.getenv('STOP_LOSS_PCT',     '0.002'))
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY',   '5'))
MAX_DAILY_LOSS     = float(os.getenv('MAX_DAILY_LOSS',    '25'))
MAX_OPEN_TRADES    = int(os.getenv('MAX_OPEN_TRADES',      '3'))

# -- SIGNAL QUALITY ----------------------------------------------------------
MIN_CONFIDENCE         = int(os.getenv('MIN_CONFIDENCE', '70'))
MIN_STRATEGY_SCORE     = int(os.getenv('MIN_STRATEGY_SCORE', '60'))
CONFIRM_HIGHER_TF      = os.getenv('CONFIRM_HIGHER_TF', 'true').lower() == 'true'
CORRELATION_CHECK      = True
MAX_SAME_DIRECTION     = 2

# -- TECHNICAL SETTINGS ------------------------------------------------------
EMA_FAST        = 9
EMA_SLOW        = 21
RSI_PERIOD      = 14
RSI_LOWER_BAND  = int(os.getenv('RSI_LOWER_BAND', '40'))
RSI_UPPER_BAND  = int(os.getenv('RSI_UPPER_BAND', '60'))

# -- ASSET UNIVERSE ----------------------------------------------------------

# Crypto - 24/7
CRYPTO_ASSETS = {
    'BTC/USDT':  'BTC-USD',
    'ETH/USDT':  'ETH-USD',
    'SOL/USDT':  'SOL-USD',
    'BNB/USDT':  'BNB-USD',
    'DOGE/USDT': 'DOGE-USD',
    'AVAX/USDT': 'AVAX-USD',
}

# Forex - London+NY sessions (30x leverage)
FOREX_ASSETS = {
    'EURUSD=X': 'EUR/USD',
    'GBPUSD=X': 'GBP/USD',
    'USDJPY=X': 'USD/JPY',
    'AUDUSD=X': 'AUD/USD',
    'USDCAD=X': 'USD/CAD',
    'EURJPY=X': 'EUR/JPY',  # FIX 20: JPY cross pair (often clearer trends)
}

# Stocks - NY session only
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
    'USO': 'Oil ETF',  # FIX 20: oil exposure via ETF (avoids =F futures issues)
}

# Commodities
COMMODITY_ASSETS = {
    'GC=F': 'GOLD',
    'SI=F': 'SILVER',
}

# -- SESSION HOURS (UTC) -----------------------------------------------------
LONDON_OPEN  = 8
LONDON_CLOSE = 17
NY_OPEN      = 14
NY_CLOSE     = 21

# -- TRAILING STOP -----------------------------------------------------------
TRAILING_STOP_ENABLED = True
TRAILING_STOP_PCT     = 0.003

# -- API KEYS ----------------------------------------------------------------
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

# -- SCHEDULER ---------------------------------------------------------------
SCAN_INTERVAL_MINUTES = int(os.getenv('SCAN_INTERVAL_MINUTES', '15'))
DAILY_POST_HOUR       = int(os.getenv('DAILY_POST_HOUR', '20'))

# -- PATHS + BRANDING --------------------------------------------------------
# FIX: trades and equity now live on persistent disk so they survive redeploys.
# DATA_DIR defaults to '/data' (the Render disk mount path). Override with env
# var DATA_DIR for local dev, e.g. set DATA_DIR=./data for laptop testing.
DATA_DIR        = os.getenv('DATA_DIR', '/data')
DATA_FILE       = os.path.join(DATA_DIR, 'trades.json')
EQUITY_FILE     = os.path.join(DATA_DIR, 'equity.json')

# Slides/videos can stay ephemeral - they're regenerated daily from trade data
SLIDES_DIR      = 'outputs/slides'
VIDEOS_DIR      = 'outputs/videos'

CHANNEL_NAME    = os.getenv('CHANNEL_NAME',   'GBP500 Trading Challenge')
CHANNEL_HANDLE  = os.getenv('CHANNEL_HANDLE', '@TradingFromZero')
CURRENCY_SYMBOL = 'GBP'
