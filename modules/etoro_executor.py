"""
etoro_executor.py
------------------
Executes trades on eToro via their official API.
Works for ALL asset classes: crypto, stocks, commodities.

eToro API docs: https://api-portal.etoro.com/
Agent Portfolios: https://www.etoro.com/news-and-analysis/etoro-updates/agent-portfolios-let-your-ai-agent-trade-for-you/

Setup:
  1. Go to eToro → Settings → API Keys  (account must be verified)
  2. Create an "Agent Portfolio" — allocate your £500 to it
  3. Copy the scoped API key → set as ETORO_API_KEY in Render
"""
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

ETORO_BASE = 'https://api.etoro.com/v1'

# ── eToro instrument name map ─────────────────────────────────────────────────
# Maps our internal asset names → eToro instrument symbols
ETORO_INSTRUMENTS = {
    # Crypto
    'BTC/USDT':  'BTC',
    'ETH/USDT':  'ETH',
    # Stocks
    'AAPL':      'AAPL',
    'TSLA':      'TSLA',
    'NVDA':      'NVDA',
    'AMZN':      'AMZN',
    'META':      'META',
    'MSFT':      'MSFT',
    # Commodities
    'GOLD':      'XAUUSD',
    'SILVER':    'XAGUSD',
    'OIL':       'OIL',
}


def _headers(api_key: str) -> dict:
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type':  'application/json',
    }


def _etoro_instrument(asset: str) -> str:
    return ETORO_INSTRUMENTS.get(asset, asset)


# ── position sizing ───────────────────────────────────────────────────────────

def _position_size(capital: float, risk_pct: float,
                   entry: float, stop_loss: float) -> float:
    risk_amount = capital * risk_pct
    diff        = abs(entry - stop_loss)
    return round(risk_amount / diff, 6) if diff else 0.0


# ── public API ────────────────────────────────────────────────────────────────

def open_trade(signal: dict, capital: float, cfg) -> dict:
    """
    Opens a trade on eToro (or paper simulates it).
    Returns the trade dict.
    """
    entry   = signal['price']
    tp      = signal['take_profit']
    sl      = signal['stop_loss']
    pos_sz  = _position_size(capital, cfg.RISK_PER_TRADE_PCT, entry, sl)
    risk_£  = round(capital * cfg.RISK_PER_TRADE_PCT, 2)
    amount  = risk_£ * 10   # invest 10x risk amount (uses 1:10 leverage concept)

    trade = {
        'id':              datetime.utcnow().strftime('%Y%m%d%H%M%S'),
        'asset':           signal['asset'],
        'asset_type':      signal.get('asset_type', 'crypto'),
        'direction':       signal['direction'],
        'entry_price':     entry,
        'take_profit':     tp,
        'stop_loss':       sl,
        'position_size':   pos_sz,
        'risk_amount':     risk_£,
        'potential_profit': risk_£,
        'confidence':      signal['confidence'],
        'entry_time':      signal['timestamp'],
        'status':          'OPEN',
        'paper':           cfg.PAPER_TRADE,
        'broker':          'etoro',
        'capital_before':  round(capital, 2),
        'order_id':        None,
        'exit_price':      None,
        'exit_time':       None,
        'pnl':             None,
        'result':          None,
    }

    if cfg.PAPER_TRADE:
        trade['order_id'] = f"PAPER_{trade['id']}"
        logger.info(f"📝 [PAPER] {signal['direction']} {signal['asset']} @ {entry} "
                    f"| TP:{tp} SL:{sl} | Risk:£{risk_£}")
        return trade

    # ── Real eToro order ───────────────────────────────────────────────────────
    api_key    = cfg.ETORO_API_KEY
    instrument = _etoro_instrument(signal['asset'])
    action     = 'buy' if signal['direction'] == 'BUY' else 'sell'

    try:
        r = requests.post(
            f'{ETORO_BASE}/trading/positions',
            headers=_headers(api_key),
            json={
                'instrumentId':  instrument,
                'action':        action,
                'amount':        amount,         # USD amount to invest
                'takeProfit':    tp,
                'stopLoss':      sl,
                'leverageId':    1,              # 1 = no leverage (safest)
                'portfolioType': 'agent',        # uses Agent Portfolio
            },
            timeout=20
        )

        if r.ok:
            data              = r.json()
            trade['order_id'] = str(data.get('positionId', data.get('id', 'unknown')))
            trade['entry_price'] = float(data.get('openRate', entry))
            logger.info(f"✅ eToro order placed: {trade['order_id']} | {instrument} {action}")
        else:
            logger.error(f"❌ eToro order failed: {r.status_code} {r.text}")
            trade['status'] = 'FAILED'
            trade['error']  = r.text

    except Exception as exc:
        logger.error(f"❌ eToro exception: {exc}")
        trade['status'] = 'FAILED'
        trade['error']  = str(exc)

    return trade


def check_and_close(open_trades: list, current_prices: dict, cfg) -> tuple:
    """
    Checks open trades and closes any that hit TP or SL.
    Returns (updated_trades, newly_closed_trades).
    """
    updated, closed = [], []

    for t in open_trades:
        if t.get('status') != 'OPEN':
            updated.append(t)
            continue

        price = current_prices.get(t['asset'])
        if price is None:
            updated.append(t)
            continue

        hit_tp = (t['direction'] == 'BUY'  and price >= t['take_profit']) or \
                 (t['direction'] == 'SELL' and price <= t['take_profit'])
        hit_sl = (t['direction'] == 'BUY'  and price <= t['stop_loss'])  or \
                 (t['direction'] == 'SELL' and price >= t['stop_loss'])

        if hit_tp or hit_sl:
            result = 'WIN' if hit_tp else 'LOSS'
            pnl    = t['risk_amount'] if hit_tp else -t['risk_amount']

            # Close on eToro if live
            if not t.get('paper') and t.get('order_id') and cfg.ETORO_API_KEY:
                _close_etoro_position(t['order_id'], cfg)

            t.update({
                'status':    'CLOSED',
                'result':    result,
                'exit_price': round(price, 6),
                'exit_time': datetime.utcnow().isoformat(),
                'pnl':       round(pnl, 2),
                'pnl_pct':   round(pnl / t['capital_before'] * 100, 2),
            })
            closed.append(t)
            icon = '✅' if hit_tp else '❌'
            logger.info(f"{icon} Closed {t['asset']} | {result} | PnL:£{pnl:.2f}")

        updated.append(t)

    return updated, closed


def _close_etoro_position(position_id: str, cfg) -> bool:
    try:
        r = requests.delete(
            f'{ETORO_BASE}/trading/positions/{position_id}',
            headers=_headers(cfg.ETORO_API_KEY),
            timeout=15
        )
        if r.ok:
            logger.info(f"✅ eToro position {position_id} closed.")
            return True
        logger.error(f"eToro close failed: {r.text}")
        return False
    except Exception as e:
        logger.error(f"eToro close exception: {e}")
        return False


def get_portfolio_balance(cfg) -> float | None:
    """Fetch current Agent Portfolio balance from eToro."""
    if cfg.PAPER_TRADE or not cfg.ETORO_API_KEY:
        return None
    try:
        r = requests.get(
            f'{ETORO_BASE}/accounts/portfolio',
            headers=_headers(cfg.ETORO_API_KEY),
            params={'portfolioType': 'agent'},
            timeout=15
        )
        if r.ok:
            data = r.json()
            return float(data.get('availableBalance', data.get('balance', 0)))
    except Exception as e:
        logger.error(f"eToro balance fetch error: {e}")
    return None
