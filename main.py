"""
main.py v5.1 - Concentration filter
------------------------------------
Scheduler that runs every 15 min:
  1. Check daily loss limit
  2. Monitor open trades -> close at TP/SL/TIME
  3. Apply trailing stop on open trades
  4. Scan markets for new signals
  5. Filter out signals for assets that already have open positions
  6. Open trade for highest-confidence approved signal

Fixes from v5:
  - FIX 16: Concentration filter - skip signals for assets that already have an
    open position. Without this, trend-continuation setups that persist for many
    bars fire every scan and open duplicate trades on the same asset.
    Seen 2026-05-03: 3x BNB BUY positions opened in 45 mins on the same setup.

Inherited from v5:
  - signal['strategy'] safely fetched with .get()
  - GBP currency symbol used correctly
  - Trailing stop logic owned by main.py only
  - Banner reflects asset count from all 5 classes including ETFs
"""
import time
import logging
import schedule
from datetime import datetime, date, timedelta

import config as cfg
from modules import trade_logger
from modules import etoro_executor as trade_executor
from modules import content_generator, slide_creator, social_publisher, notifier
from modules import market_scanner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('main')

_last_signal = None


# -- Daily P&L ----------------------------------------------------------------

def _daily_pnl():
    today = date.today().isoformat()
    return sum(
        t.get('pnl', 0) for t in trade_logger.load_trades(cfg)
        if isinstance(t.get('exit_time'), str)
        and t.get('exit_time', '').startswith(today)
        and t.get('status') == 'CLOSED'
        and t.get('pnl') is not None
    )


def _daily_loss_exceeded():
    pnl = _daily_pnl()
    if pnl <= -cfg.MAX_DAILY_LOSS:
        logger.warning(f"Daily loss limit hit: GBP{pnl:.2f}")
        notifier.send(
            f"DAILY LOSS LIMIT HIT\n"
            f"P&L today: GBP{pnl:.2f}\n"
            f"Limit: GBP{cfg.MAX_DAILY_LOSS}\n"
            f"Bot paused until tomorrow.", cfg
        )
        return True
    return False


# -- Trailing stop ------------------------------------------------------------

def _apply_trailing_stop(trades, current_prices):
    """Moves stop loss up (BUY) or down (SELL) as price moves favourably."""
    if not getattr(cfg, 'TRAILING_STOP_ENABLED', False):
        return False

    trail_pct = getattr(cfg, 'TRAILING_STOP_PCT', 0.003)
    updated = False
    for t in trades:
        if t.get('status') != 'OPEN':
            continue
        price = current_prices.get(t.get('asset'))
        if not price:
            continue
        if t['direction'] == 'BUY':
            new_sl = round(price * (1 - trail_pct), 6)
            if new_sl > t.get('stop_loss', 0):
                t['stop_loss'] = new_sl
                updated = True
                logger.info(f"Trailing stop UP: {t['asset']} SL -> {new_sl}")
        else:
            new_sl = round(price * (1 + trail_pct), 6)
            current_sl = t.get('stop_loss', float('inf'))
            if new_sl < current_sl:
                t['stop_loss'] = new_sl
                updated = True
                logger.info(f"Trailing stop DOWN: {t['asset']} SL -> {new_sl}")
    return updated


# -- Scan cycle ---------------------------------------------------------------

