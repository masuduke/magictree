"""
asset_config.py v2 — Optimised For £25/day From £100
------------------------------------------------------
Research-based profit targets matching real daily price movements.
Key insight: FOREX with 30x leverage is the most reliable path to £25/day.

Daily price movements (research-based):
- FOREX:      0.3-0.8% (with 30x = 9-24% on margin)
- CRYPTO:     2.8-10%  (with 2x = 5.6-20% on margin)
- STOCKS:     1-5%     (with 5x = 5-25% on margin)
- COMMODITIES:0.5-2%   (with 20x = 10-40% on margin)
"""
import os

# ─────────────────────────────────────────────────────────────────────────────
# Per-asset settings: (take_profit, stop_loss, max_hours, leverage)
# ─────────────────────────────────────────────────────────────────────────────
ASSET_SETTINGS = {

    # ── FOREX — Primary income source (30x leverage, small moves, 24/5) ───────
    # With 30x: 0.5% move on £100 = £15 profit. 2 wins/day = £30 target
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
    'EUR/GBP':   {'tp': 0.003, 'sl': 0.0015,'max_hours': 8,  'leverage': 30,
                  'label': 'Euro/Pound',       'emoji': '🇪🇺', 'priority': 2},

    # ── HIGH VOLATILITY CRYPTO — 24/7 trading, 5-15% daily moves ─────────────
    'BTC/USDT':  {'tp': 0.030, 'sl': 0.010, 'max_hours': 12, 'leverage': 2,
                  'label': 'Bitcoin',          'emoji': '₿',  'priority': 1},
    'ETH/USDT':  {'tp': 0.035, 'sl': 0.012, 'max_hours': 12, 'leverage': 2,
                  'label': 'Ethereum',         'emoji': 'Ξ',  'priority': 1},
    'SOL/USDT':  {'tp': 0.045, 'sl': 0.015, 'max_hours': 10, 'leverage': 2,
                  'label': 'Solana',           'emoji': '◎',  'priority': 1},
    'BNB/USDT':  {'tp': 0.030, 'sl': 0.010, 'max_hours': 12, 'leverage': 2,
                  'label': 'BNB',              'emoji': '🟡', 'priority': 2},
    'DOGE/USDT': {'tp': 0.060, 'sl': 0.020, 'max_hours': 8,  'leverage': 2,
                  'label': 'Dogecoin',         'emoji': '🐕', 'priority': 2},
    'AVAX/USDT': {'tp': 0.050, 'sl': 0.017, 'max_hours': 10, 'leverage': 2,
                  'label': 'Avalanche',        'emoji': '🔺', 'priority': 2},

    # ── HIGH VOLATILITY STOCKS — 2-8% daily, best during NY session ──────────
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

    # ── MEDIUM VOLATILITY STOCKS ──────────────────────────────────────────────
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

DEFAULT = {'tp': 0.020, 'sl': 0.007, 'max_hours': 12,
           'leverage': 2, 'label': 'Asset', 'emoji': '📈', 'priority': 3}


def get(asset):
    return ASSET_SETTINGS.get(asset, DEFAULT)

def get_tp(asset):       return get(asset)['tp']
def get_sl(asset):       return get(asset)['sl']
def get_max_hours(asset):return get(asset)['max_hours']
def get_leverage(asset): return get(asset)['leverage']
def get_label(asset):    return get(asset)['label']
def get_emoji(asset):    return get(asset)['emoji']
def get_priority(asset): return get(asset).get('priority', 3)


def expected_profit(asset, capital=100):
    """£ profit on a winning trade."""
    s = get(asset)
    return round(capital * s['tp'] * s['leverage'], 2)


def max_loss(asset, capital=100):
    """£ loss on a losing trade."""
    s = get(asset)
    return round(capital * s['sl'] * s['leverage'], 2)


def daily_target_analysis(capital=100):
    """Shows what it takes to hit £25/day."""
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
