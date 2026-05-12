"""
config.py v7 - Option C: 4 stocks/ETF, 4h timeframe, £5000 capital
------------------------------------------------------------------
Changes from v6.1:
  - INITIAL_CAPITAL: 500 -> 5000 (paper trade at scale)
  - SCAN_INTERVAL_MINUTES: 15 -> 240 (4h cadence)
  - MAX_DAILY_LOSS: 50 -> 200 (4% of £5000, scaled proportionally)
  - Asset universe: 27 -> 4 (NVDA, AAPL, TSLA, GLD only)
  - Removed CRYPTO_ASSETS, FOREX_ASSETS, COMMODITY_ASSETS (all dropped)
  - Removed RSI_LOWER_BAND, RSI_UPPER_BAND (not used by new strategies)
  - Removed MIN_CONFIDENCE (no AI gate - strategies are pre-validated)

Inherited from v6:
  - DATA_DIR + persistent disk (so paper balance survives redeploys)
  - GBP currency
  - Telegram bot integration
"""
import os

# ============================================================
# CORE TRADING CONFIG
# ============================================================
PAPER_TRADE        = os.getenv('PAPER_TRADE', 'true').lower() == 'true'
INITIAL_CAPITAL    = float(os.getenv('INITIAL_CAPITAL', '5000'))
CURRENCY_SYMBOL    = 'GBP'
CHANNEL_NAME       = os.getenv('CHANNEL_NAME', 'GBP5000 NVDA Bot')

# Risk management
MAX_OPEN_TRADES    = int(os.getenv('MAX_OPEN_TRADES', '3'))
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY', '10'))
MAX_DAILY_LOSS     = float(os.getenv('MAX_DAILY_LOSS', '200'))  # 4% of £5000

# Position sizing - used by etoro_executor.py for record-keeping (pos_sz field).
# Note: actual PnL uses capital * leverage formula, not this risk%. Kept for
# trade-log completeness (matches what a Capital.com order would record).
RISK_PER_TRADE_PCT = float(os.getenv('RISK_PER_TRADE_PCT', '0.02'))  # 2% per trade

# Daily content posting time (UTC hour)
DAILY_POST_HOUR    = int(os.getenv('DAILY_POST_HOUR', '20'))

# Scan timing - 4h cadence for 4h strategies
SCAN_INTERVAL_MINUTES = int(os.getenv('SCAN_INTERVAL_MINUTES', '240'))

# Trailing stop (kept from v6 - works well)
TRAILING_STOP_ENABLED       = True
TRAILING_STOP_ACTIVATION_PCT = 0.50  # Activate trail after 50% of TP reached

# ============================================================
# ASSET UNIVERSE - just 4 backtest-validated assets
# ============================================================
# Stocks (5x leverage, NYSE hours)
STOCK_ASSETS = {
    'NVDA':  'NVIDIA',
    'AAPL':  'Apple',
    'TSLA':  'Tesla',
}

# ETFs (5x leverage, NYSE hours)
ETF_ASSETS = {
    'GLD':   'Gold ETF',
}

# Empty dicts for compatibility with existing code that imports these
CRYPTO_ASSETS    = {}
FOREX_ASSETS     = {}
COMMODITY_ASSETS = {}

# ============================================================
# PERSISTENT DISK PATHS
# ============================================================
DATA_DIR = os.getenv('DATA_DIR', '/data')
DATA_FILE   = os.path.join(DATA_DIR, 'trades.json')
EQUITY_FILE = os.path.join(DATA_DIR, 'equity.json')

# Slide / generated content output dir (used by slide_creator for daily slides)
SLIDES_DIR = os.getenv('SLIDES_DIR', os.path.join(DATA_DIR, 'slides'))

# ============================================================
# TELEGRAM
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID', '')

# ============================================================
# ANTHROPIC API (kept for any AI-assisted features, currently unused)
# ============================================================
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ============================================================
# STRATEGY CONFIG (for visibility/debugging only)
# ============================================================
STRATEGY_NAMES = ['BBSqueeze_20', 'MTF_Momentum_daily', 'Breakout_20bar']
TIMEFRAME      = '4h'