def run_scan():
    global _last_signal
    logger.info("SCAN " + "=" * 40)

    # Step 1: Monitor open trades
    open_trades = trade_logger.get_open_trades(cfg)
    if open_trades:
        current_prices = market_scanner.get_current_prices(cfg)

        # Trailing stop (if enabled, owned by main.py)
        _apply_trailing_stop(open_trades, current_prices)

        updated, closed = trade_executor.check_and_close(open_trades, current_prices, cfg)

        # Persist updates back to disk
        all_trades = trade_logger.load_trades(cfg)
        id_map     = {t['id']: t for t in updated}
        all_trades = [id_map.get(t['id'], t) for t in all_trades]
        trade_logger.save_trades(all_trades, cfg)

        for t in closed:
            new_balance = trade_logger.update_equity(t['pnl'], cfg)
            try:
                msg = content_generator.generate_trade_closed_alert(t, new_balance, cfg)
                notifier.send(msg, cfg)
            except Exception as e:
                logger.error(f"Trade alert send failed: {e}")
                # Fallback minimal message
                notifier.send(
                    f"{t.get('result','?')} {t.get('asset')} {t.get('direction')}\n"
                    f"Entry: {t.get('entry_price')} -> Exit: {t.get('exit_price')}\n"
                    f"PnL: GBP{t.get('pnl', 0):.2f}\n"
                    f"Balance: GBP{new_balance:.2f}",
                    cfg
                )

    # Step 2: Daily loss check
    if _daily_loss_exceeded():
        return

    # Step 3: Trade limits
    today_count = trade_logger.count_today_trades(cfg)
    if today_count >= cfg.MAX_TRADES_PER_DAY:
        logger.info(f"Max trades/day reached ({cfg.MAX_TRADES_PER_DAY})")
        return

    open_count = len(trade_logger.get_open_trades(cfg))
    if open_count >= cfg.MAX_OPEN_TRADES:
        logger.info(f"Max open trades reached ({cfg.MAX_OPEN_TRADES})")
        return

    # Step 4: Scan markets
    open_trades_fresh = trade_logger.get_open_trades(cfg)
    signals = market_scanner.scan_markets(cfg, open_trades_fresh)
    if not signals:
        return

    # FIX 16: Concentration filter - skip signals for assets that already have
    # an open position. Without this, the same trend continuation setup fires
    # every scan and opens duplicate trades on the same asset (e.g. 3x BNB seen
    # 2026-05-03). One position per asset, regardless of direction.
    open_assets = {t.get('asset') for t in open_trades_fresh if t.get('asset')}
    filtered = [s for s in signals if s.get('asset') not in open_assets]
    skipped = [s for s in signals if s.get('asset') in open_assets]
    for s in skipped:
        logger.info(f"Concentration block: {s.get('asset')} {s.get('direction')} "
                    f"- already have open position")
    signals = filtered
    if not signals:
        logger.info("All signals blocked by concentration filter")
        return

    # Step 5: Open the highest-confidence signal (one per scan)
    signals.sort(key=lambda s: s.get('confidence', 0), reverse=True)
    best = signals[0]

    _last_signal = best

    try:
        alert = content_generator.generate_signal_alert(best, cfg)
        notifier.send(alert, cfg)
    except Exception as e:
        logger.error(f"Signal alert failed: {e}")

    equity = trade_logger.get_equity(cfg)
    trade  = trade_executor.open_trade(best, equity['balance'], cfg)
    trade_logger.save_trade(trade, cfg)

    logger.info(
        f"Trade opened: {best.get('strategy', 'EMA_TREND')} {best['direction']} "
        f"{best['asset']} @ {best['price']} | "
        f"TP:{best['take_profit']} SL:{best['stop_loss']} | "
        f"Lev:{best.get('leverage', 1)}x | "
        f"ExpProfit:GBP{best.get('expected_profit', 0)}"
    )


# -- Daily content ------------------------------------------------------------

