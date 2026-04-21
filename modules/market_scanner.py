"""
market_scanner.py  (v2 — multi-asset)
---------------------------------------
Scans ALL asset classes:
  • Crypto     → BTC/USDT, ETH/USDT      (via Binance/ccxt — 24/7)
  • Stocks     → AAPL, TSLA, NVDA etc.   (via yfinance — market hours only)
  • Commodities→ Gold, Silver, Oil        (via yfinance — 24/5)

Execution for ALL assets happens via eToro API (or paper trade).
"""
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

STOCK_OPEN_HOUR  = 14   # 9:30am ET ≈ 14:30 UTC
STOCK_CLOSE_HOUR = 21   # 4:00pm ET ≈ 21:00 UTC


def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _confidence(rsi, ema_fast, ema_slow):
    score = 50
    score += (100 - abs(rsi - 50) * 2 - 50) * 0.3
    sep = abs(ema_fast - ema_slow) / ema_slow * 100
    if sep > 0.3: score += 10
    if sep > 0.7: score += 5
    return int(min(max(score, 0), 100))


def _is_stock_hours():
    return STOCK_OPEN_HOUR <= datetime.utcnow().hour <= STOCK_CLOSE_HOUR


def _fetch_crypto(symbol, timeframe='15m', limit=120):
    try:
        import ccxt
        ex   = ccxt.binance({'enableRateLimit': True})
        data = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        df   = pd.DataFrame(data, columns=['ts','open','high','low','close','vol'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except Exception as e:
        logger.error(f"Crypto fetch ({symbol}): {e}")
        return None


def _fetch_yf(ticker, period='5d', interval='15m', limit=120):
    try:
        import yfinance as yf
        raw = yf.download(ticker, period=period, interval=interval,
                          progress=False, auto_adjust=True)
        if raw.empty:
            return None
        df = raw.reset_index()
        df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]
        df = df.rename(columns={'Datetime':'ts','Date':'ts','Open':'open',
                                 'High':'high','Low':'low','Close':'close','Volume':'vol'})
        return df[['ts','open','high','low','close','vol']].dropna().tail(limit)
    except Exception as e:
        logger.error(f"yfinance fetch ({ticker}): {e}")
        return None


def _analyse(df, asset, asset_type, tp_pct, sl_pct, ef, es, rlo, rhi):
    if df is None or len(df) < es + 10:
        return None
    close = df['close'].astype(float)
    ef_s, es_s = _ema(close, ef), _ema(close, es)
    rsi_s = _rsi(close)
    cf, pf = ef_s.iloc[-1], ef_s.iloc[-2]
    cs, ps = es_s.iloc[-1], es_s.iloc[-2]
    rsi_v  = rsi_s.iloc[-1]
    price  = float(close.iloc[-1])
    direction = None
    if pf <= ps and cf > cs and rlo <= rsi_v <= rhi:
        direction = 'BUY'
    elif pf >= ps and cf < cs and rlo <= rsi_v <= rhi:
        direction = 'SELL'
    if not direction:
        return None
    tp = round(price * (1 + tp_pct if direction == 'BUY' else 1 - tp_pct), 6)
    sl = round(price * (1 - sl_pct if direction == 'BUY' else 1 + sl_pct), 6)
    return {
        'asset': asset, 'asset_type': asset_type,
        'direction': direction, 'price': round(price, 6),
        'take_profit': tp, 'stop_loss': sl,
        'rsi': round(rsi_v, 2), 'ema_fast': round(cf, 6), 'ema_slow': round(cs, 6),
        'confidence': _confidence(rsi_v, cf, cs),
        'timestamp': datetime.utcnow().isoformat(),
    }


def scan_markets(cfg):
    signals = []
    kw = dict(tp_pct=cfg.TAKE_PROFIT_PCT, sl_pct=cfg.STOP_LOSS_PCT,
              ef=cfg.EMA_FAST, es=cfg.EMA_SLOW,
              rlo=cfg.RSI_LOWER_BAND, rhi=cfg.RSI_UPPER_BAND)

    for symbol in cfg.CRYPTO_ASSETS:
        sig = _analyse(_fetch_crypto(symbol), symbol, 'crypto', **kw)
        if sig:
            signals.append(sig)
            logger.info(f"🔵 CRYPTO  {sig['direction']} {symbol} @ {sig['price']} [{sig['confidence']}%]")

    if _is_stock_hours():
        for ticker, name in cfg.STOCK_ASSETS.items():
            sig = _analyse(_fetch_yf(ticker), ticker, 'stock', **kw)
            if sig:
                sig['name'] = name
                signals.append(sig)
                logger.info(f"📈 STOCK   {sig['direction']} {ticker} ({name}) @ {sig['price']} [{sig['confidence']}%]")
    else:
        logger.info("⏰ Stock market closed – skipping stock scan.")

    for ticker, name in cfg.COMMODITY_ASSETS.items():
        sig = _analyse(_fetch_yf(ticker), name, 'commodity', **kw)
        if sig:
            sig['ticker'] = ticker
            signals.append(sig)
            logger.info(f"🥇 COMMOD  {sig['direction']} {name} @ {sig['price']} [{sig['confidence']}%]")

    if not signals:
        logger.info("🔍 No signals this scan.")
    return signals


def get_current_prices(cfg):
    prices = {}
    for s in cfg.CRYPTO_ASSETS:
        df = _fetch_crypto(s, limit=5)
        if df is not None:
            prices[s] = float(df['close'].iloc[-1])
    for ticker, name in {**cfg.STOCK_ASSETS, **cfg.COMMODITY_ASSETS}.items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[name if name else ticker] = float(df['close'].iloc[-1])
    return prices
