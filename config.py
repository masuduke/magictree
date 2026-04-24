"""
config.py  v3 — Expanded Assets + Consistent Profit Settings
"""
import os

# ─────────────────────────────────────────
# TRADING SETTINGS
# ─────────────────────────────────────────
PAPER_TRADE        = os.getenv('PAPER_TRADE', 'true').lower() == 'true'
INITIAL_CAPITAL    = float(os.getenv('INITIAL_CAPITAL', '500'))
RISK_PER_TRADE_PCT = float(os.getenv('RISK_PER_TRADE_PCT', '0.01'))   # 1% risk = £5 max loss
TAKE_PROFIT_PCT    = float(os.getenv('TAKE_PROFIT_PCT',   '0.03'))   # 3% target = £15 profit
STOP_LOSS_PCT      = float(os.getenv('STOP_LOSS_PCT',     '0.01'))   # 1% stop  = £5 max loss
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY',   '3'))
MAX_DAILY_LOSS     = float(os.getenv('MAX_DAILY_LOSS',    '25'))     # Stop trading if down £25

# ─────────────────────────────────────────
# EXPANDED ASSET UNIVERSE
# ─────────────────────────────────────────

# ── Crypto (24/7 via Binance) ──────────────────────────────────────────────────
CRYPTO_ASSETS = [
    'BTC/USDT',   # Bitcoin       — most liquid crypto
    'ETH/USDT',   # Ethereum      — strong technicals
    'SOL/USDT',   # Solana        — high momentum 2026
    'BNB/USDT',   # Binance Coin  — stable, good volume
]

# ── Forex (24/5 via yfinance) ─────────────────────────────────────────────────
# Most liquid market in the world — tight spreads, predictable patterns
FOREX_ASSETS = {
    'EURUSD=X':  'EUR/USD',   # Most traded pair
    'GBPUSD=X':  'GBP/USD',   # Good for UK-based content
    'USDJPY=X':  'USD/JPY',   # Very liquid
    'AUDUSD=X':  'AUD/USD',   # Commodity-linked
}

# ── Stocks — AI & Tech focused (market hours only) ────────────────────────────
STOCK_ASSETS = {
    'AAPL':  'Apple',
    'NVDA':  'Nvidia',       # AI leader — most volatile/profitable
    'MSFT':  'Microsoft',
    'AMZN':  'Amazon',
    'META':  'Meta',
    'TSLA':  'Tesla',
    'GOOGL': 'Google',
    'AMD':   'AMD',          # AI chips
}

# ── ETFs (market hours only) ──────────────────────────────────────────────────
# More stable than individual stocks — good for consistent signals
ETF_ASSETS = {
    'SPY':   'S&P 500 ETF',      # Most liquid ETF
    'QQQ':   'Nasdaq ETF',       # Tech-heavy
    'GLD':   'Gold ETF',         # Gold exposure via stock market
    'SLV':   'Silver ETF',       # Silver without futures risk
}

# ── Commodities (via yfinance futures) ────────────────────────────────────────
COMMODITY_ASSETS = {
    'GC=F':  'GOLD',             # Most reliable commodity signal
    # OIL and SILVER removed — too volatile in current geopolitical climate
}

# ── Session hours (UTC) ───────────────────────────────────────────────────────
LONDON_OPEN   = 8    # Best for Forex
LONDON_CLOSE  = 17
NY_OPEN       = 14   # Best for Stocks + Forex overlap
NY_CLOSE      = 21

# ─────────────────────────────────────────
# TECHNICAL INDICATOR SETTINGS
# ─────────────────────────────────────────
EMA_FAST        = 9
EMA_SLOW        = 21
EMA_TREND       = 50    # Trend filter
RSI_PERIOD      = 14
RSI_LOWER_BAND  = int(os.getenv('RSI_LOWER_BAND', '45'))
RSI_UPPER_BAND  = int(os.getenv('RSI_UPPER_BAND', '55'))
MIN_CONFIDENCE  = int(os.getenv('MIN_CONFIDENCE', '80'))

# ─────────────────────────────────────────
# MULTI-TIMEFRAME SETTINGS
# ─────────────────────────────────────────
# Bot checks 1hr chart to confirm 15min signal direction
CONFIRM_HIGHER_TIMEFRAME = True

# ─────────────────────────────────────────
# RISK MANAGEMENT RULES
# ─────────────────────────────────────────
MAX_OPEN_TRADES        = 2      # Never have more than 2 open at once
MAX_SAME_DIRECTION     = 1      # Max 1 BUY and 1 SELL open at same time
TRAILING_STOP_ENABLED  = True   # Lock in profits as price moves
TRAILING_STOP_PCT      = 0.005  # Trail by 0.5%
CORRELATION_CHECK      = True   # Don't trade correlated assets together
NEWS_BLACKOUT_MINS     = 30     # Skip trading 30 mins around major news

# ─────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────
ANTHROPIC_API_KEY      = os.getenv('ANTHROPIC_API_KEY', '')
ETORO_API_KEY          = os.getenv('ETORO_API_KEY', '')
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
CHANNEL_NAME    = os.getenv('CHANNEL_NAME',   '£500 Trading Challenge')
CHANNEL_HANDLE  = os.getenv('CHANNEL_HANDLE', '@TradingFromZero')
CURRENCY_SYMBOL = '£'