def run_daily_content():
    logger.info("DAILY CONTENT " + "=" * 30)

    try:
        stats = trade_logger.get_stats(cfg)
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        return

    try:
        content = content_generator.generate_daily_content(stats, _last_signal, cfg)
        media   = slide_creator.create_daily_content(stats, _last_signal, content, cfg)
        results = social_publisher.publish_all(media, content, cfg)
    except Exception as e:
        logger.error(f"Daily content generation failed: {e}")
        media, results = {}, {}

    daily_pnl = _daily_pnl()
    sign  = '+' if stats.get('total_pnl', 0) >= 0 else ''
    dsign = '+' if daily_pnl >= 0 else ''

    summary = (
        f"DAY {stats.get('days_active', 0)} SUMMARY\n\n"
        f"Balance:       GBP{stats.get('balance', 0):.2f}\n"
        f"Today P&L:     {dsign}GBP{daily_pnl:.2f}\n"
        f"Total P&L:     {sign}GBP{stats.get('total_pnl', 0):.2f}\n"
        f"Win rate:      {stats.get('win_rate', 0)}%\n"
        f"Total trades:  {stats.get('total_trades', 0)}\n"
        f"Wins/Losses:   {stats.get('wins', 0)}/{stats.get('losses', 0)}\n\n"
        f"Posts: {', '.join(k + (':OK' if v else ':FAIL') for k, v in results.items()) if results else '(skipped)'}\n\n"
        f"{getattr(cfg, 'CHANNEL_NAME', 'Trading Bot')}"
    )
    notifier.send(summary, cfg)

    if media.get('thumbnail'):
        try:
            notifier.send_photo(media['thumbnail'], f"Day {stats.get('days_active', 0)} slides", cfg)
        except Exception as e:
            logger.error(f"Photo send failed: {e}")


# -- Main ---------------------------------------------------------------------

def main():
    total_assets = (
        len(getattr(cfg, 'CRYPTO_ASSETS', {})) +
        len(getattr(cfg, 'FOREX_ASSETS', {})) +
        len(getattr(cfg, 'STOCK_ASSETS', {})) +
        len(getattr(cfg, 'ETF_ASSETS', {})) +
        len(getattr(cfg, 'COMMODITY_ASSETS', {}))
    )

    logger.info("Trading Bot v5.1 starting")
    logger.info(f"  Mode:          {'PAPER' if cfg.PAPER_TRADE else 'LIVE'}")
    logger.info(f"  Capital:       GBP{cfg.INITIAL_CAPITAL}")
    logger.info(f"  Assets:        {total_assets} across 5 classes")
    logger.info(f"  Strategy:      EMA_TREND (single strategy)")
    logger.info(f"  Min conf:      {cfg.MIN_CONFIDENCE}%")
    logger.info(f"  Daily limit:   GBP{cfg.MAX_DAILY_LOSS}")
    logger.info(f"  Max open:      {cfg.MAX_OPEN_TRADES}")
    logger.info(f"  Max per day:   {cfg.MAX_TRADES_PER_DAY}")
    logger.info(f"  Trailing stop: {'ON' if getattr(cfg, 'TRAILING_STOP_ENABLED', False) else 'OFF'}")

    notifier.send(
        f"Trading Bot v5.1 Started\n\n"
        f"Mode: {'Paper' if cfg.PAPER_TRADE else 'LIVE'}\n"
        f"Capital: GBP{cfg.INITIAL_CAPITAL}\n"
        f"Assets: {total_assets} total\n"
        f"  {len(getattr(cfg,'CRYPTO_ASSETS',{}))} crypto (24/7)\n"
        f"  {len(getattr(cfg,'FOREX_ASSETS',{}))} forex (30x leverage)\n"
        f"  {len(getattr(cfg,'STOCK_ASSETS',{}))} stocks + {len(getattr(cfg,'ETF_ASSETS',{}))} ETFs\n"
        f"  {len(getattr(cfg,'COMMODITY_ASSETS',{}))} commodity\n"
        f"Strategy: EMA_TREND\n"
        f"Min confidence: {cfg.MIN_CONFIDENCE}%\n"
        f"Daily loss limit: GBP{cfg.MAX_DAILY_LOSS}\n"
        f"Max open trades: {cfg.MAX_OPEN_TRADES}",
        cfg
    )

    run_scan()
    schedule.every(cfg.SCAN_INTERVAL_MINUTES).minutes.do(run_scan)
    schedule.every().day.at(f"{cfg.DAILY_POST_HOUR:02d}:00").do(run_daily_content)

    logger.info(f"Running - scan every {cfg.SCAN_INTERVAL_MINUTES}min")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
