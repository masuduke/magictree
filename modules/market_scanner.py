"""
market_scanner.py v6.1 - Phase 1.5: Backtest matches live signal
-----------------------------------------------------------------
Fixes from v6:
  - FIX 13: _historical_score() now counts both fresh-cross AND trend-continuation
    setups, matching the Phase 1 live signal logic. Previously the backtest only
    looked for fresh crossovers, so any live trend_continue signal had zero
    matching historical samples -> AI auto-rejected for 'sample_size = 0'.
    Also added the price > 50EMA / price < 50EMA filter to backtest, matching live.
  - FIX 14: Backtest forward simulation window extended from 12 to 32 bars (8h on 15m
    bars). 12 bars was 3h - shorter than any real trade max_hours, so most setups
    never resolved in window and were silently dropped. Also: setups that still
    don't resolve within 32 bars are now counted as TIME-stop closes (won/lost based
    on direction of move at end of window) instead of being dropped entirely.
  - FIX 15: Min sample threshold lowered from 10 to 5. Empirical testing showed
    only ~15% of 200-bar windows reach 10 samples even with FIX 13/14 - too tight
    given live data is 200 bars. AI prompt also updated to match.
"""
import logging
import json
import re
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
    return now.weekday() < 5 and FOREX_OPEN_HOUR <= now.hour <= FOREX_CLOSE_HOUR


def _is_forex_asset(asset):
    return '/' in asset and 'USDT' not in asset and '/USDT' not in asset


# -- Regime detection ---------------------------------------------------------

def _compute_regime(df):
    """Return 'bull', 'bear', or 'neutral' based on 50/200 EMA + price."""
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
    df = _fetch_daily_yf('DX-Y.NYB', period='400d')
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


def _regime_allows(direction, regime, asset=None, asset_type=None):
    """Reject counter-trend trades.
    Forex: regime tracks DXY (USD strength). Pair direction depends on whether
    USD is base or quote. Crypto/stocks/commodities: regime tracks the asset itself.
    """
    if regime == 'neutral':
        return True

    if asset_type == 'forex' and asset and '/' in asset:
        base, quote = asset.split('/', 1)
        usd_is_quote = (quote.upper() == 'USD')
        usd_is_base  = (base.upper() == 'USD')

        if usd_is_quote:
            # XXX/USD: pair UP when USD DOWN
            if regime == 'bull' and direction == 'BUY':  return False
            if regime == 'bear' and direction == 'SELL': return False
            return True
        if usd_is_base:
            # USD/XXX: pair UP when USD UP
            if regime == 'bull' and direction == 'SELL': return False
            if regime == 'bear' and direction == 'BUY':  return False
            return True
        return True  # Cross pair, no USD - allow either

    # Crypto / stocks / commodities
    if regime == 'bull' and direction == 'SELL': return False
    if regime == 'bear' and direction == 'BUY':  return False
    return True


# -- Volume (skips forex) -----------------------------------------------------

