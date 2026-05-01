"""
asset_config.py v4 - Comprehensive Rewrite
-------------------------------------------
Per-asset trade settings (TP, SL, leverage, max_hours).

Fixes from v3:
  - Added SILVER entry (was missing - silver signals fell through to DEFAULT)
  - Replaced corrupted UTF-8 emojis with simple ASCII-safe placeholders
  - Aligned all keys to what market_scanner passes:
      crypto -> 'BTC/USDT' style
      forex  -> 'EUR/USD' style
      stocks -> 'NVDA' style
      ETFs   -> 'SPY' style
      commodity -> 'GOLD' / 'SILVER' style
"""

ASSET_SETTINGS = {

    # -- FOREX (30x leverage, primary income source) --------------------------
    # 1H timeframe; tighter SL because forex moves slowly without leverage
    'EUR/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Euro/Dollar',     'emoji': 'EUR', 'priority': 1},
    'GBP/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Pound/Dollar',    'emoji': 'GBP', 'priority': 1},
    'USD/JPY':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Dollar/Yen',      'emoji': 'JPY', 'priority': 1},
    'AUD/USD':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Aussie/Dollar',   'emoji': 'AUD', 'priority': 2},
    'USD/CAD':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Dollar/CAD',      'emoji': 'CAD', 'priority': 2},

    # -- CRYPTO (2x leverage; SLs widened in v3 fix) --------------------------
    'BTC/USDT':  {'tp': 0.030, 'sl': 0.020, 'max_hours': 12, 'leverage': 2,
                  'label': 'Bitcoin',         'emoji': 'BTC', 'priority': 1},
    'ETH/USDT':  {'tp': 0.035, 'sl': 0.022, 'max_hours': 12, 'leverage': 2,
                  'label': 'Ethereum',        'emoji': 'ETH', 'priority': 1},
    'SOL/USDT':  {'tp': 0.045, 'sl': 0.025, 'max_hours': 10, 'leverage': 2,
                  'label': 'Solana',          'emoji': 'SOL', 'priority': 1},
    'BNB/USDT':  {'tp': 0.030, 'sl': 0.020, 'max_hours': 12, 'leverage': 2,
                  'label': 'BNB',             'emoji': 'BNB', 'priority': 2},
    'DOGE/USDT': {'tp': 0.060, 'sl': 0.030, 'max_hours': 8,  'leverage': 2,
                  'label': 'Dogecoin',        'emoji': 'DOGE','priority': 2},
    'AVAX/USDT': {'tp': 0.050, 'sl': 0.028, 'max_hours': 10, 'leverage': 2,
                  'label': 'Avalanche',       'emoji': 'AVAX','priority': 2},

    # -- STOCKS (5x leverage) -------------------------------------------------
    'NVDA':      {'tp': 0.030, 'sl': 0.010, 'max_hours': 7,  'leverage': 5,
                  'label': 'Nvidia',          'emoji': 'NVDA','priority': 1},
    'TSLA':      {'tp': 0.035, 'sl': 0.012, 'max_hours': 7,  'leverage': 5,
                  'label': 'Tesla',           'emoji': 'TSLA','priority': 1},
    'AMD':       {'tp': 0.030, 'sl': 0.010, 'max_hours': 7,  'leverage': 5,
                  'label': 'AMD',             'emoji': 'AMD', 'priority': 1},
    'META':      {'tp': 0.025, 'sl': 0.008, 'max_hours': 7,  'leverage': 5,
                  'label': 'Meta',            'emoji': 'META','priority': 2},
    'AMZN':      {'tp': 0.025, 'sl': 0.008, 'max_hours': 7,  'leverage': 5,
                  'label': 'Amazon',          'emoji': 'AMZN','priority': 2},
    'GOOGL':     {'tp': 0.020, 'sl': 0.007, 'max_hours': 7,  'leverage': 5,
                  'label': 'Google',          'emoji': 'GOOG','priority': 2},
    'AAPL':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Apple',           'emoji': 'AAPL','priority': 3},
    'MSFT':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Microsoft',       'emoji': 'MSFT','priority': 3},

    # -- COMMODITIES (20x leverage) ------------------------------------------
    'GOLD':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 16, 'leverage': 20,
                  'label': 'Gold',            'emoji': 'GOLD','priority': 2},
    # FIX: SILVER added - was missing in v3, silver signals fell through to DEFAULT
    'SILVER':    {'tp': 0.020, 'sl': 0.007, 'max_hours': 16, 'leverage': 20,
                  'label': 'Silver',          'emoji': 'SILV','priority': 3},

    # -- ETFs (5x leverage) ---------------------------------------------------
    'SPY':       {'tp': 0.010, 'sl': 0.004, 'max_hours': 7,  'leverage': 5,
                  'label': 'S&P 500 ETF',     'emoji': 'SPY', 'priority': 3},
    'QQQ':       {'tp': 0.012, 'sl': 0.004, 'max_hours': 7,  'leverage': 5,
                  'label': 'Nasdaq ETF',      'emoji': 'QQQ', 'priority': 3},
    'GLD':       {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Gold ETF',        'emoji': 'GLD', 'priority': 3},
    'SLV':       {'tp': 0.020, 'sl': 0.007, 'max_hours': 7,  'leverage': 5,
                  'label': 'Silver ETF',      'emoji': 'SLV', 'priority': 3},
}

DEFAULT = {'tp': 0.020, 'sl': 0.008, 'max_hours': 12,
           'leverage': 2, 'label': 'Asset', 'emoji': '?', 'priority': 3}


def get(asset):
    return ASSET_SETTINGS.get(asset, DEFAULT)

def get_tp(asset):        return get(asset)['tp']
def get_sl(asset):        return get(asset)['sl']
def get_max_hours(asset): return get(asset)['max_hours']
def get_leverage(asset):  return get(asset)['leverage']
def get_label(asset):     return get(asset)['label']
def get_emoji(asset):     return get(asset)['emoji']
def get_priority(asset):  return get(asset).get('priority', 3)


def expected_profit(asset, capital=100):
    s = get(asset)
    return round(capital * s['tp'] * s['leverage'], 2)


def max_loss(asset, capital=100):
    s = get(asset)
    return round(capital * s['sl'] * s['leverage'], 2)
