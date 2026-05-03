"""
etoro_executor.py v3.1 - Phase B: WIN/LOSS by PnL sign
-------------------------------------------------------
Opens and closes paper trades, computes PnL with correct leverage.

Fixes from v3:
  - FIX 18: Result label (WIN/LOSS/BREAKEVEN) determined by sign of PnL, not
    by which level was hit. Previously, a profitable trade closed by a trailed
    SL was labelled LOSS - misleading. Now: pnl>0 -> WIN, pnl<0 -> LOSS,
    pnl==0 -> BREAKEVEN. Close reason tracked separately as TP/SL/TRAIL/TIME.
  - Distinguishes TRAIL (trailed-SL hit after activation) from SL (initial
    stop hit, trail never activated). Uses trail_activated flag set by main.py.

Inherited from v3:
  - Reads leverage / tp_pct / sl_pct / max_hours / labels DIRECTLY from
    asset_config rather than trusting signal dict (defensive: even if scanner
    forgets a key, executor still uses correct values)
  - Removed duplicate trailing-stop logic (lives only in main.py now)
  - Removed live eToro execution code path (was always failing per handover doc;
    user is on Capital.com, not eToro). Kept module name for backward compat.
"""
import logging
from datetime import datetime, timedelta
from modules import asset_config

logger = logging.getLogger(__name__)


def _position_size(capital, risk_pct, entry, stop_loss):
    """Position size for risk-based sizing. Used for record-keeping only;
    leveraged PnL formula uses capital * leverage directly."""
    risk_amount = capital * risk_pct
    diff = abs(entry - stop_loss)
    return round(risk_amount / diff, 6) if diff else 0.0


def open_trade(signal, capital, cfg):
    """Opens a trade (paper-mode). Returns trade dict."""
    asset    = signal['asset']
    settings = asset_config.get(asset)

    # Single source of truth = asset_config. Signal dict is just a hint.
    leverage  = settings['leverage']
    tp_pct    = settings['tp']
    sl_pct    = settings['sl']
    max_hours = settings['max_hours']
    label     = settings.get('label', asset)
    emoji     = settings.get('emoji', '?')

    entry = signal['price']
    tp    = signal['take_profit']
    sl    = signal['stop_loss']

    pos_sz   = _position_size(capital, cfg.RISK_PER_TRADE_PCT, entry, sl)
    risk_gbp = round(capital * cfg.RISK_PER_TRADE_PCT, 2)

    # Leveraged paper PnL: capital is the margin, gain = move% * capital * leverage
    leveraged_pos    = capital * leverage
    potential_profit = round(leveraged_pos * tp_pct, 2)
    potential_loss   = round(leveraged_pos * sl_pct, 2)

    trade_id = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:18]

    trade = {
        'id':               trade_id,
        'asset':            asset,
        'asset_type':       signal.get('asset_type', 'unknown'),
        'asset_label':      label,
        'asset_emoji':      emoji,
        'strategy':         signal.get('strategy', 'EMA_TREND'),
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
        'max_hours':        max_hours,
        'confidence':       signal.get('confidence', 0),
        'entry_time':       signal.get('timestamp', datetime.utcnow().isoformat()),
        'status':           'OPEN',
        'paper':            True,
        'broker':           'paper',
        'capital_before':   round(capital, 2),
        'order_id':         f"PAPER_{trade_id}",
        'exit_price':       None,
        'exit_time':        None,
        'pnl':              None,
        'pnl_pct':          None,
        'result':           None,
        'close_reason':     None,
    }

    logger.info(
        f"[OPEN] {trade['direction']} {asset} @ {entry} "
        f"| TP:{tp} SL:{sl} | Lev:{leverage}x "
        f"| Win=GBP{potential_profit} Loss=GBP{potential_loss}"
    )
    return trade


def check_and_close(open_trades, current_prices, cfg):
    """Checks open trades against current prices.
    Closes at TP, SL, or time stop. Returns (updated_trades, newly_closed_trades).
    """
    updated = []
    closed  = []

    for t in open_trades:
        if t.get('status') != 'OPEN':
            updated.append(t)
            continue

        asset = t.get('asset')
        price = current_prices.get(asset)
        if price is None:
            logger.warning(f"No current price for {asset} - cannot evaluate trade {t.get('id')}")
            updated.append(t)
            continue

        direction = t['direction']
        entry     = t['entry_price']
        tp_target = t['take_profit']
        sl_target = t['stop_loss']

        hit_tp = (
            (direction == 'BUY'  and price >= tp_target) or
            (direction == 'SELL' and price <= tp_target)
        )
        hit_sl = (
            (direction == 'BUY'  and price <= sl_target) or
            (direction == 'SELL' and price >= sl_target)
        )

        # Time stop
        max_hours  = t.get('max_hours', 24)
        try:
            entry_time = datetime.fromisoformat(t['entry_time'])
        except Exception:
            entry_time = datetime.utcnow()
        hit_time = datetime.utcnow() >= entry_time + timedelta(hours=max_hours)

        if not (hit_tp or hit_sl or hit_time):
            updated.append(t)
            continue

        # Calculate leveraged PnL
        leverage      = t.get('leverage', 1)
        capital       = t.get('capital_before', cfg.INITIAL_CAPITAL)
        leveraged_pos = capital * leverage

        if direction == 'BUY':
            raw_pnl = (price - entry) / entry * leveraged_pos
        else:
            raw_pnl = (entry - price) / entry * leveraged_pos

        pnl = round(raw_pnl, 2)

        # FIX 18: Determine close_reason from what was hit, but determine
        # WIN/LOSS strictly from sign of PnL. Previously, a profitable trade
        # closed by a trailed SL was labelled LOSS - confusing and wrong.
        if hit_tp:
            close_reason = 'TP'
        elif hit_sl:
            # Distinguish trail-stop from original-stop close
            close_reason = 'TRAIL' if t.get('trail_activated') else 'SL'
        else:
            close_reason = 'TIME'
            logger.info(f"Time stop: {asset} after {max_hours}h | PnL: GBP{pnl:.2f}")

        if pnl > 0:
            result = 'WIN'
        elif pnl < 0:
            result = 'LOSS'
        else:
            result = 'BREAKEVEN'

        t.update({
            'status':       'CLOSED',
            'result':       result,
            'exit_price':   round(price, 6),
            'exit_time':    datetime.utcnow().isoformat(),
            'pnl':          pnl,
            'pnl_pct':      round(pnl / capital * 100, 2) if capital else 0.0,
            'close_reason': close_reason,
        })
        closed.append(t)

        logger.info(
            f"[{result}] {asset} {direction} | Entry:{entry} Exit:{price} | "
            f"PnL:GBP{pnl:.2f} | Reason:{close_reason}"
        )
        updated.append(t)

    return updated, closed


def get_portfolio_balance(cfg):
    """Live broker balance fetch - paper mode returns None."""
    return None