def _volume_ratio(df, asset):
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
        return {'score': 0, 'direction': None, 'diag': None}

    close = df['close'].astype(float)
    ef    = _ema(close, ema_f)
    es    = _ema(close, ema_s)
    e50   = _ema(close, 50)
    rsi   = _rsi(close)

    cf, pf   = ef.iloc[-1], ef.iloc[-2]
    cs, ps   = es.iloc[-1], es.iloc[-2]
    cur_rsi  = float(rsi.iloc[-1])
    price    = float(close.iloc[-1])
    e50_val  = float(e50.iloc[-1])
    ema_sep  = abs(cf - cs) / cs * 100

    vol_ratio = _volume_ratio(df, asset)
    vol_ok    = vol_ratio > 0.8

    # Fresh crossover on the current bar (high-confirmation entry)
    cross_up   = bool(pf <= ps and cf > cs)
    cross_down = bool(pf >= ps and cf < cs)

    # PHASE 1 (FIX 12): Trend-continuation entry.
    # If fast > slow now AND a crossover happened within the last LOOKBACK bars,
    # we're allowed to join an in-progress trend. Lower base score than fresh cross.
    # Without this, we miss every move where the crossover bar isn't the current one.
    LOOKBACK = 5  # bars - keep small so we only join JUST-started trends
    fast_above_now = bool(cf > cs)
    fast_below_now = bool(cf < cs)
    recent_cross_up   = False
    recent_cross_down = False
    if len(ef) >= LOOKBACK + 2 and not (cross_up or cross_down):
        # Skip the current bar (already covered by cross_up/cross_down above)
        # Walk backwards across the last LOOKBACK bars looking for a flip.
        for i in range(2, LOOKBACK + 2):
            f_now,  s_now  = ef.iloc[-(i - 1)], es.iloc[-(i - 1)]
            f_prev, s_prev = ef.iloc[-i],       es.iloc[-i]
            if f_prev <= s_prev and f_now > s_now and fast_above_now:
                recent_cross_up = True
                break
            if f_prev >= s_prev and f_now < s_now and fast_below_now:
                recent_cross_down = True
                break

    rsi_ok   = bool(rsi_lo <= cur_rsi <= rsi_hi)
    above_50 = bool(price > e50_val)

    direction = None
    score     = 0
    reasons   = []
    entry_kind = None  # 'fresh_cross' or 'trend_continue'

    # BUY: fresh crossover gets full score; trend-continuation gets lower base
    if cross_up and rsi_ok and above_50:
        direction = 'BUY'; entry_kind = 'fresh_cross'
        score += 40; reasons.append('EMA bullish crossover (fresh)')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price above 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    elif recent_cross_up and rsi_ok and above_50:
        direction = 'BUY'; entry_kind = 'trend_continue'
        score += 30; reasons.append('Trend continuation (cross in last 5 bars)')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price above 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    elif cross_down and rsi_ok and not above_50:
        direction = 'SELL'; entry_kind = 'fresh_cross'
        score += 40; reasons.append('EMA bearish crossover (fresh)')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price below 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    elif recent_cross_down and rsi_ok and not above_50:
        direction = 'SELL'; entry_kind = 'trend_continue'
        score += 30; reasons.append('Trend continuation (cross in last 5 bars)')
        score += 20; reasons.append(f'RSI {cur_rsi:.1f} in range')
        score += 20; reasons.append('Price below 50 EMA')
        if vol_ok:
            score += 15; reasons.append(f'Volume {vol_ratio:.2f}x')
        if ema_sep > 0.3:
            score += 5; reasons.append(f'EMA sep {ema_sep:.2f}%')

    diag = {
        'cross_up':          cross_up,
        'cross_down':        cross_down,
        'recent_cross_up':   recent_cross_up,
        'recent_cross_down': recent_cross_down,
        'rsi_ok':            rsi_ok,
        'above_50':          above_50,
        'fast_above':        fast_above_now,
        'entry_kind':        entry_kind,
    }

    return {
        'score':     min(score, 100),
        'direction': direction,
        'price':     price,
        'rsi':       round(cur_rsi, 2),
        'ema_sep':   round(ema_sep, 3),
        'reasons':   reasons,
        'diag':      diag,
        'entry_kind': entry_kind,
    }


# -- LAYER 2: News Sentiment --------------------------------------------------

def _fetch_news(asset, asset_type):
    headlines = []
    try:
        ticker = asset.split('/')[0] if '/' in asset else asset
        url = (f"https://feeds.finance.yahoo.com/rss/2.0/headline"
               f"?s={ticker}&region=US&lang=en-US")
        r = requests.get(url, timeout=8)
        if r.ok:
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
    raw = (bull / total * 100) if total > 0 else 50
    sent = 'bullish' if raw > 60 else 'bearish' if raw < 40 else 'neutral'
    score = raw if direction == 'BUY' else (100 - raw)
    return {
        'score':      round(score, 1),
        'sentiment':  sent,
        'bullish_kw': bull,
        'bearish_kw': bear,
        'headlines':  headlines[:5],
    }


# -- LAYER 3: Historical Backtest --------------------------------------------

