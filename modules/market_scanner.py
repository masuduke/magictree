"""
market_scanner.py v5 — 4 Strategies × 27 Assets
--------------------------------------------------
What changed vs v4:
- 4 strategies: EMA, Bollinger Band, RSI Reversal, Momentum
- 27 assets: +6 forex pairs +2 crypto (DOGE, AVAX)
- Weighted AI scoring (not all-or-nothing)
- Market regime detection
- ATR volatility filter
- Forex prioritised (best path to £25/day)
"""
import logging, json, re, requests
import pandas as pd
from datetime import datetime
from modules import asset_config, strategies

logger = logging.getLogger(__name__)

BULLISH_KW = ['surge','rally','breakout','bullish','upgrade','record','growth',
              'buy','beat','above','positive','rise','jump','gain','strong']
BEARISH_KW = ['crash','collapse','ban','recession','selloff','plunge','warning',
              'fear','dump','bearish','downgrade','loss','drop','weak','miss']


# ── Session helpers ───────────────────────────────────────────────────────────

def _is_forex_hours(cfg):
    now = datetime.utcnow()
    return now.weekday() < 5 and cfg.LONDON_OPEN <= now.hour < cfg.NY_CLOSE

def _is_stock_hours(cfg):
    now = datetime.utcnow()
    return now.weekday() < 5 and cfg.NY_OPEN <= now.hour < cfg.NY_CLOSE

def _is_overlap(cfg):
    """London/NY overlap — best forex session."""
    now = datetime.utcnow()
    return now.weekday() < 5 and cfg.NY_OPEN <= now.hour < cfg.LONDON_CLOSE


# ── Data fetchers ─────────────────────────────────────────────────────────────

def _fetch_yf(ticker, period='5d', interval='15m', limit=200):
    try:
        import yfinance as yf, socket
        socket.setdefaulttimeout(8)
        raw = yf.download(ticker, period=period, interval=interval,
                          progress=False, auto_adjust=True, timeout=8)
        if raw.empty:
            return None
        df = raw.reset_index()
        df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in df.columns]
        df = df.rename(columns={'Datetime':'ts','Date':'ts','Open':'open',
                                'High':'high','Low':'low','Close':'close','Volume':'vol'})
        cols = [c for c in ['ts','open','high','low','close','vol'] if c in df.columns]
        return df[cols].dropna().tail(limit)
    except Exception as e:
        logger.debug(f"yfinance ({ticker}): {e}")
        return None

def _fetch_crypto(symbol):
    yf_map = {
        'BTC/USDT':'BTC-USD','ETH/USDT':'ETH-USD',
        'SOL/USDT':'SOL-USD','BNB/USDT':'BNB-USD',
        'DOGE/USDT':'DOGE-USD','AVAX/USDT':'AVAX-USD',
    }
    return _fetch_yf(yf_map.get(symbol, symbol.replace('/USDT','-USD')))


# ── News sentiment ────────────────────────────────────────────────────────────

def _fetch_news(asset):
    headlines = []
    try:
        ticker = asset.split('/')[0].replace('=X','').replace('=F','').replace('USDT','')
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        r = requests.get(url, timeout=6)
        if r.ok:
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', r.text)
            headlines.extend([t for t in titles if len(t) > 10][:8])
    except Exception:
        pass
    return headlines


def _sentiment(headlines, direction):
    if not headlines:
        return 50
    text = ' '.join(headlines).lower()
    bull = sum(text.count(k) for k in BULLISH_KW)
    bear = sum(text.count(k) for k in BEARISH_KW)
    total = bull + bear
    raw = (bull / total * 100) if total > 0 else 50
    return round(raw if direction == 'BUY' else (100 - raw), 1)


# ── Historical win rate ───────────────────────────────────────────────────────

def _historical_wr(df, direction, tp_pct, sl_pct):
    if df is None or len(df) < 80:
        return 50
    close = df['close'].astype(float)
    ef = close.ewm(span=9,adjust=False).mean()
    es = close.ewm(span=21,adjust=False).mean()
    wins = total = 0
    for i in range(25, len(df)-10):
        cf,pf = float(ef.iloc[i]),float(ef.iloc[i-1])
        cs,ps = float(es.iloc[i]),float(es.iloc[i-1])
        p = float(close.iloc[i])
        is_buy  = direction=='BUY'  and pf<=ps and cf>cs
        is_sell = direction=='SELL' and pf>=ps and cf<cs
        if is_buy or is_sell:
            tp = p*(1+tp_pct) if is_buy else p*(1-tp_pct)
            sl = p*(1-sl_pct) if is_buy else p*(1+sl_pct)
            for fp in close.iloc[i+1:i+10].values:
                if (is_buy and fp>=tp) or (is_sell and fp<=tp):
                    wins+=1; total+=1; break
                elif (is_buy and fp<=sl) or (is_sell and fp>=sl):
                    total+=1; break
    return round(wins/total*100,1) if total>0 else 50


# ── AI decision ───────────────────────────────────────────────────────────────

