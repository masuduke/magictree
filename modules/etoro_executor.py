"""
etoro_executor.py v3.2 - FIX 21: Intra-bar SL/TP detection
-----------------------------------------------------------
Opens and closes paper trades, computes PnL with correct leverage.

Fix 21 (2026-05-11): check_and_close() now accepts intra_bar_history dict.
  When provided, walks 1h bars between entry and now to detect SL/TP hits AT
  the SL/TP price (matching backtest + real-broker behaviour). Without this,
  paper trades closed at whatever the scan-time price was - up to 3% past SL
  on a 4h scan cadence. Caused two -£548 / -£1087 over-losses on 2026-05-11.

Fixes from v3:
  - FIX 18: Result label (WIN/LOSS/BREAKEVEN) determined by sign of PnL, not
    by which level was hit.
  - Distinguishes TRAIL (trailed-SL hit after activation) from SL (initial
    stop hit, trail never activated).

Inherited from v3:
  - Reads leverage / tp_pct / sl_pct / max_hours / labels DIRECTLY from
    asset_config rather than trusting signal dict (defensive: even if scanner
    forgets a key, executor still uses correct values)
  - Removed duplicate trailing-stop logic (lives only in main.py now)
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


def check_and_close(open_trades, current_prices, cfg, intra_bar_history=None):
    """Checks open trades against current prices.
    Closes at TP, SL, or time stop. Returns (updated_trades, newly_closed_trades).
    
    FIX 21 (2026-05-11): When intra_bar_history is provided, walks through bars
    between entry and now to detect SL/TP hits AT the SL/TP price, not at the
    current (possibly worse) price. This matches backtest behaviour and real
    broker stop-loss orders.
    
    intra_bar_history: optional dict {asset: DataFrame with ts/open/high/low/close}
                       containing bars since trade entry. If None or asset missing,
                       falls back to current-price check (legacy behaviour).
    """
    updated = []
    closed  = []

    for t in open_trades:
        if t.get('status') != 'OPEN':
            updated.append(t)
            continue

        asset = t.get('asset')
        current_price = current_prices.get(asset)
        if current_price is None:
            logger.warning(f"No current price for {asset} - cannot evaluate trade {t.get('id')}")
            updated.append(t)
            continue

        direction = t['direction']
        entry     = t['entry_price']
        tp_target = t['take_profit']
        sl_target = t['stop_loss']

        # FIX 21: Try intra-bar detection first if history is available
        exit_price = None
        exit_reason = None
        history = intra_bar_history.get(asset) if intra_bar_history else None
        if history is not None and len(history) > 0:
            for _, bar in history.iterrows():
                high = float(bar['high'])
                low  = float(bar['low'])
                if direction == 'BUY':
                    # Check SL first: if both hit in same bar, assume SL hit first (conservative)
                    if low <= sl_target:
                        exit_price = sl_target
                        exit_reason = 'TRAIL' if t.get('trail_activated') else 'SL'
                        break
                    if high >= tp_target:
                        exit_price = tp_target
                        exit_reason = 'TP'
                        break
                else:  # SELL
                    if high >= sl_target:
                        exit_price = sl_target
                        exit_reason = 'TRAIL' if t.get('trail_activated') else 'SL'
                        break
                    if low <= tp_target:
                        exit_price = tp_target
                        exit_reason = 'TP'
                        break

        # If no intra-bar SL/TP hit, fall back to current-price check (catches
        # cases where intra-bar data wasn't available, or for time-stop)
        if exit_price is None:
            hit_tp = (
                (direction == 'BUY'  and current_price >= tp_target) or
                (direction == 'SELL' and current_price <= tp_target)
            )
            hit_sl = (
                (direction == 'BUY'  and current_price <= sl_target) or
                (direction == 'SELL' and current_price >= sl_target)
            )
            if hit_tp:
                # Close AT tp target, not at current (which is even better - rare)
                exit_price = tp_target
                exit_reason = 'TP'
            elif hit_sl:
                # Close AT sl target, not at the worse current price
                # (this is the bug fix - matches a real broker SL fill)
                exit_price = sl_target
                exit_reason = 'TRAIL' if t.get('trail_activated') else 'SL'

        # Time stop check (independent of price levels)
        max_hours  = t.get('max_hours', 24)
        try:
            entry_time = datetime.fromisoformat(t['entry_time'])
        except Exception:
            entry_time = datetime.utcnow()
        hit_time = datetime.utcnow() >= entry_time + timedelta(hours=max_hours)

        if exit_price is None and not hit_time:
            updated.append(t)
            continue

        # If we got here via TIME (no TP/SL hit), use current price
        if exit_price is None:
            exit_price = current_price
            exit_reason = 'TIME'

        # Calculate leveraged PnL using the exit price determined above
        leverage      = t.get('leverage', 1)
        capital       = t.get('capital_before', cfg.INITIAL_CAPITAL)
        leveraged_pos = capital * leverage

        if direction == 'BUY':
            raw_pnl = (exit_price - entry) / entry * leveraged_pos
        else:
            raw_pnl = (entry - exit_price) / entry * leveraged_pos

        pnl = round(raw_pnl, 2)

        # FIX 18: WIN/LOSS by PnL sign (not by close reason)
        if pnl > 0:
            result = 'WIN'
        elif pnl < 0:
            result = 'LOSS'
        else:
            result = 'BREAKEVEN'

        if exit_reason == 'TIME':
            logger.info(f"Time stop: {asset} after {max_hours}h | PnL: GBP{pnl:.2f}")

        t.update({
            'status':       'CLOSED',
            'result':       result,
            'exit_price':   round(exit_price, 6),
            'exit_time':    datetime.utcnow().isoformat(),
            'pnl':          pnl,
            'pnl_pct':      round(pnl / capital * 100, 2) if capital else 0.0,
            'close_reason': exit_reason,
        })
        closed.append(t)

        logger.info(
            f"[{result}] {asset} {direction} | Entry:{entry} Exit:{exit_price} | "
            f"PnL:GBP{pnl:.2f} | Reason:{exit_reason}"
        )
        updated.append(t)

    return updated, closed


def get_portfolio_balance(cfg):
    """Live broker balance fetch - paper mode returns None."""
    return None
