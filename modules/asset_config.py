"""
asset_config.py
---------------
Per-asset profit targets, stop losses and max hold times.
Based on real average daily price movements for each asset class.

Goal: Every trade resolves within 24 hours with realistic targets.
"""

# ─────────────────────────────────────────────────────────────────────────────
# PER-ASSET SETTINGS
# Format: 'ASSET': (take_profit_pct, stop_loss_pct, max_hours, leverage)
# ─────────────────────────────────────────────────────────────────────────────

ASSET_SETTINGS = {

    # ── HIGH VOLATILITY CRYPTO (moves 3-8% daily) ─────────────────────────────
    'BTC/USDT':  {'tp': 0.030, 'sl': 0.010, 'max_hours': 12, 'leverage': 2,
                  'label': 'Bitcoin',     'emoji': '₿'},
    'ETH/USDT':  {'tp': 0.035, 'sl': 0.012, 'max_hours': 12, 'leverage': 2,
                  'label': 'Ethereum',    'emoji': 'Ξ'},
    'SOL/USDT':  {'tp': 0.040, 'sl': 0.013, 'max_hours': 10, 'leverage': 2,
                  'label': 'Solana',      'emoji': '◎'},
    'BNB/USDT':  {'tp': 0.030, 'sl': 0.010, 'max_hours': 12, 'leverage': 2,
                  'label': 'BNB',         'emoji': '🟡'},

    # ── HIGH VOLATILITY STOCKS (moves 2-5% daily) ─────────────────────────────
    'NVDA':      {'tp': 0.025, 'sl': 0.008, 'max_hours': 8,  'leverage': 5,
                  'label': 'Nvidia',      'emoji': '🟢'},
    'TSLA':      {'tp': 0.030, 'sl': 0.010, 'max_hours': 8,  'leverage': 5,
                  'label': 'Tesla',       'emoji': '⚡'},
    'AMD':       {'tp': 0.025, 'sl': 0.008, 'max_hours': 8,  'leverage': 5,
                  'label': 'AMD',         'emoji': '🔴'},
    'META':      {'tp': 0.020, 'sl': 0.007, 'max_hours': 8,  'leverage': 5,
                  'label': 'Meta',        'emoji': '🔵'},

    # ── MEDIUM VOLATILITY STOCKS (moves 1-3% daily) ───────────────────────────
    'AAPL':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 8,  'leverage': 5,
                  'label': 'Apple',       'emoji': '🍎'},
    'AMZN':      {'tp': 0.020, 'sl': 0.007, 'max_hours': 8,  'leverage': 5,
                  'label': 'Amazon',      'emoji': '📦'},
    'MSFT':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 8,  'leverage': 5,
                  'label': 'Microsoft',   'emoji': '🪟'},
    'GOOGL':     {'tp': 0.020, 'sl': 0.007, 'max_hours': 8,  'leverage': 5,
                  'label': 'Google',      'emoji': '🔍'},

    # ── COMMODITIES (moves 1-2% daily) ────────────────────────────────────────
    'GOLD':      {'tp': 0.015, 'sl': 0.005, 'max_hours': 16, 'leverage': 20,
                  'label': 'Gold',        'emoji': '🥇'},

    # ── ETFs (moves 0.5-1.5% daily) ───────────────────────────────────────────
    'SPY':       {'tp': 0.010, 'sl': 0.004, 'max_hours': 8,  'leverage': 5,
                  'label': 'S&P 500 ETF', 'emoji': '📊'},
    'QQQ':       {'tp': 0.012, 'sl': 0.004, 'max_hours': 8,  'leverage': 5,
                  'label': 'Nasdaq ETF',  'emoji': '💻'},
    'GLD':       {'tp': 0.015, 'sl': 0.005, 'max_hours': 8,  'leverage': 5,
                  'label': 'Gold ETF',    'emoji': '🥇'},
    'SLV':       {'tp': 0.020, 'sl': 0.007, 'max_hours': 8,  'leverage': 5,
                  'label': 'Silver ETF',  'emoji': '🥈'},

    # ── FOREX (moves 0.3-0.8% daily — use leverage to amplify) ───────────────
    # With 30x leverage: 0.5% move = 15% return on margin
    'EUR/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 12, 'leverage': 30,
                  'label': 'EUR/USD',     'emoji': '💶'},
    'GBP/USD':   {'tp': 0.005, 'sl': 0.002, 'max_hours': 12, 'leverage': 30,
                  'label': 'GBP/USD',     'emoji': '💷'},
    'USD/JPY':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 12, 'leverage': 30,
                  'label': 'USD/JPY',     'emoji': '💴'},
    'AUD/USD':   {'tp': 0.004, 'sl': 0.002, 'max_hours': 12, 'leverage': 30,
                  'label': 'AUD/USD',     'emoji': '🦘'},
}

# Default fallback if asset not in map
DEFAULT_SETTINGS = {
    'tp': 0.020, 'sl': 0.007, 'max_hours': 24,
    'leverage': 2, 'label': 'Unknown', 'emoji': '📈'
}


def get(asset: str) -> dict:
    """Returns settings for an asset. Falls back to defaults."""
    return ASSET_SETTINGS.get(asset, DEFAULT_SETTINGS)


def get_tp(asset: str) -> float:
    return get(asset)['tp']


def get_sl(asset: str) -> float:
    return get(asset)['sl']


def get_max_hours(asset: str) -> int:
    return get(asset)['max_hours']


def get_leverage(asset: str) -> int:
    return get(asset)['leverage']


def get_label(asset: str) -> str:
    return get(asset)['label']


def get_emoji(asset: str) -> str:
    return get(asset)['emoji']


def expected_profit_gbp(asset: str, capital: float) -> float:
    """Calculate expected profit in GBP for a winning trade."""
    s = get(asset)
    return round(capital * s['tp'] * s['leverage'], 2)


def max_loss_gbp(asset: str, capital: float) -> float:
    """Calculate max loss in GBP for a losing trade."""
    s = get(asset)
    return round(capital * s['sl'] * s['leverage'], 2)


def summary_table(capital: float = 100) -> str:
    """Returns a readable summary of all asset targets."""
    lines = [
        "Asset          | TP    | SL    | Leverage | Win£   | Loss£  | Max hrs",
        "---------------|-------|-------|----------|--------|--------|--------",
    ]
    for asset, s in ASSET_SETTINGS.items():
        win  = round(capital * s['tp'] * s['leverage'], 2)
        loss = round(capital * s['sl'] * s['leverage'], 2)
        lines.append(
            f"{asset:<14} | {s['tp']*100:.1f}%  | {s['sl']*100:.2f}% "
            f"| {s['leverage']:>6}x   | £{win:<5} | £{loss:<5} | {s['max_hours']}h"
        )
    return '\n'.join(lines)
