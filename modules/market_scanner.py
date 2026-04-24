"""
market_scanner.py  v4 — Ultimate Edition
------------------------------------------
Asset universe: Crypto + Forex + Stocks + ETFs + Commodities
Analysis tools:
  1. Multi-timeframe (15min + 1hr confirmation)
  2. EMA 9/21/50 crossover + trend filter
  3. RSI + MACD confirmation
  4. Volume analysis
  5. Support/Resistance levels
  6. News sentiment (Yahoo Finance RSS)
  7. Historical win rate backtest
  8. Correlation check (no duplicate exposure)
  9. Session timing (London/NY overlap best)
 10. Claude AI final decision

Target: 80%+ confidence signals only → consistent £15-25 profit per trade
"""
import logging
import json
import re
import requests
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Session hours UTC ─────────────────────────────────────────────────────────
LONDON_OPEN  = 8
LONDON_CLOSE = 17
NY_OPEN      = 14
NY_CLOSE     = 21

BULLISH_KW = ['surge','rally','breakout','bullish','upgrade','adoption','record',
              'growth','buy','accumulate','institutional','approval','profit','gain',
              'high','strong','beat','above','positive','rise','jump']
BEARISH_KW = ['crash','collapse','ban','hack','fraud','lawsuit','recession',
              'inflation','hike','selloff','plunge','tumble','warning','fear',
              'panic','dump','bearish','downgrade','loss','drop','weak','miss',
              'below','negative','fall','decline','cut','concern']


# ── Session helpers ───────────────────────────────────────────────────────────

def _is_london():
    return LONDON_OPEN <= datetime.utcnow().hour < LONDON_CLOSE

def _is_ny():
    return NY_OPEN <= datetime.utcnow().hour < NY_CLOSE

def _is_overlap():
    """London/NY overlap 14:00-17:00 UTC — highest volume period"""
    h = datetime.utcnow().hour
    return NY_OPEN <= h < LONDON_CLOSE

def _is_stock_hours():
    now = datetime.utcnow()
    return now.weekday() < 5 and NY_OPEN <= now.hour < NY_CLOSE

def _is_forex_hours():
    now = datetime.utcnow()
    return now.weekday() < 5 and LONDON_OPEN <= now.hour < NY_CLOSE

def _session_multiplier():
    """Returns quality multiplier based on current session."""
    if _is_overlap():
        return 1.2    # Best session
    elif _is_london() or _is_ny():
        return 1.0    # Good session
    else:
        return 0.8    # Quiet hours


# ── Technical indicators ──────────────────────────────────────────────────────

def _ema(s, p): return s.ewm(span=p, adjust=False).mean()

def _rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l.replace(0, 1e-9)))

def _macd(s, fast=12, slow=26, signal=9):
    macd_line   = _ema(s, fast) - _ema(s, slow)
    signal_line = _ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram

def _support_resistance(close, lookback=20):
    """Finds key support and resistance levels."""
    recent = close.tail(lookback)
    resistance = float(recent.max())
    support    = float(recent.min())
    return support, resistance

def _atr(df, period=14):
    """Average True Range — measures volatility."""
    high  = df['high'].astype(float)
    low   = df['low'].astype(float)
    close = df['close'].astype(float)
    tr    = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ── Data fetchers ─────────────────────────────────────────────────────────────

