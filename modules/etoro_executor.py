"""
etoro_executor.py
------------------
Executes trades on eToro/Capital.com or paper simulates them.
Fixed: Correct PnL calculation with leverage.
Fixed: Time stop added.
Fixed: No pound sign in variable names.
"""
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ETORO_BASE = 'https://api.etoro.com/v1'

ETORO_INSTRUMENTS = {
    'BTC/USDT': 'BTC', 'ETH/USDT': 'ETH', 'SOL/USDT': 'SOL',
    'BNB/USDT': 'BNB', 'DOGE/USDT': 'DOGE', 'AVAX/USDT': 'AVAX',
    'AAPL': 'AAPL', 'TSLA': 'TSLA', 'NVDA': 'NVDA', 'AMZN': 'AMZN',
    'META': 'META', 'MSFT': 'MSFT', 'AMD': 'AMD', 'GOOGL': 'GOOGL',
    'GOLD': 'XAUUSD', 'SILVER': 'XAGUSD', 'OIL': 'OIL',
    'EUR/USD': 'EURUSD', 'GBP/USD': 'GBPUSD', 'USD/JPY': 'USDJPY',
    'AUD/USD': 'AUDUSD', 'USD/CAD': 'USDCAD', 'EUR/GBP': 'EURGBP',
    'SPY': 'SPY', 'QQQ': 'QQQ', 'GLD': 'GLD', 'SLV': 'SLV',
}


def _headers(api_key):
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _etoro_instrument(asset):
    return ETORO_INSTRUMENTS.get(asset, asset)


def _position_size(capital, risk_pct, entry, stop_loss):
    risk_amount = capital * risk_pct
    diff = abs(entry - stop_loss)
    return round(risk_amount / diff, 6) if diff else 0.0


def open_trade(signal, capital, cfg):
    """Opens a trade. Returns trade dict."""
    entry    = signal['price']
    tp       = signal['take_profit']
    sl       = signal['stop_loss']
    leverage = signal.get('leverage', 1)
    tp_pct   = signal.get('tp_pct', 0.01)
    sl_pct   = signal.get('sl_pct', 0.005)
    pos_sz   = _position_size(capital, cfg.RISK_PER_TRADE_PCT, entry, sl)
    risk_gbp = round(capital * cfg.RISK_PER_TRADE_PCT, 2)

    # Correct leveraged profit/loss calculation
    leveraged_pos    = capital * leverage
    potential_profit = round(leveraged_pos * tp_pct, 2)
    potential_loss   = round(leveraged_pos * sl_pct, 2)

    trade = {
        'id':               datetime.utcnow().strftime('%Y%m%d%H%M%S'),
        'asset':            signal['asset'],
        'asset_type':       signal.get('asset_type', 'crypto'),
        'strategy':         signal.get('strategy', 'UNKNOWN'),
        'direction':        signal['direction'],
        'entry_price':      entry,
        'take_profit':      tp,
        'stop_loss':        sl,
        'position_size':    pos_sz,
        'risk_amount':      risk_gbp,
        'potential_profit': potential_profit,
        'potential_loss':   potential_loss,
        'leverage':         leverage,
        'tp_pct':           tp_pct,
        'sl_pct':           sl_pct,
        'confidence':       signal['confidence'],
        'entry_time':       signal['timestamp'],
        'status':           'OPEN',
        'paper':            cfg.PAPER_TRADE,
        'broker':           'paper' if cfg.PAPER_TRADE else 'etoro',
        'capital_before':   round(capital, 2),
        'max_hours':        signal.get('max_hours', 24),
        'asset_label':      signal.get('asset_label', signal['asset']),
        'asset_emoji':      signal.get('asset_emoji', ''),
        'order_id':         None,
        'exit_price':       None,
        'exit_time':        None,
        'pnl':              None,
        'result':           None,
        'close_reason':     None,
    }

    if cfg.PAPER_TRADE:
        trade['order_id'] = f"PAPER_{trade['id']}"
        logger.info(
            f"[PAPER] {signal['direction']} {signal['asset']} @ {entry} "
            f"| TP:{tp} SL:{sl} | Leverage:{leverage}x "
            f"| Win=£{potential_profit} Loss=£{potential_loss}"
        )
        return trade

    # Live eToro order
    api_key    = cfg.ETORO_API_KEY
    instrument = _etoro_instrument(signal['asset'])
    action     = 'buy' if signal['direction'] == 'BUY' else 'sell'
    amount     = risk_gbp * 10

    try:
        r = requests.post(
            f'{ETORO_BASE}/trading/positions',
            headers=_headers(api_key),
            json={
                'instrumentId':  instrument,
                'action':        action,
                'amount':        amount,
                'takeProfit':    tp,
                'stopLoss':      sl,
                'leverageId':    leverage,
                'portfolioType': 'agent',
            },
            timeout=20
        )
        if r.ok:
            data = r.json()
            trade['order_id']   = str(data.get('positionId', data.get('id', 'unknown')))
            trade['entry_price'] = float(data.get('openRate', entry))
            logger.info(f"eToro order placed: {trade['order_id']} | {instrument} {action}")
        else:
            logger.error(f"eToro order failed: {r.status_code} {r.text}")
            trade['status'] = 'FAILED'
            trade['error']  = r.text
    except Exception as exc:
        logger.error(f"eToro exception: {exc}")
        trade['status'] = 'FAILED'
        trade['error']  = str(exc)

    return trade


