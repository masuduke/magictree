"""
asset_config.py v6 - Option C: NVDA + AAPL + TSLA + GLD only
--------------------------------------------------------------
Per-asset trade settings. After honest backtesting on 19 assets x 7 strategies
across 15min and 4h timeframes, ONLY these 4 assets showed robust edge across
multiple strategies and BOTH timeframes:
  - NVDA: 3 strategies positive on both timeframes
  - TSLA: BBSqueeze positive on both
  - AAPL: Breakout positive on both
  - GLD:  BBSqueeze positive on both

All other 15 assets either showed no edge or only on one timeframe (= noise).

Calibration:
  - TP 3.0%, SL 1.5% (2:1 R:R) - sized for 4h bars (bigger ranges than 15min)
  - 5x leverage (matches Capital.com retail tier for stocks/ETF)
  - max_hours=64 (16 bars x 4h = up to 3 days hold)
"""

# Per-asset settings (keys must match what market_scanner passes)
ASSET_SETTINGS = {
    'NVDA': {'tp': 0.030, 'sl': 0.015, 'max_hours': 64, 'leverage': 5,
             'label': 'NVIDIA', 'emoji': 'NVD', 'priority': 1},
    'AAPL': {'tp': 0.030, 'sl': 0.015, 'max_hours': 64, 'leverage': 5,
             'label': 'Apple',  'emoji': 'AAP', 'priority': 1},
    'TSLA': {'tp': 0.030, 'sl': 0.015, 'max_hours': 64, 'leverage': 5,
             'label': 'Tesla',  'emoji': 'TSL', 'priority': 1},
    'GLD':  {'tp': 0.030, 'sl': 0.015, 'max_hours': 64, 'leverage': 5,
             'label': 'Gold ETF','emoji': 'GLD', 'priority': 1},
}

# Used as fallback - should never actually fire since we control the universe
DEFAULT = {'tp': 0.020, 'sl': 0.010, 'max_hours': 32, 'leverage': 2,
           'label': 'Unknown', 'emoji': 'UNK', 'priority': 5}


def get(asset):
    """Get settings for an asset. Returns DEFAULT if unknown."""
    return ASSET_SETTINGS.get(asset, DEFAULT)


def expected_profit(asset, capital):
    """Expected GBP profit if TP hits."""
    s = get(asset)
    return capital * s['tp'] * s['leverage']


def max_loss(asset, capital):
    """Expected GBP loss if SL hits (positive number)."""
    s = get(asset)
    return capital * s['sl'] * s['leverage']


def all_assets():
    """List of asset keys in priority order."""
    return sorted(ASSET_SETTINGS.keys(),
                  key=lambda k: ASSET_SETTINGS[k]['priority'])


if __name__ == '__main__':
    # Sanity check
    for asset in ['NVDA', 'AAPL', 'TSLA', 'GLD']:
        s = get(asset)
        print(f"{asset}: tp={s['tp']*100}%, sl={s['sl']*100}%, lev={s['leverage']}x, "
              f"on £5000: win=£{expected_profit(asset,5000):.0f}, loss=£{max_loss(asset,5000):.0f}")
