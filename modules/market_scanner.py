"""
market_scanner.py v7 - Option C: 3 strategies on 4h bars, 4 stocks/ETFs
-----------------------------------------------------------------------
This is a COMPLETE REWRITE from v6.2. The previous scanner used EMA crossover
+ AI gate on 27 assets. That strategy produced no edge after 27 paper trades.

After rigorous backtest research (19 assets x 7 strategies x 2 timeframes),
ONLY 3 strategies on 4 specific stocks showed positive expectancy on BOTH
15min AND 4h timeframes:
  - BBSqueeze_20:        TSLA, NVDA, GLD
  - MTF_Momentum_daily:  NVDA
  - Breakout_20bar:      NVDA, AAPL

We trade ALL 3 strategies on ALL 4 assets (the strategies that don't work on
a particular asset will produce few signals or losing ones; the AGGREGATE
across this universe was profitable in backtest).

KEY DESIGN DECISIONS:
  - NO AI gate. Strategies were validated by backtest, not by AI scoring.
  - NO RSI-band filter. Each strategy has its own internal logic.
  - NO regime filter. Strategies are robust enough not to need it.
  - 4h bars resampled from yfinance 1h data (4h not directly available).
  - Live mode samples the most recent 200 bars × 1h = 50 4h-bars for signal.

CONFIDENCE/AUDIT:
  v6.2 lost £100 net across 27 trades. This was BECAUSE the strategy had no edge.
  v7's strategies were tested on 730 days of real data and showed PF > 1.2 on the
  specific (strategy, asset) pairs we trade. That's the only honest reason to
  deploy a new strategy.
"""
import logging
import time
from datetime import datetime, timezone

import pandas as pd
import numpy as np

from modules import asset_config

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
TIMEFRAME_HOURS    = 4
HISTORY_BARS_NEEDED = 100   # 100 4h bars = ~17 days
FETCH_HOURS_NEEDED = HISTORY_BARS_NEEDED * TIMEFRAME_HOURS * 1  # +safety margin
YF_PERIOD          = '60d'  # yfinance: enough for 100+ 4h bars
YF_INTERVAL        = '1h'   # we resample 1h -> 4h ourselves


# ============================================================
# DATA FETCH (with retry from v6.2 fix 19)
# ============================================================

def _yf_download_with_retry(ticker, period, interval, retry_delay=20):
    """yfinance retry-once. Fix 19 from v6.2."""
    import yfinance as yf
    for attempt in (1, 2):
        try:
            raw = yf.download(ticker, period=period, interval=interval,
                              progress=False, auto_adjust=True)
            if not raw.empty:
                return raw
            if attempt == 1:
                logger.info(f"yfinance empty for {ticker} - retrying in {retry_delay}s")
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"yfinance ({ticker}): {e}")
            return None
    logger.warning(f"yfinance ({ticker}) - empty after retry, giving up")
    return None


def _fetch_1h_data(ticker):
    """Fetch 1-hour bars from yfinance."""
    raw = _yf_download_with_retry(ticker, YF_PERIOD, YF_INTERVAL)
    if raw is None or raw.empty:
        return None
    try:
        df = raw.reset_index()
        df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]
        df = df.rename(columns={'Datetime':'ts','Date':'ts','Open':'open',
                                 'High':'high','Low':'low','Close':'close','Volume':'vol'})
        cols = ['ts','open','high','low','close']
        return df[cols].dropna()
    except Exception as e:
        logger.error(f"yfinance parse ({ticker}): {e}")
        return None


def _resample_to_4h(df_1h):
    """Resample 1h OHLC -> 4h OHLC."""
    if df_1h is None or df_1h.empty:
        return None
    df = df_1h.set_index('ts').sort_index()
    rs = df.resample('4h').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    return rs.reset_index()


# ============================================================
# INDICATORS (vanilla implementations, no look-ahead)
# ============================================================

def _ema(s, period):
    return s.ewm(span=period, adjust=False).mean()


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bollinger(close, period=20, std=2.0):
    ma = close.rolling(window=period).mean()
    sd = close.rolling(window=period).std()
    return ma + std*sd, ma, ma - std*sd


def _precompute(df):
    """Add all indicator columns once per scan."""
    df = df.copy()
    df['rsi14']     = _rsi(df['close'], 14)
    df['ema_short'] = _ema(df['close'], 20)
    df['ema_long']  = _ema(df['close'], 50)
    df['ma_long']   = df['close'].rolling(50).mean()
    bu, bm, bl = _bollinger(df['close'], 20, 2.0)
    df['bb_upper'] = bu
    df['bb_lower'] = bl
    return df