def check_and_close(open_trades, current_prices, cfg):
    """
    Checks open trades against current prices.
    Closes at TP, SL, or time stop.
    Returns (updated_trades, newly_closed_trades).
    """
    updated = []
    closed  = []

    for t in open_trades:
        if t.get('status') != 'OPEN':
            updated.append(t)
            continue

        price = current_prices.get(t['asset'])
        if price is None:
            updated.append(t)
            continue

        hit_tp = (
            (t['direction'] == 'BUY'  and price >= t['take_profit']) or
            (t['direction'] == 'SELL' and price <= t['take_profit'])
        )
        hit_sl = (
            (t['direction'] == 'BUY'  and price <= t['stop_loss']) or
            (t['direction'] == 'SELL' and price >= t['stop_loss'])
        )

        # Time stop check
        max_hours  = t.get('max_hours', 24)
        entry_time = datetime.fromisoformat(t['entry_time'])
        hit_time   = datetime.utcnow() >= entry_time + timedelta(hours=max_hours)

        if not (hit_tp or hit_sl or hit_time):
            # Apply trailing stop
            if cfg.TRAILING_STOP_ENABLED:
                trail_pct = cfg.TRAILING_STOP_PCT
                if t['direction'] == 'BUY':
                    new_sl = round(price * (1 - trail_pct), 6)
                    if new_sl > t['stop_loss']:
                        t['stop_loss'] = new_sl
                        logger.info(f"Trailing stop up: {t['asset']} SL->{new_sl}")
                else:
                    new_sl = round(price * (1 + trail_pct), 6)
                    if new_sl < t['stop_loss']:
                        t['stop_loss'] = new_sl
                        logger.info(f"Trailing stop down: {t['asset']} SL->{new_sl}")
            updated.append(t)
            continue

        # Calculate PnL with leverage
        entry_price   = t['entry_price']
        leverage      = t.get('leverage', 1)
        capital       = t['capital_before']
        leveraged_pos = capital * leverage

        if t['direction'] == 'BUY':
            raw_pnl = (price - entry_price) / entry_price * leveraged_pos
        else:
            raw_pnl = (entry_price - price) / entry_price * leveraged_pos

        if hit_tp:
            result       = 'WIN'
            pnl          = round(max(raw_pnl, t.get('potential_profit', 0.01)), 2)
            close_reason = 'TP'
        elif hit_sl:
            result       = 'LOSS'
            pnl          = round(min(raw_pnl, -t.get('potential_loss', 0.01)), 2)
            close_reason = 'SL'
        else:
            pnl          = round(raw_pnl, 2)
            result       = 'WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'BREAKEVEN'
            close_reason = 'TIME'
            logger.info(f"Time stop: {t['asset']} after {max_hours}h | PnL: £{pnl:.2f}")

        # Close on eToro if live
        if not t.get('paper') and t.get('order_id') and cfg.ETORO_API_KEY:
            _close_etoro_position(t['order_id'], cfg)

        t.update({
            'status':       'CLOSED',
            'result':       result,
            'exit_price':   round(price, 6),
            'exit_time':    datetime.utcnow().isoformat(),
            'pnl':          pnl,
            'pnl_pct':      round(pnl / capital * 100, 2),
            'close_reason': close_reason,
        })

        closed.append(t)
        icon = 'WIN' if result == 'WIN' else 'LOSS' if result == 'LOSS' else 'EVEN'
        logger.info(
            f"{icon}: {t['asset']} {t['direction']} | "
            f"Entry:{entry_price} Exit:{price} | "
            f"PnL:£{pnl:.2f} | Reason:{close_reason}"
        )
        updated.append(t)

    return updated, closed


def _close_etoro_position(position_id, cfg):
    try:
        r = requests.delete(
            f'{ETORO_BASE}/trading/positions/{position_id}',
            headers=_headers(cfg.ETORO_API_KEY),
            timeout=15
        )
        if r.ok:
            logger.info(f"eToro position {position_id} closed.")
            return True
        logger.error(f"eToro close failed: {r.text}")
        return False
    except Exception as e:
        logger.error(f"eToro close exception: {e}")
        return False


def get_portfolio_balance(cfg):
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
        logger.error(f"eToro balance error: {e}")
    return None
