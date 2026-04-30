"""
asset_config.py v3 — Fixed
---------------------------
Fixes applied:
1. Crypto stop losses DOUBLED — 1H candles need room to breathe
   BTC average 1H range = 0.8-1.5% — a 1% SL gets hit by noise alone
2. EUR/GBP REMOVED — 0.3% daily range, TP target unreachable
3. AVAX/DOGE SL widened — extreme volatility assets
"""
import os

ASSET_SETTINGS = {

    # ── FOREX — Primary income source (30x leverage) ──────────────────────────
    # FIX: EUR/GBP removed — 0.2-0.3% daily range, TP of 0.3% = needs full day
    'EUR/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Euro/Dollar',      'emoji': '💶', 'priority': 1},
    'GBP/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Pound/Dollar',     'emoji': '💷', 'priority': 1},
    'USD/JPY':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Dollar/Yen',       'emoji': '💴', 'priority': 1},
    'AUD/USD':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Aussie/Dollar',    'emoji': '🦘', 'priority': 2},
    'USD/CAD':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 8,  'leverage': 30,
                  'label': 'Dollar/CAD',       'emoji': '🍁', 'priority': 2},
    # EUR/GBP REMOVED — too low volatility (0.2% daily range)

    # ── CRYPTO — FIX: Stop losses doubled for 1H timeframe ───────────────────
    # BTC 1H average candle range = 0.8-1.5%
    # Old SL of 1.0% was getting hit by NORMAL NOISE before trade could work
    # ETH example: went UP but trade still lost — stop hit on wick
    'BTC/USDT':  {'tp': 0.030, 'sl': 0.020, 'max_hours': 12, 'leverage': 2,
                  'label': 'Bitcoin',          'emoji': '₿',  'priority': 1},
    'ETH/USDT':  {'tp': 0.035, 'sl': 0.022, 'max_hours': 12, 'leverage': 2,
                  'label': 'Ethereum',         'emoji': 'Ξ',  'priority': 1},
    'SOL/USDT':  {'tp': 0.045, 'sl': 0.025, 'max_hours': 10, 'leverage': 2,
                  'label': 'Solana',           'emoji': '◎',  'priority': 1},
    'BNB/USDT':  {'tp': 0.030, 'sl': 0.020, 'max_hours': 12, 'leverage': 2,
                  'label': 'BNB',              'emoji': '🟡', 'priority': 2},
    'DOGE/USDT': {'tp': 0.060, 'sl': 0.030, 'max_hours': 8,  'leverage': 2,
                  'label': 'Dogecoin',         'emoji': '🐕', 'priority': 2},
    'AVAX/USDT': {'tp': 0.050, 'sl': 0.028, 'max_hours': 10, 'leverage': 2,
                  'label': 'Avalanche',        'emoji': '🔺', 'priority': 2},

    # ── STOCKS ────────────────────────────────────────────────────────────────
    'NVDA':      {'tp': 0.030, 'sl': 0.010, 'max_hours': 7,  'leverage': 5,
                  'label': 'Nvidia',           'emoji': '🟢', 'priority': 1},
    'TSLA':      {'tp': 0.035, 'sl': 0.012, 'max_hours': 7,  'leverage': 5,
                  'label': 'Tesla',            'emoji': '⚡', 'priority': 1},
    'AMD':       {'tp': 0.030, 'sl': 0.010, 'max_hours': 7,  'leverage': 5,
                  'label': 'AMD',              'emoji': '🔴', 'priority': 1},
    'META':      {'tp': 0.025, 'sl': 0.008, 'max_hours': 7,  'leverage': 5,
                  'label': 'Meta',             'emoji': '🔵', 'priority': 2},
    'AMZN':      {'tp': 0.025, 'sl': 0.008, 'max_hours': 7,  'leverage': 5,
                  'label': 'Amazon',           'emoji': '📦', 'priority': 2},
    'GOOGL':     {'tp': 0.020, 'sl': 0.007, 'max_hours': 7,  'leverage': 5,
                  'label': 'Google',           'emoji': '🔍', 'priority': 2},
    'AAPL':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Apple',            'emoji': '🍎', 'priority': 3},
    'MSFT':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Microsoft',        'emoji': '🪟', 'priority': 3},

    # ── COMMODITIES ───────────────────────────────────────────────────────────
    'GOLD':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 16, 'leverage': 20,
                  'label': 'Gold',             'emoji': '🥇', 'priority': 2},

    # ── ETFs ──────────────────────────────────────────────────────────────────
    'SPY':       {'tp': 0.010, 'sl': 0.004, 'max_hours': 7,  'leverage': 5,
                  'label': 'S&P 500 ETF',      'emoji': '📊', 'priority': 3},
    'QQQ':       {'tp': 0.012, 'sl': 0.004, 'max_hours': 7,  'leverage': 5,
                  'label': 'Nasdaq ETF',       'emoji': '💻', 'priority': 3},
    'GLD':       {'tp': 0.015, 'sl': 0.005, 'max_hours': 7,  'leverage': 5,
                  'label': 'Gold ETF',         'emoji': '🥇', 'priority': 3},
    'SLV':       {'tp': 0.020, 'sl': 0.007, 'max_hours': 7,  'leverage': 5,
                  'label': 'Silver ETF',       'emoji': '🥈', 'priority': 3},
}

DEFAULT = {'tp': 0.020, 'sl': 0.008, 'max_hours': 12,
           'leverage': 2, 'label': 'Asset', 'emoji': '📈', 'priority': 3}


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


def daily_target_analysis(capital=100):
    print(f"\n{'='*65}")
    print(f"£25/DAY TARGET ANALYSIS — Capital: £{capital}")
    print(f"{'='*65}")
    print(f"{'Asset':<14} {'Win £':>6} {'Loss £':>7} {'Wins needed':>11}")
    print(f"{'-'*65}")
    for asset, s in ASSET_SETTINGS.items():
        win  = round(capital * s['tp'] * s['leverage'], 2)
        loss = round(capital * s['sl'] * s['leverage'], 2)
        if win > 0:
            wins_needed = max(1, round(25 / win, 1))
            print(f"{asset:<14} £{win:>5} £{loss:>6}  {wins_needed:>11}x wins/day")
    print(f"{'='*65}\n")