def _ai_decision(asset, direction, price, strat_sig,
                 sentiment_score, hist_wr, asset_type, api_key):
    if not api_key:
        score = strat_sig['score']*0.5 + sentiment_score*0.2 + hist_wr*0.3
        return {'approved': score>=62, 'confidence': round(score),
                'reasoning': 'Weighted avg (no API)', 'key_risk': 'Unknown'}

    heads = _fetch_news(asset)
    headlines_text = '\n'.join(f'  • {h}' for h in heads[:4]) or '  No news'

    prompt = f"""Professional trader analysis. Be decisive — this system needs trades to work.

ASSET: {asset} ({asset_type}) | {direction} | ${price}
STRATEGY: {strat_sig['strategy']} (score {strat_sig['score']}/100)
SIGNALS: {', '.join(strat_sig.get('reasons',[]))}
RSI: {strat_sig.get('rsi','N/A')} | Vol ratio: {strat_sig.get('vol_ratio','N/A')}

NEWS SENTIMENT: {sentiment_score}/100
{headlines_text}

HISTORICAL WIN RATE: {hist_wr}% on similar setups

RULES:
- Approve if total weighted score >= 62
- Reject ONLY if: hist_wr < 45% OR news strongly against (score<30) OR strategy score < 50
- Be willing to trade on moderate confidence — waiting for perfection = no trades = no profit

Respond ONLY in JSON:
{{"approved": true/false, "confidence": 0-100, "reasoning": "brief", "key_risk": "main risk"}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-sonnet-4-20250514', max_tokens=150,
            messages=[{'role':'user','content':prompt}]
        )
        raw = msg.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1].replace('json','').strip()
        return json.loads(raw)
    except Exception as e:
        score = strat_sig['score']*0.5 + sentiment_score*0.2 + hist_wr*0.3
        return {'approved': score>=62, 'confidence': round(score),
                'reasoning': f'Fallback: {e}', 'key_risk': 'Unknown'}


# ── Correlation check ─────────────────────────────────────────────────────────

def _correlation_ok(asset, direction, open_trades):
    corr = {
        'BTC/USDT':['ETH/USDT','SOL/USDT','BNB/USDT','DOGE/USDT','AVAX/USDT'],
        'ETH/USDT':['BTC/USDT','SOL/USDT'],
        'SOL/USDT':['BTC/USDT','ETH/USDT'],
        'DOGE/USDT':['BTC/USDT','AVAX/USDT'],
        'EUR/USD':['GBP/USD','AUD/USD','EUR/GBP'],
        'GBP/USD':['EUR/USD','EUR/GBP'],
        'GOLD':['GLD','GC=F'],
        'SPY':['QQQ'],
    }
    for t in open_trades:
        if t.get('asset') in corr.get(asset,[]) and t.get('direction')==direction:
            return False
    return True


# ── Main signal builder ───────────────────────────────────────────────────────

def _build_signal(df, asset, asset_type, cfg, open_trades, market_regime="NEUTRAL"):
    if df is None or len(df) < 30:
        return None

    # Run all strategies, get best signal
    sig = strategies.best_signal(df, asset_type, market_regime)
    if not sig or sig['score'] < cfg.MIN_STRATEGY_SCORE:
        return None

    direction = sig['direction']
    price     = sig['price']

    # Correlation check
    if not _correlation_ok(asset, direction, open_trades):
        logger.debug(f"Correlation block: {asset}")
        return None

    # Get asset-specific settings
    tp_pct = asset_config.get_tp(asset)
    sl_pct = asset_config.get_sl(asset)

    # Sentiment
    heads = _fetch_news(asset)
    sent_score = _sentiment(heads, direction)
    if sent_score < 25:
        logger.info(f"News block: {asset} {direction} (sentiment {sent_score})")
        return None

    # Historical
    hist_wr = _historical_wr(df, direction, tp_pct, sl_pct)
    if hist_wr < 45:
        logger.info(f"History block: {asset} {direction} (WR {hist_wr}%)")
        return None

    # AI decision
    ai = _ai_decision(asset, direction, price, sig, sent_score,
                      hist_wr, asset_type, cfg.ANTHROPIC_API_KEY)

    if not ai.get('approved', False):
        logger.info(f"AI rejected: {asset} {direction} — {ai.get('reasoning','')}")
        return None

    confidence = int(ai.get('confidence', 0))
    if confidence < cfg.MIN_CONFIDENCE:
        logger.info(f"Low confidence {confidence}% < {cfg.MIN_CONFIDENCE}%: {asset}")
        return None

    tp = round(price*(1+tp_pct if direction=='BUY' else 1-tp_pct), 6)
    sl = round(price*(1-sl_pct if direction=='BUY' else 1+sl_pct), 6)

    exp_profit = asset_config.expected_profit(asset, cfg.INITIAL_CAPITAL)
    max_loss   = asset_config.max_loss(asset, cfg.INITIAL_CAPITAL)

    logger.info(
        f"SIGNAL: {sig['strategy']} {direction} {asset} @ {price} | "
        f"Conf:{confidence}% | Strat:{sig['score']} | "
        f"News:{sent_score} | WR:{hist_wr}% | "
        f"ExpProfit:£{exp_profit} MaxLoss:£{max_loss} | "
        f"{ai.get('reasoning','')}"
    )

    return {
        'asset':          asset,
        'asset_type':     asset_type,
        'strategy':       sig['strategy'],
        'direction':      direction,
        'price':          round(price, 6),
        'take_profit':    tp,
        'stop_loss':      sl,
        'confidence':     confidence,
        'timestamp':      datetime.utcnow().isoformat(),
        'rsi':            sig.get('rsi'),
        'strategy_score': sig['score'],
        'sentiment_score':sent_score,
        'historical_wr':  hist_wr,
        'tp_pct':         tp_pct,
        'sl_pct':         sl_pct,
        'max_hours':      asset_config.get_max_hours(asset),
        'leverage':       asset_config.get_leverage(asset),
        'asset_label':    asset_config.get_label(asset),
        'asset_emoji':    asset_config.get_emoji(asset),
        'expected_profit':exp_profit,
        'max_loss':       max_loss,
        'ai_reasoning':   ai.get('reasoning',''),
        'ai_risk':        ai.get('key_risk',''),
        'strategy_reasons': sig.get('reasons', []),
        'headlines':      heads[:3],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def scan_markets(cfg, open_trades=None):
    if open_trades is None:
        open_trades = []

    signals = []
    in_overlap = _is_overlap(cfg)

    # ── Crypto (24/7) ─────────────────────────────────────────────────────────
    # Detect overall crypto market regime using BTC trend
    btc_df = _fetch_yf('BTC-USD', period='30d', interval='1h', limit=200)
    market_regime = strategies.get_market_regime(btc_df)
    logger.info(f'Market regime: {market_regime}')

    for internal, yf_ticker in cfg.CRYPTO_ASSETS.items():
        df = _fetch_yf(yf_ticker)
        s  = _build_signal(df, internal, 'crypto', cfg, open_trades, market_regime)
        if s: signals.append(s)

    # ── Forex (London+NY) — HIGHEST PRIORITY ──────────────────────────────────
    if _is_forex_hours(cfg):
        for yf_ticker, name in cfg.FOREX_ASSETS.items():
            df = _fetch_yf(yf_ticker)
            s  = _build_signal(df, name, 'forex', cfg, open_trades)
            if s:
                s['is_overlap'] = in_overlap
                if in_overlap:
                    s['confidence'] = min(s['confidence'] + 5, 100)
                signals.append(s)
    else:
        logger.info("Forex: outside trading hours")

    # ── Stocks + ETFs (NY hours) ───────────────────────────────────────────────
    if _is_stock_hours(cfg):
        for ticker, name in {**cfg.STOCK_ASSETS, **cfg.ETF_ASSETS}.items():
            df = _fetch_yf(ticker)
            s  = _build_signal(df, ticker, 'stock' if ticker in cfg.STOCK_ASSETS else 'etf', cfg, open_trades)
            if s:
                s['name'] = name
                signals.append(s)
    else:
        logger.info("Stocks/ETFs: market closed")

    # -- Commodities
    for ticker, name in cfg.COMMODITY_ASSETS.items():
        df = _fetch_yf(ticker, period="5d", interval="15m", limit=200)
        if df is None or df.empty:
            df = _fetch_yf(ticker, period="1mo", interval="1h", limit=200)
        if df is None or df.empty:
            if "GC" in ticker:
                df = _fetch_yf("GLD", period="5d", interval="15m", limit=200)
                logger.info("Using GLD as Gold fallback")
            elif "SI" in ticker:
                df = _fetch_yf("SLV", period="5d", interval="15m", limit=200)
                logger.info("Using SLV as Silver fallback")
        s = _build_signal(df, name, "commodity", cfg, open_trades)
        if s: signals.append(s)
    # Sort: forex overlap first, then by confidence
    signals.sort(key=lambda x: (-x.get('is_overlap',0), -x['confidence']))

    if not signals:
        logger.info("No signals — all strategies checked, waiting for right conditions")
    else:
        top = signals[0]
        logger.info(
            f"{len(signals)} signal(s) found | "
            f"Best: {top['strategy']} {top['direction']} {top['asset']} "
            f"conf={top['confidence']}% exp=£{top.get('expected_profit',0)}"
        )

    return signals


def get_current_prices(cfg):
    prices = {}
    # Detect overall crypto market regime using BTC trend
    btc_df = _fetch_yf('BTC-USD', period='30d', interval='1h', limit=200)
    market_regime = strategies.get_market_regime(btc_df)
    logger.info(f'Market regime: {market_regime}')

    for internal, yf_ticker in cfg.CRYPTO_ASSETS.items():
        df = _fetch_yf(yf_ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[internal] = float(df['close'].iloc[-1])
    for ticker, name in {**cfg.FOREX_ASSETS, **cfg.STOCK_ASSETS,
                         **cfg.ETF_ASSETS, **cfg.COMMODITY_ASSETS}.items():
        df = _fetch_yf(ticker, period='1d', interval='5m', limit=5)
        if df is not None and not df.empty:
            prices[name] = float(df['close'].iloc[-1])
    return prices
