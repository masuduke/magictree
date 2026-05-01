"""
market_scanner.py  (v4 - Risk-First Rewrite)
--------------------------------------------
All 8 fixes applied:
  1. Per-asset SL/TP from asset_config.py (no more flat globals)
  2. Risk-first AI prompt
  3. BTC regime detection (300d daily data)
  4. Forex regime filter
  5. Stock regime filter
  6. Volume skip for forex (fake data)
  7. Min 10 historical setups required
  8. Forex session hours (08-21 UTC)
"""
import logging
import json
import requests
import pandas as pd
from datetime import datetime
from modules import asset_config

logger = logging.getLogger(__name__)

STOCK_OPEN_HOUR  = 14
STOCK_CLOSE_HOUR = 21
FOREX_OPEN_HOUR  = 8
FOREX_CLOSE_HOUR = 21

BULLISH_KEYWORDS = [
    'surge', 'rally', 'breakout', 'bullish', 'upgrade', 'adoption',
    'partnership', 'record', 'high', 'growth', 'buy', 'accumulate',
    'institutional', 'etf', 'approval', 'positive', 'profit', 'gain'
]

BEARISH_KEYWORDS = [
    'crash', 'collapse', 'ban', 'hack', 'fraud', 'lawsuit', 'recession',
    'inflation', 'rate hike', 'selloff', 'plunge', 'tumble', 'warning',
    'fear', 'panic', 'dump', 'bearish', 'downgrade', 'loss', 'drop'
]

# Cached regimes (refreshed per scan)
_regime_cache = {}


# -- Helpers ------------------------------------------------------------------

def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _is_stock_hours():
    now = datetime.utcnow()
    return now.weekday() < 5 and STOCK_OPEN_HOUR <= now.hour <= STOCK_CLOSE_HOUR


def _is_forex_hours():
    now = datetime.utcnow()
    # Forex: Mon-Fri, 08-21 UTC (London + NY overlap coverage)
    return now.weekday() < 5 and FOREX_OPEN_HOUR <= now.hour <= FOREX_CLOSE_HOUR


def _is_forex_asset(asset):
    return '/' in asset and 'USDT' not in asset and '/USDT' not in asset


# -- FIX 3/4/5: Market regime detection ---------------------------------------

def _compute_regime(df):
    """Return 'bull', 'bear', or 'neutral' based on 50/200 EMA cross."""
    if df is None or len(df) < 210:
        return 'neutral'
    close = df['close'].astype(float)
    ema50  = _ema(close, 50).iloc[-1]
    ema200 = _ema(close, 200).iloc[-1]
    price  = float(close.iloc[-1])
    if ema50 > ema200 and price > ema50:
        return 'bull'
    if ema50 < ema200 and price < ema50:
        return 'bear'
    return 'neutral'


def get_crypto_regime():
    if 'crypto' in _regime_cache:
        return _regime_cache['crypto']
    df = _fetch_daily_yf('BTC-USD', period='400d')
    regime = _compute_regime(df)
    _regime_cache['crypto'] = regime
    logger.info(f"Crypto regime (BTC daily): {regime}")
    return regime


def get_forex_regime():
    if 'forex' in _regime_cache:
        return _regime_cache['forex']
    df = _fetch_daily_yf('DX-Y.NYB', period='400d')  # DXY proxy
    regime = _compute_regime(df)
    _regime_cache['forex'] = regime
    logger.info(f"Forex regime (DXY daily): {regime}")
    return regime


def get_stock_regime():
    if 'stock' in _regime_cache:
        return _regime_cache['stock']
    df = _fetch_daily_yf('SPY', period='400d')
    regime = _compute_regime(df)
    _regime_cache['stock'] = regime
    logger.info(f"Stock regime (SPY daily): {regime}")
    return regime


def _regime_allows(direction, regime):
    """Reject counter-trend trades."""
    if regime == 'neutral':
        return True
    if regime == 'bull' and direction == 'SELL':
        return False
    if regime == 'bear' and direction == 'BUY':
        return False
    return True


# -- FIX 6: Volume ratio (skips forex) ----------------------------------------

def _volume_ratio(df, asset):
    """Return vol/avg_vol or 1.0 for forex (fake volume data)."""
    if _is_forex_asset(asset):
        return 1.0
    if df is None or 'vol' not in df.columns or len(df) < 21:
        return 1.0
    vol = df['vol'].astype(float)
    cur = float(vol.iloc[-1])
    avg = float(vol.iloc[-20:].mean())
    if avg <= 0:
        return 1.0
    return cur / avg