def _historical_score(df, direction, tp_pct=0.02, sl_pct=0.01):
    """Backtest looks at past setups identical to live entry logic.
    PHASE 1.5 (FIX 13): Count BOTH fresh-cross AND trend-continuation setups.
    PHASE 1.5 (FIX 14): Forward window extended from 12 to 32 bars (8h on 15m bars)
        to match real-world trade time horizons. With 12 bars, ~50% of valid setups
        never resolved within window and were silently dropped.
    """
    if df is None or len(df) < 100:
        return {'score': 50, 'win_rate': 50, 'sample_size': 0}

    FORWARD_BARS = 32  # 8 hours on 15m timeframe; covers forex max_hours
    LOOKBACK     = 5

    close = df['close'].astype(float)
    e9    = _ema(close, 9)
    e21   = _ema(close, 21)
    e50   = _ema(close, 50)
    rsi_s = _rsi(close)
    wins  = 0
    total = 0
    fresh_count    = 0
    continue_count = 0

    for i in range(30, len(df) - FORWARD_BARS):
        cf, pf = float(e9.iloc[i]),  float(e9.iloc[i-1])
        cs, ps = float(e21.iloc[i]), float(e21.iloc[i-1])
        e50v   = float(e50.iloc[i])
        r      = float(rsi_s.iloc[i])
        p      = float(close.iloc[i])

        if not (40 <= r <= 60):
            continue

        fresh_cross_up   = pf <= ps and cf > cs
        fresh_cross_down = pf >= ps and cf < cs

        recent_cross_up   = False
        recent_cross_down = False
        fast_above = cf > cs
        fast_below = cf < cs
        if not (fresh_cross_up or fresh_cross_down) and i >= LOOKBACK + 2:
            for k in range(2, LOOKBACK + 2):
                f_now,  s_now  = float(e9.iloc[i-(k-1)]),  float(e21.iloc[i-(k-1)])
                f_prev, s_prev = float(e9.iloc[i-k]),     float(e21.iloc[i-k])
                if f_prev <= s_prev and f_now > s_now and fast_above:
                    recent_cross_up = True
                    break
                if f_prev >= s_prev and f_now < s_now and fast_below:
                    recent_cross_down = True
                    break

        above_50 = p > e50v

        setup_buy = direction == 'BUY' and above_50 and (
            fresh_cross_up or recent_cross_up
        )
        setup_sell = direction == 'SELL' and not above_50 and (
            fresh_cross_down or recent_cross_down
        )

        if not (setup_buy or setup_sell):
            continue

        if setup_buy:
            if fresh_cross_up:   fresh_count += 1
            else:                continue_count += 1
        else:
            if fresh_cross_down: fresh_count += 1
            else:                continue_count += 1

        # Simulate forward to see if TP or SL hits first
        tp = p * (1 + tp_pct) if setup_buy else p * (1 - tp_pct)
        sl = p * (1 - sl_pct) if setup_buy else p * (1 + sl_pct)
        future = close.iloc[i+1:i+1+FORWARD_BARS].values
        resolved = False
        for fp in future:
            if (setup_buy and fp >= tp) or (setup_sell and fp <= tp):
                wins  += 1
                total += 1
                resolved = True
                break
            elif (setup_buy and fp <= sl) or (setup_sell and fp >= sl):
                total += 1
                resolved = True
                break
        # If never resolved within window, count as a TIME-stop close at last price.
        # Treat as win if last price favourable, loss otherwise. Don't drop the sample.
        if not resolved and len(future) > 0:
            last = float(future[-1])
            move = (last - p) if setup_buy else (p - last)
            total += 1
            if move > 0:
                wins += 1

    if total < 5:
        return {'score': 50, 'win_rate': 50, 'sample_size': total,
                'fresh_count': fresh_count, 'continue_count': continue_count}

    win_rate = round(wins / total * 100, 1)
    return {
        'score':          win_rate,
        'win_rate':       win_rate,
        'sample_size':    total,
        'fresh_count':    fresh_count,
        'continue_count': continue_count,
    }


# -- LAYER 4: Claude AI Decision ---------------------------------------------

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
- Historical sample_size < 5 (not enough data to trust)
- Historical win rate below 55%
- News sentiment opposes direction
- Technical score below 65
- Market regime opposes direction (bull regime + SELL, or bear regime + BUY)
- RSI outside 40-60

Only APPROVE if ALL of these are true:
- sample_size >= 5 AND win_rate >= 58%
- Technical score >= 65
- News sentiment neutral or supportive
- Regime is neutral OR aligned with direction
- You can articulate a specific edge in one sentence