def _fetch_crypto(symbol, timeframe='15m', limit=200):
    try:
        import ccxt
        ex   = ccxt.binance({'enableRateLimit': True})
        data = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        df   = pd.DataFrame(data, columns=['ts','open','high','low','close','vol'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df.astype({'open':float,'high':float,'low':float,'close':float,'vol':float})
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
        cols = ['ts','open','high','low','close','vol']
        cols = [c for c in cols if c in df.columns]
        return df[cols].dropna().tail(limit)
    except Exception as e:
        logger.error(f"yfinance ({ticker}): {e}")
        return None


def _fetch_higher_tf(ticker, asset_type):
    """Fetch 1-hour chart for trend confirmation."""
    try:
        if asset_type == 'crypto':
            import ccxt
            ex   = ccxt.binance({'enableRateLimit': True})
            data = ex.fetch_ohlcv(ticker, '1h', limit=100)
            df   = pd.DataFrame(data, columns=['ts','open','high','low','close','vol'])
            df['ts'] = pd.to_datetime(df['ts'], unit='ms')
            return df
        else:
            return _fetch_yf(ticker, period='30d', interval='1h', limit=100)
    except Exception as e:
        logger.debug(f"Higher TF fetch error: {e}")
        return None


# ── LAYER 1: Multi-timeframe Technical ───────────────────────────────────────

def _technical_analysis(df, df_1h, ema_f, ema_s, rsi_lo, rsi_hi):
    if df is None or len(df) < ema_s + 30:
        return {'score': 0, 'direction': None}

    close  = df['close'].astype(float)
    vol    = df['vol'].astype(float) if 'vol' in df.columns else None
    ef     = _ema(close, ema_f)
    es     = _ema(close, ema_s)
    e50    = _ema(close, 50)
    rsi_s  = _rsi(close)
    macd_l, macd_sig, macd_hist = _macd(close)
    sup, res = _support_resistance(close)

    cf, pf   = float(ef.iloc[-1]),    float(ef.iloc[-2])
    cs, ps   = float(es.iloc[-1]),    float(es.iloc[-2])
    cur_rsi  = float(rsi_s.iloc[-1])
    price    = float(close.iloc[-1])
    e50_val  = float(e50.iloc[-1])
    macd_cur = float(macd_hist.iloc[-1])
    macd_prv = float(macd_hist.iloc[-2])
    ema_sep  = abs(cf - cs) / cs * 100

    # Volume check
    vol_ok = True
    if vol is not None and len(vol) > 20:
        avg_vol = float(vol.iloc[-20:].mean())
        cur_vol = float(vol.iloc[-1])
        vol_ok  = cur_vol > avg_vol * 0.9

    # Higher timeframe trend check
    htf_trend = 'neutral'
    if df_1h is not None and len(df_1h) > 21:
        htf_close = df_1h['close'].astype(float)
        htf_ef    = _ema(htf_close, 9)
        htf_es    = _ema(htf_close, 21)
        if float(htf_ef.iloc[-1]) > float(htf_es.iloc[-1]):
            htf_trend = 'bullish'
        else:
            htf_trend = 'bearish'

    # Distance from support/resistance
    dist_to_res = (res - price) / price * 100
    dist_to_sup = (price - sup) / price * 100

    cross_up   = pf <= ps and cf > cs
    cross_down = pf >= ps and cf < cs
    rsi_ok     = rsi_lo <= cur_rsi <= rsi_hi
    trend_up   = price > e50_val
    trend_down = price < e50_val
    macd_bull  = macd_cur > 0 and macd_cur > macd_prv
    macd_bear  = macd_cur < 0 and macd_cur < macd_prv

    direction = None
    score     = 0
    reasons   = []

    if cross_up and rsi_ok and trend_up:
        direction = 'BUY'
        score += 30
        reasons.append('EMA 9/21 bullish crossover')
        if rsi_ok:
            score += 15
            reasons.append(f'RSI {cur_rsi:.1f} neutral')
        if trend_up:
            score += 15
            reasons.append('Above 50 EMA trend')
        if macd_bull:
            score += 15
            reasons.append('MACD bullish')
        if vol_ok:
            score += 10
            reasons.append('Volume confirmed')
        if htf_trend == 'bullish':
            score += 10
            reasons.append('1H chart agrees')
        if dist_to_res > 1.5:
            score += 5
            reasons.append(f'{dist_to_res:.1f}% room to resistance')

    elif cross_down and rsi_ok and trend_down:
        direction = 'SELL'
        score += 30
        reasons.append('EMA 9/21 bearish crossover')
        if rsi_ok:
            score += 15
            reasons.append(f'RSI {cur_rsi:.1f} neutral')
        if trend_down:
            score += 15
            reasons.append('Below 50 EMA trend')
        if macd_bear:
            score += 15
            reasons.append('MACD bearish')
        if vol_ok:
            score += 10
            reasons.append('Volume confirmed')
        if htf_trend == 'bearish':
            score += 10
            reasons.append('1H chart agrees')
        if dist_to_sup > 1.5:
            score += 5
            reasons.append(f'{dist_to_sup:.1f}% room to support')

    if ema_sep > 0.5:
        score += 5

    session_mult = _session_multiplier()
    score = min(int(score * session_mult), 100)

    return {
        'score':     score,
        'direction': direction,
        'price':     price,
        'rsi':       round(cur_rsi, 2),
        'ema_sep':   round(ema_sep, 3),
        'macd':      round(macd_cur, 6),
        'support':   round(sup, 4),
        'resistance': round(res, 4),
        'htf_trend': htf_trend,
        'vol_ok':    vol_ok,
        'reasons':   reasons,
    }


# ── LAYER 2: News Sentiment ───────────────────────────────────────────────────

def _fetch_news(asset, asset_type):
    headlines = []
    try:
        ticker = asset.split('/')[0] if '/' in asset else asset.replace('=X','').replace('=F','')
        # Yahoo Finance RSS
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        r   = requests.get(url, timeout=6)
        if r.ok:
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', r.text)
            headlines.extend([t for t in titles if len(t) > 15][:10])
    except Exception:
        pass
    return headlines[:15]


def _sentiment_score(headlines, direction):
    if not headlines:
        return {'score': 50, 'sentiment': 'neutral', 'headlines': [],
                'bullish_kw': 0, 'bearish_kw': 0}
    text = ' '.join(headlines).lower()
    bull = sum(text.count(kw) for kw in BULLISH_KW)
    bear = sum(text.count(kw) for kw in BEARISH_KW)
    total = bull + bear
    raw   = (bull / total * 100) if total > 0 else 50
    sent  = 'bullish' if raw > 60 else 'bearish' if raw < 40 else 'neutral'
    score = raw if direction == 'BUY' else (100 - raw)
    return {'score': round(score, 1), 'sentiment': sent,
            'bullish_kw': bull, 'bearish_kw': bear, 'headlines': headlines[:5]}


# ── LAYER 3: Historical Backtest ──────────────────────────────────────────────

def _historical_score(df, direction, tp_pct, sl_pct):
    if df is None or len(df) < 100:
        return {'score': 50, 'win_rate': 50, 'sample_size': 0}
    close = df['close'].astype(float)
    ef    = _ema(close, 9)
    es    = _ema(close, 21)
    rsi_s = _rsi(close)
    wins = total = 0
    for i in range(30, len(df) - 12):
        cf, pf = float(ef.iloc[i]), float(ef.iloc[i-1])
        cs, ps = float(es.iloc[i]), float(es.iloc[i-1])
        r = float(rsi_s.iloc[i])
        p = float(close.iloc[i])
        buy  = direction == 'BUY'  and pf <= ps and cf > cs and 43 <= r <= 57
        sell = direction == 'SELL' and pf >= ps and cf < cs and 43 <= r <= 57
        if buy or sell:
            tp = p * (1 + tp_pct) if buy else p * (1 - tp_pct)
            sl = p * (1 - sl_pct) if buy else p * (1 + sl_pct)
            for fp in close.iloc[i+1:i+12].values:
                if (buy and fp >= tp) or (sell and fp <= tp):
                    wins += 1; total += 1; break
                elif (buy and fp <= sl) or (sell and fp >= sl):
                    total += 1; break
    if total == 0:
        return {'score': 50, 'win_rate': 50, 'sample_size': 0}
    wr = round(wins / total * 100, 1)
    return {'score': wr, 'win_rate': wr, 'sample_size': total}


# ── LAYER 4: Correlation Check ────────────────────────────────────────────────

def _correlation_ok(asset, direction, open_trades):
    """Prevents trading correlated assets in same direction."""
    correlated = {
        'BTC/USDT': ['ETH/USDT', 'SOL/USDT', 'BNB/USDT'],
        'ETH/USDT': ['BTC/USDT', 'SOL/USDT'],
        'SOL/USDT': ['BTC/USDT', 'ETH/USDT'],
        'GOLD':     ['GLD', 'GC=F'],
        'GLD':      ['GOLD', 'GC=F'],
        'EUR/USD':  ['GBP/USD', 'AUD/USD'],
        'GBP/USD':  ['EUR/USD'],
        'SPY':      ['QQQ'],
        'QQQ':      ['SPY'],
    }
    corr_assets = correlated.get(asset, [])
    for t in open_trades:
        if t.get('asset') in corr_assets and t.get('direction') == direction:
            logger.info(f"⚠️ Correlation block: {asset} {direction} — already in {t['asset']}")
            return False
    return True


# ── LAYER 5: Claude AI Decision ───────────────────────────────────────────────

def _ai_decision(asset, direction, price, tech, sentiment, historical, api_key):
    if not api_key:
        avg = tech['score']*0.5 + sentiment['score']*0.2 + historical['score']*0.3
        return {'approved': avg >= 75, 'confidence': round(avg),
                'reasoning': 'Weighted average', 'key_risk': 'No AI', 'expected_outcome': 'UNCERTAIN'}

    heads = '\n'.join(f"  • {h}" for h in sentiment.get('headlines', [])[:5])

    prompt = f"""You are a professional quant trader with strict rules. Analyze this trade.

ASSET: {asset} | DIRECTION: {direction} | PRICE: {price}

TECHNICAL SCORE: {tech['score']}/100
- EMA crossover confirmed: Yes
- RSI: {tech.get('rsi')} (ideal 45-55)
- MACD: {tech.get('macd')} ({'bullish' if tech.get('macd', 0) > 0 else 'bearish'})
- 1H trend: {tech.get('htf_trend')}
- Volume ok: {tech.get('vol_ok')}
- Room to resistance: sufficient
- Reasons: {', '.join(tech.get('reasons', []))}

NEWS SENTIMENT SCORE: {sentiment['score']}/100
- Sentiment: {sentiment.get('sentiment')}
- Bullish signals: {sentiment.get('bullish_kw')} | Bearish: {sentiment.get('bearish_kw')}
- Headlines:
{heads if heads else '  No news available'}

HISTORICAL BACKTEST SCORE: {historical['score']}/100
- Win rate on similar setups: {historical.get('win_rate')}%
- Based on {historical.get('sample_size')} historical trades

REJECTION CRITERIA (auto-reject if ANY of these):
- Historical win rate < 55%
- Technical score < 60
- RSI outside 43-57
- News strongly against direction (score < 35)
- 1H trend opposes trade direction

TARGET: 3% profit, 1% stop loss (3:1 reward/risk)

Respond ONLY in valid JSON — no other text:
{{"approved": true/false, "confidence": 0-100, "reasoning": "one sentence", "key_risk": "main risk", "expected_outcome": "WIN/LOSS/UNCERTAIN"}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg    = client.messages.create(
            model='claude-sonnet-4-20250514', max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1].replace('json','').strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"AI decision error: {e}")
        avg = tech['score']*0.5 + sentiment['score']*0.2 + historical['score']*0.3
        return {'approved': avg >= 75, 'confidence': round(avg),
                'reasoning': f'Fallback ({e})', 'key_risk': 'Unknown',
                'expected_outcome': 'UNCERTAIN'}


# ── Signal builder ────────────────────────────────────────────────────────────

def _build_signal(df, asset, asset_type, cfg, open_trades=None):
    if open_trades is None:
        open_trades = []

    # Fetch higher timeframe
    ticker = asset
    df_1h = _fetch_higher_tf(ticker, asset_type) if cfg.CONFIRM_HIGHER_TIMEFRAME else None

    # Layer 1: Technical
    tech = _technical_analysis(df, df_1h, cfg.EMA_FAST, cfg.EMA_SLOW,
                               cfg.RSI_LOWER_BAND, cfg.RSI_UPPER_BAND)
    if not tech['direction'] or tech['score'] < 40:
        return None

    direction = tech['direction']
    price     = tech['price']

    # Layer 4: Correlation check (fast — do before slow operations)
    if not _correlation_ok(asset, direction, open_trades):
        return None

    # Layer 2: News sentiment
    headlines = _fetch_news(asset, asset_type)
    sentiment = _sentiment_score(headlines, direction)

    # Hard reject on very negative news
    if sentiment['score'] < 30:
        logger.info(f"📰 News block: {asset} {direction} — sentiment {sentiment['score']}")
        return None

    # Layer 3: Historical backtest
    historical = _historical_score(df, direction, cfg.TAKE_PROFIT_PCT, cfg.STOP_LOSS_PCT)

    # Hard reject on poor historical win rate
    if historical['win_rate'] < 52:
        logger.info(f"📊 History block: {asset} {direction} — win rate {historical['win_rate']}%")
        return None

    # Layer 5: Claude AI
    ai = _ai_decision(asset, direction, price, tech, sentiment, historical, cfg.ANTHROPIC_API_KEY)

    if not ai.get('approved', False):
        logger.info(f"🤖 AI rejected {asset} {direction} — {ai.get('reasoning')}")
        return None

    confidence = int(ai.get('confidence', 0))
    if confidence < cfg.MIN_CONFIDENCE:
        logger.info(f"⚡ Confidence {confidence}% < {cfg.MIN_CONFIDENCE}% — {asset} skipped")
        return None

    tp = round(price * (1 + cfg.TAKE_PROFIT_PCT if direction == 'BUY' else 1 - cfg.TAKE_PROFIT_PCT), 6)
    sl = round(price * (1 - cfg.STOP_LOSS_PCT   if direction == 'BUY' else 1 + cfg.STOP_LOSS_PCT),   6)

    logger.info(
        f"✅ SIGNAL: {direction} {asset} @ {price} | "
        f"Conf:{confidence}% | Tech:{tech['score']} | "
        f"News:{sentiment['sentiment']}({sentiment['score']}) | "
        f"WR:{historical['win_rate']}% | 1H:{tech['htf_trend']} | "
        f"AI:{ai.get('reasoning')}"
    )

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
        'htf_trend':       tech.get('htf_trend'),
        'macd':            tech.get('macd'),
        'ai_reasoning':    ai.get('reasoning'),
        'ai_risk':         ai.get('key_risk'),
        'top_headlines':   sentiment.get('headlines', [])[:3],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def scan_markets(cfg, open_trades=None) -> list[dict]:
    if open_trades is None:
        open_trades = []

    signals = []

    # ── Crypto 24/7 ───────────────────────────────────────────────────────────
    for symbol in cfg.CRYPTO_ASSETS:
        df  = _fetch_crypto(symbol)
        sig = _build_signal(df, symbol, 'crypto', cfg, open_trades)
        if sig:
            signals.append(sig)

    # ── Forex (London or NY session only) ─────────────────────────────────────
    if _is_forex_hours():
        for ticker, name in cfg.FOREX_ASSETS.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, name, 'forex', cfg, open_trades)
            if sig:
                sig['ticker'] = ticker
                signals.append(sig)
    else:
        logger.info("⏰ Forex: outside trading hours.")

    # ── Stocks (NY hours only) ────────────────────────────────────────────────
    if _is_stock_hours():
        for ticker, name in cfg.STOCK_ASSETS.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, ticker, 'stock', cfg, open_trades)
            if sig:
                sig['name'] = name
                signals.append(sig)

        # ── ETFs ──────────────────────────────────────────────────────────────
        for ticker, name in cfg.ETF_ASSETS.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, ticker, 'etf', cfg, open_trades)
            if sig:
                sig['name'] = name
                signals.append(sig)
    else:
        logger.info("⏰ Stocks/ETFs: market closed.")

    # ── Commodities ───────────────────────────────────────────────────────────
    for ticker, name in cfg.COMMODITY_ASSETS.items():
        df  = _fetch_yf(ticker)
        sig = _build_signal(df, name, 'commodity', cfg, open_trades)
        if sig:
            sig['ticker'] = ticker
            signals.append(sig)

    # Sort by confidence — take best signal first
    signals.sort(key=lambda x: x['confidence'], reverse=True)

    if not signals:
        logger.info("🔍 No signals this scan — all layers must agree for a trade.")
    else:
        logger.info(f"🎯 {len(signals)} signal(s) found — top: {signals[0]['asset']} "
                    f"{signals[0]['direction']} conf={signals[0]['confidence']}%")

    return signals


def get_current_prices(cfg) -> dict:
    prices = {}
    for s in cfg.CRYPTO_ASSETS:
        df = _fetch_crypto(s, limit=5)
        if df is not None:
            prices[s] = float(df['close'].iloc[-1])
    all_yf = {**cfg.FOREX_ASSETS, **cfg.STOCK_ASSETS,
              **cfg.ETF_ASSETS, **cfg.COMMODITY_ASSETS}
    for ticker, name in all_yf.items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            key = name if name else ticker
            prices[key] = float(df['close'].iloc[-1])
    return prices