# -- LAYER 1: Technical -------------------------------------------------------

def _technical_score(df, asset, ema_f, ema_s, rsi_lo, rsi_hi):
    if df is None or len(df) < ema_s + 30:
        return {'score': 0, 'direction': None}

    close = df['close'].astype(float)
    ef    = _ema(close, ema_f)
    es    = _ema(close, ema_s)
    e50   = _ema(close, 50)
    rsi   = _rsi(close)

    cf, pf   = ef.iloc[-1], ef.iloc[-2]
    cs, ps   = es.iloc[-1], es.iloc[-2]
    cur_rsi  = rsi.iloc[-1]
    price    = float(close.iloc[-1])
    e50_val  = e50.iloc[-1]
    ema_sep  = abs(cf - cs) / cs * 100

    vol_ratio = _volume_ratio(df, asset)
    vol_ok    = vol_ratio > 0.8

    cross_up   = pf <= ps and cf > cs
    cross_down = pf >= ps and cf < cs
    rsi_ok     = rsi_lo <= cur_rsi <= rsi_hi

    direction = None
    score     = 0
    reasons   = []

    if cross_up and rsi_ok and price > e50_val:
        direction = 'BUY'
        score += 40; reasons.append('EMA bullish crossover')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price above 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    elif cross_down and rsi_ok and price < e50_val:
        direction = 'SELL'
        score += 40; reasons.append('EMA bearish crossover')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price below 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    return {
        'score':     min(score, 100),
        'direction': direction,
        'price':     price,
        'rsi':       round(cur_rsi, 2),
        'ema_sep':   round(ema_sep, 3),
        'reasons':   reasons,
    }


# -- LAYER 2: News Sentiment --------------------------------------------------

def _fetch_news(asset, asset_type):
    headlines = []
    try:
        ticker = asset.split('/')[0] if '/' in asset else asset
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        r   = requests.get(url, timeout=8)
        if r.ok:
            import re
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', r.text)
            headlines.extend([t for t in titles if len(t) > 15][:10])
    except Exception as e:
        logger.debug(f"News fetch error: {e}")
    return headlines[:15]


def _sentiment_score(headlines, direction):
    if not headlines:
        return {'score': 50, 'sentiment': 'neutral', 'headlines': [],
                'bullish_kw': 0, 'bearish_kw': 0}
    text = ' '.join(headlines).lower()
    bull = sum(text.count(kw) for kw in BULLISH_KEYWORDS)
    bear = sum(text.count(kw) for kw in BEARISH_KEYWORDS)
    total = bull + bear
    raw   = (bull / total * 100) if total > 0 else 50
    sent  = 'bullish' if raw > 60 else 'bearish' if raw < 40 else 'neutral'
    score = raw if direction == 'BUY' else (100 - raw)
    return {
        'score':      round(score, 1),
        'sentiment':  sent,
        'bullish_kw': bull,
        'bearish_kw': bear,
        'headlines':  headlines[:5],
    }


# -- LAYER 3: Historical Backtest (FIX 7: min 10 setups) ----------------------

def _historical_score(df, direction, tp_pct=0.02, sl_pct=0.01):
    if df is None or len(df) < 100:
        return {'score': 50, 'win_rate': 50, 'sample_size': 0}

    close = df['close'].astype(float)
    ef    = _ema(close, 9)
    es    = _ema(close, 21)
    rsi_s = _rsi(close)
    wins  = 0
    total = 0

    for i in range(30, len(df) - 12):
        cf, pf = ef.iloc[i], ef.iloc[i-1]
        cs, ps = es.iloc[i], es.iloc[i-1]
        r      = float(rsi_s.iloc[i])
        p      = float(close.iloc[i])

        setup_buy  = direction == 'BUY'  and pf <= ps and cf > cs and 45 <= r <= 55
        setup_sell = direction == 'SELL' and pf >= ps and cf < cs and 45 <= r <= 55

        if setup_buy or setup_sell:
            tp = p * (1 + tp_pct) if setup_buy else p * (1 - tp_pct)
            sl = p * (1 - sl_pct) if setup_buy else p * (1 + sl_pct)
            future = close.iloc[i+1:i+12].values
            for fp in future:
                if (setup_buy and fp >= tp) or (setup_sell and fp <= tp):
                    wins += 1
                    total += 1
                    break
                elif (setup_buy and fp <= sl) or (setup_sell and fp >= sl):
                    total += 1
                    break

    # FIX 7: require minimum 10 setups or return neutral
    if total < 10:
        return {'score': 50, 'win_rate': 50, 'sample_size': total}

    win_rate = round(wins / total * 100, 1)
    return {'score': win_rate, 'win_rate': win_rate, 'sample_size': total}