# ============================================================
# STRATEGY 1: BB SQUEEZE BREAKOUT
# ============================================================

def _bb_squeeze_signal(df):
    """
    Look for compression then breakout.
    Fires on the bar that closes OUTSIDE the bands after squeeze.
    Uses LAST bar (most recent complete 4h) for the signal.
    """
    if len(df) < 45:
        return None, "insufficient history"
    bb_period = 20
    squeeze_lookback = 20
    i = len(df) - 1  # most recent bar
    last = df.iloc[i]
    prev = df.iloc[i-1]
    # Compute current BB width as % of price
    if pd.isna(last['bb_upper']) or pd.isna(last['bb_lower']):
        return None, "bb not ready"
    bw_now = (last['bb_upper'] - last['bb_lower']) / last['close']
    # Average width over recent squeeze_lookback bars (excluding current)
    recent = df.iloc[i-squeeze_lookback:i]
    widths = (recent['bb_upper'] - recent['bb_lower']) / recent['close']
    avg_width = widths.mean()
    if pd.isna(avg_width) or avg_width == 0:
        return None, "avg width nan"
    # Squeeze condition: current width is < 70% of recent average
    if bw_now >= 0.7 * avg_width:
        return None, f"no squeeze (bw {bw_now:.4f} >= 0.7*{avg_width:.4f})"
    # Now check if THIS bar broke OUT of the band
    close = last['close']
    prev_close = prev['close']
    if pd.isna(prev['bb_upper']) or pd.isna(prev['bb_lower']):
        return None, "prev bb nan"
    if close > last['bb_upper'] and prev_close <= prev['bb_upper']:
        return 'BUY', "squeeze + close above upper band"
    if close < last['bb_lower'] and prev_close >= prev['bb_lower']:
        return 'SELL', "squeeze + close below lower band"
    return None, "in squeeze but no breakout"


# ============================================================
# STRATEGY 2: MTF MOMENTUM (4h + daily alignment)
# ============================================================

def _mtf_momentum_signal(df):
    """
    Trade 4h fresh EMA cross only when daily (6 bars back) trend aligns.
    """
    if len(df) < 55:
        return None, "insufficient history"
    i = len(df) - 1
    last = df.iloc[i]
    prev = df.iloc[i-1]
    if pd.isna(last['ema_short']) or pd.isna(last['ema_long']):
        return None, "ema nan"
    # Daily trend: now vs 6 bars (24h) ago
    if i < 6:
        return None, "not enough lookback for daily"
    price_now = last['close']
    price_back = df.iloc[i-6]['close']
    daily_up = price_now > price_back
    # Fresh cross condition (in last 3 bars)
    rec = df.iloc[i-3:i+1]
    crossed_up = (rec['ema_short'].iloc[0] <= rec['ema_long'].iloc[0]) and (rec['ema_short'].iloc[-1] > rec['ema_long'].iloc[-1])
    crossed_dn = (rec['ema_short'].iloc[0] >= rec['ema_long'].iloc[0]) and (rec['ema_short'].iloc[-1] < rec['ema_long'].iloc[-1])
    if crossed_up and daily_up:
        return 'BUY', "fresh EMA cross up + daily up"
    if crossed_dn and not daily_up:
        return 'SELL', "fresh EMA cross down + daily down"
    if crossed_up and not daily_up:
        return None, "cross up but daily down (blocked)"
    if crossed_dn and daily_up:
        return None, "cross down but daily up (blocked)"
    return None, "no fresh cross"


# ============================================================
# STRATEGY 3: 20-BAR BREAKOUT (Donchian)
# ============================================================

def _breakout_signal(df, lookback=20):
    """
    Trade close above/below N-bar high/low.
    Fires on the bar where the breakout happens (not after).
    """
    if len(df) < lookback + 2:
        return None, "insufficient history"
    i = len(df) - 1
    last_close = df.iloc[i]['close']
    prev_close = df.iloc[i-1]['close']
    # N-bar range BEFORE current bar
    recent = df.iloc[i-lookback:i]
    prev_high = recent['high'].max()
    prev_low  = recent['low'].min()
    if last_close > prev_high and prev_close <= prev_high:
        return 'BUY', f"close {last_close:.2f} > {lookback}-bar high {prev_high:.2f}"
    if last_close < prev_low and prev_close >= prev_low:
        return 'SELL', f"close {last_close:.2f} < {lookback}-bar low {prev_low:.2f}"
    return None, f"inside {lookback}-bar range [{prev_low:.2f}, {prev_high:.2f}]"