Respond ONLY in valid JSON:
{{"approved": true/false, "confidence": 0-100, "reasoning": "brief reason", "key_risk": "main risk", "expected_outcome": "WIN/LOSS/UNCERTAIN"}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
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
        return {'approved': False, 'confidence': 0,
                'reasoning': f'AI error - rejected for safety ({e})',
                'key_risk': 'Unknown', 'expected_outcome': 'UNCERTAIN'}


# -- Signal builder -----------------------------------------------------------

def _build_signal(df, asset, asset_type, cfg):
    # Regime by asset class
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

    # Diagnostic: log why no signal fired
    if not tech.get('direction'):
        d = tech.get('diag') or {}
        if d:
            # Decide what the most informative description is
            bits = []
            if d.get('cross_up'):
                bits.append('fresh cross up')
            elif d.get('cross_down'):
                bits.append('fresh cross down')
            elif d.get('recent_cross_up'):
                bits.append('recent cross up')
            elif d.get('recent_cross_down'):
                bits.append('recent cross down')
            elif d.get('fast_above'):
                bits.append('trend up but no recent cross')
            else:
                bits.append('no trend')

            if not d.get('rsi_ok'):
                bits.append(f'RSI {tech.get("rsi")} out of band')
            if (d.get('cross_up') or d.get('recent_cross_up')) and not d.get('above_50'):
                bits.append('price below 50EMA')
            if (d.get('cross_down') or d.get('recent_cross_down')) and d.get('above_50'):
                bits.append('price above 50EMA')

            logger.info(f"  [{asset}] no signal - RSI {tech.get('rsi')}, "
                        f"sep {tech.get('ema_sep')}% | {', '.join(bits)}")
        return None

    if tech['score'] < 40:
        logger.info(f"  [{asset}] weak signal - score {tech['score']} < 40")
        return None

    direction = tech['direction']
    price     = tech['price']

    # Regime check
    if not _regime_allows(direction, regime, asset=asset, asset_type=asset_type):
        logger.info(f"  [{asset}] regime blocked: {direction} ({regime} regime)")
        return None

    # Per-asset settings - this is the SINGLE SOURCE OF TRUTH
    settings = asset_config.get(asset)
    tp_pct    = settings['tp']
    sl_pct    = settings['sl']
    leverage  = settings['leverage']
    max_hours = settings['max_hours']
    label     = settings['label']
    emoji     = settings['emoji']

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

    tp = round(price * ((1 + tp_pct) if direction == 'BUY' else (1 - tp_pct)), 6)
    sl = round(price * ((1 - sl_pct) if direction == 'BUY' else (1 + sl_pct)), 6)

    # Expected profit (paper) for log/banner
    expected_profit = round(cfg.INITIAL_CAPITAL * tp_pct * leverage, 2)
    expected_loss   = round(cfg.INITIAL_CAPITAL * sl_pct * leverage, 2)

    entry_kind = tech.get('entry_kind', 'unknown')

    logger.info(f"SIGNAL APPROVED: {direction} {asset} @ {price} | "
                f"Entry:{entry_kind} | Conf:{confidence}% | Tech:{tech['score']} | "
                f"Regime:{regime} | News:{sentiment['sentiment']} | "
                f"HistWR:{historical['win_rate']}% ({historical['sample_size']}) | "
                f"TP:{tp_pct*100:.2f}% SL:{sl_pct*100:.2f}% | Lev:{leverage}x | "
                f"ExpWin GBP{expected_profit} | "
                f"{ai.get('reasoning')}")

    return {
        # identifiers
        'asset':           asset,
        'asset_type':      asset_type,
        'asset_label':     label,
        'asset_emoji':     emoji,
        'strategy':        f'EMA_TREND_{entry_kind.upper()}',
        'entry_kind':      entry_kind,

        # trade params (executor reads these directly)
        'direction':       direction,
        'price':           round(price, 6),
        'take_profit':     tp,
        'stop_loss':       sl,
        'tp_pct':          tp_pct,
        'sl_pct':          sl_pct,
        'leverage':        leverage,
        'max_hours':       max_hours,

        # signal quality
        'confidence':      confidence,
        'tech_score':      tech['score'],
        'sentiment_score': sentiment['score'],
        'sentiment':       sentiment.get('sentiment'),
        'historical_wr':   historical.get('win_rate'),
        'sample_size':     historical.get('sample_size'),
        'regime':          regime,
        'rsi':             tech.get('rsi'),
        'ai_reasoning':    ai.get('reasoning'),
        'ai_risk':         ai.get('key_risk'),
        'top_headlines':   sentiment.get('headlines', [])[:3],

        # bookkeeping
        'timestamp':       datetime.utcnow().isoformat(),
        'expected_profit': expected_profit,
        'expected_loss':   expected_loss,
    }


# -- Public API ---------------------------------------------------------------

def scan_markets(cfg, open_trades=None):
    _regime_cache.clear()
    signals = []

    # Crypto - 24/7
    crypto_assets = getattr(cfg, 'CRYPTO_ASSETS', {})
    for symbol, yf_ticker in crypto_assets.items():
        df  = _fetch_crypto_yf(yf_ticker)
        sig = _build_signal(df, symbol, 'crypto', cfg)
        if sig:
            sig['ticker'] = yf_ticker
            signals.append(sig)

    # Forex - session hours
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

    # Stocks - NYSE hours
    if _is_stock_hours():
        stock_assets = getattr(cfg, 'STOCK_ASSETS', {})
        for ticker, name in stock_assets.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, ticker, 'stock', cfg)
            if sig:
                sig['display_name'] = name
                signals.append(sig)

        # ETFs - same hours and treatment as stocks (FIX: was never scanned)
        etf_assets = getattr(cfg, 'ETF_ASSETS', {})
        for ticker, name in etf_assets.items():
            df  = _fetch_yf(ticker)
            sig = _build_signal(df, ticker, 'stock', cfg)
            if sig:
                sig['display_name'] = name
                signals.append(sig)
    else:
        logger.info("Stock/ETF market closed.")

    # Commodities (use commodity name as asset key, matches asset_config)
    commodity_assets = getattr(cfg, 'COMMODITY_ASSETS', {})
    for ticker, name in commodity_assets.items():
        df  = _fetch_yf(ticker)
        sig = _build_signal(df, name, 'commodity', cfg)
        if sig:
            sig['ticker'] = ticker
            signals.append(sig)

    if not signals:
        logger.info("No high-quality signals - waiting for perfect setup.")
    return signals