# -- LAYER 4: Claude AI Decision (FIX 2: risk-first prompt) -------------------

def _ai_decision(asset, direction, price, tech, sentiment, historical, regime, api_key):
    if not api_key:
        avg = tech['score'] * 0.5 + sentiment['score'] * 0.2 + historical['score'] * 0.3
        return {'approved': avg >= 70, 'confidence': round(avg),
                'reasoning': 'Weighted average (no API key)',
                'key_risk': 'Unknown', 'expected_outcome': 'UNCERTAIN'}

    headlines_text = '\n'.join(f"  - {h}" for h in sentiment.get('headlines', [])[:5])

    prompt = f"""You are a risk-first trader protecting real capital.

CORE PRINCIPLE:
- Missing a trade costs NOTHING.
- Taking a bad trade costs MONEY.
- When in doubt, REJECT. Default answer is NO.
- Only approve trades with overwhelming evidence of edge.

TRADE SETUP:
Asset: {asset} | Direction: {direction} | Price: {price} | Market regime: {regime}

TECHNICAL (score {tech['score']}/100):
RSI: {tech.get('rsi')} | EMA sep: {tech.get('ema_sep')}%
Signals: {', '.join(tech.get('reasons', []))}

NEWS SENTIMENT (score {sentiment['score']}/100):
Sentiment: {sentiment.get('sentiment')} | Bullish kw: {sentiment.get('bullish_kw')} | Bearish kw: {sentiment.get('bearish_kw')}
Headlines:
{headlines_text if headlines_text else '  No headlines available'}

HISTORICAL BACKTEST (score {historical['score']}/100):
Win rate on similar setups: {historical.get('win_rate')}% from {historical.get('sample_size')} trades

REJECT IMMEDIATELY if any of these are true:
- Historical sample_size < 10 (not enough data to trust)
- Historical win rate below 55%
- News sentiment opposes direction
- Technical score below 65
- Market regime opposes direction (bull regime + SELL, or bear regime + BUY)
- RSI outside 45-55

Only APPROVE if ALL of these are true:
- sample_size >= 10 AND win_rate >= 58%
- Technical score >= 65
- News sentiment neutral or supportive
- Regime is neutral OR aligned with direction
- You can articulate a specific edge in one sentence

Respond ONLY in valid JSON:
{{"approved": true/false, "confidence": 0-100, "reasoning": "brief reason", "key_risk": "main risk", "expected_outcome": "WIN/LOSS/UNCERTAIN"}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg    = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1].replace('json', '').strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"AI decision error: {e}")
        # Risk-first fallback: reject on error
        return {'approved': False, 'confidence': 0,
                'reasoning': f'AI error - rejected for safety ({e})',
                'key_risk': 'Unknown', 'expected_outcome': 'UNCERTAIN'}


# -- Signal builder -----------------------------------------------------------

def _build_signal(df, asset, asset_type, cfg):
    # Regime filter (FIX 3/4/5)
    if asset_type == 'crypto':
        regime = get_crypto_regime()
    elif asset_type == 'forex':
        regime = get_forex_regime()
    elif asset_type == 'stock':
        regime = get_stock_regime()
    else:
        regime = 'neutral'

    tech = _technical_score(df, asset, cfg.EMA_FAST, cfg.EMA_SLOW,
                            cfg.RSI_LOWER_BAND, cfg.RSI_UPPER_BAND)
    if not tech['direction'] or tech['score'] < 40:
        return None

    direction = tech['direction']
    price     = tech['price']

    # Regime check
    if not _regime_allows(direction, regime):
        logger.info(f"Regime blocked: {asset} {direction} ({regime} regime)")
        return None

    # FIX 1: per-asset SL/TP from asset_config
    tp_pct = asset_config.get_tp(asset)
    sl_pct = asset_config.get_sl(asset)

    headlines  = _fetch_news(asset, asset_type)
    sentiment  = _sentiment_score(headlines, direction)
    historical = _historical_score(df, direction, tp_pct, sl_pct)

    ai = _ai_decision(asset, direction, price, tech, sentiment, historical,
                      regime, cfg.ANTHROPIC_API_KEY)

    if not ai.get('approved', False):
        logger.info(f"AI rejected {asset} {direction} - {ai.get('reasoning')}")
        return None

    confidence = ai.get('confidence', 0)
    if confidence < cfg.MIN_CONFIDENCE:
        logger.info(f"Low confidence ({confidence}%) {asset} - skipped")
        return None

    # FIX 1: use per-asset SL/TP (not flat cfg values)
    tp = round(price * ((1 + tp_pct) if direction == 'BUY' else (1 - tp_pct)), 6)
    sl = round(price * ((1 - sl_pct) if direction == 'BUY' else (1 + sl_pct)), 6)

    logger.info(f"SIGNAL APPROVED: {direction} {asset} @ {price} | "
                f"Conf:{confidence}% | Tech:{tech['score']} | "
                f"Regime:{regime} | News:{sentiment['sentiment']} | "
                f"HistWR:{historical['win_rate']}% ({historical['sample_size']}) | "
                f"TP:{tp_pct*100:.2f}% SL:{sl_pct*100:.2f}% | "
                f"{ai.get('reasoning')}")

    return {
        'asset':           asset,
        'asset_type':      asset_type,
        'direction':       direction,
        'price':           round(price, 6),
        'take_profit':     tp,
        'stop_loss':       sl,
        'confidence':      confidence,
        'timestamp':       datetime.utcnow().isoformat(),
        'rsi':             tech.get('rsi'),
        'tech_score':      tech['score'],
        'sentiment_score': sentiment['score'],
        'sentiment':       sentiment.get('sentiment'),
        'historical_wr':   historical.get('win_rate'),
        'sample_size':     historical.get('sample_size'),
        'regime':          regime,
        'ai_reasoning':    ai.get('reasoning'),
        'ai_risk':         ai.get('key_risk'),
        'top_headlines':   sentiment.get('headlines', [])[:3],
    }


# -- Public API ---------------------------------------------------------------

def scan_markets(cfg, open_trades=None):
    # Clear regime cache at start of each scan (refreshes once per scan)
    _regime_cache.clear()

    signals = []

    # Crypto (24/7)
    for symbol in cfg.CRYPTO_ASSETS:
        df  = _fetch_crypto(symbol)
        sig = _build_signal(df, symbol, 'crypto', cfg)
        if sig:
            signals.append(sig)

    # Forex (FIX 8: only during session hours)
    if _is_forex_hours():
        forex_assets = getattr(cfg, 'FOREX_ASSETS', {})
        for ticker, name in forex_assets.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, name, 'forex', cfg)
            if sig:
                sig['ticker'] = ticker
                signals.append(sig)
    else:
        logger.info("Forex session closed (active 08-21 UTC Mon-Fri).")

    # Stocks (NYSE hours)
    if _is_stock_hours():
        for ticker, name in cfg.STOCK_ASSETS.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, ticker, 'stock', cfg)
            if sig:
                sig['name'] = name
                signals.append(sig)
    else:
        logger.info("Stock market closed.")

    # Commodities
    for ticker, name in cfg.COMMODITY_ASSETS.items():
        df  = _fetch_yf(ticker)
        sig = _build_signal(df, name, 'commodity', cfg)
        if sig:
            sig['ticker'] = ticker
            signals.append(sig)

    if not signals:
        logger.info("No high-quality signals - waiting for perfect setup.")
    return signals


def _fetch_crypto(symbol, timeframe='15m', limit=200):
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


def _fetch_yf(ticker, period='5d', interval='15m', limit=200):
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
        logger.error(f"yfinance ({ticker}): {e}")
        return None


def _fetch_daily_yf(ticker, period='400d'):
    """Fetch daily bars for regime detection."""
    try:
        import yfinance as yf
        raw = yf.download(ticker, period=period, interval='1d',
                          progress=False, auto_adjust=True)
        if raw.empty:
            return None
        df = raw.reset_index()
        df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]
        df = df.rename(columns={'Datetime':'ts','Date':'ts','Open':'open',
                                 'High':'high','Low':'low','Close':'close','Volume':'vol'})
        return df[['ts','open','high','low','close','vol']].dropna()
    except Exception as e:
        logger.error(f"yfinance daily ({ticker}): {e}")
        return None


def get_current_prices(cfg):
    prices = {}
    for s in cfg.CRYPTO_ASSETS:
        df = _fetch_crypto(s, limit=5)
        if df is not None:
            prices[s] = float(df['close'].iloc[-1])
    forex_assets = getattr(cfg, 'FOREX_ASSETS', {})
    all_yf = {**cfg.STOCK_ASSETS, **cfg.COMMODITY_ASSETS, **forex_assets}
    for ticker, name in all_yf.items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[name if name else ticker] = float(df['close'].iloc[-1])
    return prices