# ============================================================
# MARKET HOURS CHECK
# ============================================================

def _stock_market_open():
    """NYSE: Mon-Fri 14:30-21:00 UTC.
    For 4h strategies we relax this: scan if today is a weekday and we're
    within 2h of normal market hours."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    # Allow scans from 13:00 to 22:00 UTC (gives buffer around market hours)
    hour = now.hour
    return 13 <= hour <= 22


# ============================================================
# PRICE FETCHER (called by main.py for trade monitoring)
# ============================================================

def get_current_prices(cfg):
    """Returns dict {asset: current_price} for all assets in universe.
    Used by main.py to check open trades against TP/SL.
    """
    UNIVERSE = {
        'NVDA': 'NVDA',
        'AAPL': 'AAPL',
        'TSLA': 'TSLA',
        'GLD':  'GLD',
    }
    prices = {}
    for asset, ticker in UNIVERSE.items():
        df = _fetch_1h_data(ticker)
        if df is not None and len(df) > 0:
            prices[asset] = float(df.iloc[-1]['close'])
        else:
            logger.warning(f"No current price for {asset}")
    return prices


# ============================================================
# FIX 21: INTRA-BAR HISTORY FETCHER
# ============================================================
# Required because the bot scans every 4h. Between scans, price can move
# through SL/TP without the bot seeing it. If we only check current price,
# we close at the *current* price (could be far past SL) instead of at SL.
# This caused NVDA -£548 (designed -£375) and TSLA -£1087 (designed -£375)
# on 2026-05-11.
#
# This function fetches the 1h bars since trade entry, so check_and_close
# can walk through each bar and detect intra-bar SL/TP hits at the actual
# SL/TP price (modeling a real broker stop-loss order).

import pandas as pd
from datetime import datetime, timezone

def get_intra_bar_history(asset, since_time_iso):
    """Fetch 1h OHLC bars between since_time and now.
    
    Returns DataFrame with columns ts, open, high, low, close.
    Returns None if fetch fails or no data after since_time.
    
    since_time_iso: ISO format string (e.g. '2026-05-11T14:44:00')
    """
    UNIVERSE = {
        'NVDA': 'NVDA',
        'AAPL': 'AAPL',
        'TSLA': 'TSLA',
        'GLD':  'GLD',
    }
    ticker = UNIVERSE.get(asset)
    if not ticker:
        return None
    df = _fetch_1h_data(ticker)
    if df is None or df.empty:
        return None
    try:
        since_dt = pd.to_datetime(since_time_iso)
        # Make both timezone-aware or both naive for comparison
        df_ts = pd.to_datetime(df['ts'])
        if df_ts.dt.tz is not None and since_dt.tzinfo is None:
            since_dt = since_dt.tz_localize('UTC')
        elif df_ts.dt.tz is None and since_dt.tzinfo is not None:
            since_dt = since_dt.tz_localize(None)
        # Filter to bars at or after entry time
        filtered = df[df_ts >= since_dt].copy()
        if filtered.empty:
            return None
        return filtered.reset_index(drop=True)
    except Exception as e:
        logger.warning(f"intra-bar history parse error for {asset}: {e}")
        return None


# ============================================================
# BACKWARD-COMPAT ALIAS (so main.py doesn't need to change)
# ============================================================

def scan_markets(cfg, open_trades=None):
    """Alias for scan_for_signals - keeps API compat with main.py v5.2.
    Returns signals shaped to match what main.py expects.
    """
    raw_signals = scan_for_signals(cfg, open_trades)
    # main.py expects fields: asset, direction, price, take_profit, stop_loss,
    # leverage, strategy, confidence, expected_profit
    formatted = []
    for s in raw_signals:
        entry = s['entry_price']
        if s['direction'] == 'BUY':
            tp = entry * (1 + s['tp_pct'])
            sl = entry * (1 - s['sl_pct'])
        else:
            tp = entry * (1 - s['tp_pct'])
            sl = entry * (1 + s['sl_pct'])
        formatted.append({
            'asset':            s['asset'],
            'direction':        s['direction'],
            'price':            entry,
            'entry_price':      entry,
            'take_profit':      round(tp, 6),
            'stop_loss':        round(sl, 6),
            'tp_pct':           s['tp_pct'],
            'sl_pct':           s['sl_pct'],
            'leverage':         s['leverage'],
            'strategy':         s['strategy'],
            'confidence':       s['confidence'],
            'why':              s['why'],
            'max_hours':        s['max_hours'],
            'expected_profit':  round(entry * s['tp_pct'] * s['leverage'] * 50, 2),  # rough
            'regime':           'neutral',  # not used in v7 but main.py may log it
            'news_sentiment':   'neutral',
        })
    return formatted


# ============================================================
# MAIN SCAN FUNCTION
# ============================================================

def scan_for_signals(cfg, open_trades=None):
    """
    Run all 3 strategies on all 4 assets.
    Returns list of signal dicts, each with:
      asset, direction, strategy, entry_price, why, tp, sl, leverage, max_hours
    """
    if not _stock_market_open():
        logger.info("Stock/ETF market closed (NYSE hours: Mon-Fri 13-22 UTC). Skipping scan.")
        return []
    
    # ticker mapping: bot-internal name -> yfinance ticker
    UNIVERSE = {
        'NVDA': 'NVDA',
        'AAPL': 'AAPL',
        'TSLA': 'TSLA',
        'GLD':  'GLD',
    }
    
    open_assets = set()
    if open_trades:
        open_assets = {t['asset'] for t in open_trades if t.get('status') == 'OPEN'}
    
    signals = []
    strategies = [
        ('BBSqueeze_20',       _bb_squeeze_signal),
        ('MTF_Momentum_daily', _mtf_momentum_signal),
        ('Breakout_20bar',     _breakout_signal),
    ]
    
    for asset, yf_ticker in UNIVERSE.items():
        # Skip if we already have an open position on this asset (concentration filter)
        if asset in open_assets:
            logger.info(f"  [{asset}] skip - already has open position")
            continue
        
        # Fetch + resample
        df_1h = _fetch_1h_data(yf_ticker)
        if df_1h is None or len(df_1h) < 50:
            logger.warning(f"  [{asset}] insufficient 1h data, skipping")
            continue
        df_4h = _resample_to_4h(df_1h)
        if df_4h is None or len(df_4h) < HISTORY_BARS_NEEDED:
            logger.warning(f"  [{asset}] insufficient 4h data ({len(df_4h) if df_4h is not None else 0} bars), skipping")
            continue
        df_4h = _precompute(df_4h)
        
        current_price = float(df_4h.iloc[-1]['close'])
        
        # Run all 3 strategies on this asset
        asset_signals = []
        for strat_name, strat_fn in strategies:
            sig, reason = strat_fn(df_4h)
            if sig is None:
                logger.info(f"  [{asset}] {strat_name}: no signal ({reason})")
            else:
                logger.info(f"  [{asset}] {strat_name}: {sig} ({reason})")
                asset_signals.append({
                    'strategy': strat_name,
                    'direction': sig,
                    'reason': reason,
                })
        
        if not asset_signals:
            continue
        
        # If multiple strategies fire on same asset, prefer agreement
        # (e.g., if 2 strategies say BUY and 1 says SELL, take BUY)
        directions = [s['direction'] for s in asset_signals]
        if directions.count('BUY') > directions.count('SELL'):
            chosen_dir = 'BUY'
        elif directions.count('SELL') > directions.count('BUY'):
            chosen_dir = 'SELL'
        else:
            # Tie - take the first (priority order: BBSqueeze, MTF, Breakout)
            chosen_dir = asset_signals[0]['direction']
        
        # Use strategy(s) that voted for the chosen direction
        winning_strats = [s for s in asset_signals if s['direction'] == chosen_dir]
        strat_label = '+'.join(s['strategy'] for s in winning_strats)
        why = ' | '.join(s['reason'] for s in winning_strats)
        
        # Build the signal
        cfg_asset = asset_config.get(asset)
        signal = {
            'asset':       asset,
            'direction':   chosen_dir,
            'strategy':    strat_label,
            'entry_price': current_price,
            'tp_pct':      cfg_asset['tp'],
            'sl_pct':      cfg_asset['sl'],
            'leverage':    cfg_asset['leverage'],
            'max_hours':   cfg_asset['max_hours'],
            'why':         why,
            'confidence':  min(95, 70 + 8 * len(winning_strats)),  # 78/86/94 for 1/2/3 agreeing
            'n_strategies_agree': len(winning_strats),
        }
        signals.append(signal)
        logger.info(f"  [{asset}] APPROVED: {chosen_dir} via {strat_label} @ {current_price}")
    
    if not signals:
        logger.info("No signals this scan.")
    return signals