# -- Data fetchers ------------------------------------------------------------

def _fetch_crypto_yf(yf_ticker, period='5d', interval='15m', limit=200):
    """FIX: yfinance for crypto (binance was IP-banned on Render)."""
    return _fetch_yf(yf_ticker, period=period, interval=interval, limit=limit)


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
        return df[cols].dropna().tail(limit)
    except Exception as e:
        logger.error(f"yfinance ({ticker}): {e}")
        return None


def _fetch_daily_yf(ticker, period='400d'):
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


# -- Price lookup for open trades --------------------------------------------
# CRITICAL: keys MUST match what is stored in trade['asset']
#   crypto    -> 'BTC/USDT'  (the symbol from CRYPTO_ASSETS keys)
#   forex     -> 'EUR/USD'   (the name from FOREX_ASSETS values)
#   stocks    -> 'NVDA'      (the ticker from STOCK_ASSETS keys)
#   ETFs      -> 'SPY'       (the ticker from ETF_ASSETS keys)
#   commodity -> 'GOLD'      (the name from COMMODITY_ASSETS values)

def get_current_prices(cfg):
    prices = {}

    # Crypto: store under symbol like 'BTC/USDT'
    for symbol, yf_ticker in getattr(cfg, 'CRYPTO_ASSETS', {}).items():
        df = _fetch_crypto_yf(yf_ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[symbol] = float(df['close'].iloc[-1])

    # Forex: store under name like 'EUR/USD'
    for ticker, name in getattr(cfg, 'FOREX_ASSETS', {}).items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[name] = float(df['close'].iloc[-1])

    # Stocks: store under ticker like 'NVDA' (FIX: was storing under company name)
    for ticker, name in getattr(cfg, 'STOCK_ASSETS', {}).items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[ticker] = float(df['close'].iloc[-1])

    # ETFs: store under ticker like 'SPY' (FIX: was not fetched at all)
    for ticker, name in getattr(cfg, 'ETF_ASSETS', {}).items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[ticker] = float(df['close'].iloc[-1])

    # Commodities: store under name like 'GOLD'
    for ticker, name in getattr(cfg, 'COMMODITY_ASSETS', {}).items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[name] = float(df['close'].iloc[-1])

    return prices
