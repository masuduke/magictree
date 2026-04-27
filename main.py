"""
main.py v4 — £25/day optimised
--------------------------------
Every 15 min:
  1. Check daily loss limit
  2. Monitor open trades → close at TP/SL/TIME
  3. Scan 27 assets × 4 strategies = 108 opportunities
  4. AI approves best signal
  5. Open trade

Every day 8pm UTC:
  1. Generate AI content
  2. Create slides + video
  3. Post to social media
  4. Send daily summary
"""
import time, logging, schedule
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


# ── Daily P&L ─────────────────────────────────────────────────────────────────

def _daily_pnl():
    today = date.today().isoformat()
    return sum(
        t.get('pnl', 0) for t in trade_logger.load_trades(cfg)
        if isinstance(t.get('exit_time'), str)
        and t.get('exit_time','').startswith(today)
        and t.get('status') == 'CLOSED'
        and t.get('pnl') is not None
    )

def _daily_loss_exceeded():
    pnl = _daily_pnl()
    if pnl <= -cfg.MAX_DAILY_LOSS:
        logger.warning(f"Daily loss limit hit: £{pnl:.2f}")
        notifier.send(
            f"DAILY LOSS LIMIT HIT\n"
            f"P&L today: £{pnl:.2f}\n"
            f"Limit: £{cfg.MAX_DAILY_LOSS}\n"
            f"Bot paused until tomorrow.", cfg
        )
        return True
    return False


# ── Trailing stop ─────────────────────────────────────────────────────────────

def _apply_trailing_stop(trades, current_prices):
    """Moves stop loss up as price moves in our favour."""
    updated = False
    for t in trades:
        if t.get('status') != 'OPEN':
            continue
        price = current_prices.get(t['asset'])
        if not price:
            continue
        trail_pct = cfg.TRAILING_STOP_PCT
        if t['direction'] == 'BUY':
            new_sl = round(price * (1 - trail_pct), 6)
            if new_sl > t['stop_loss']:
                t['stop_loss'] = new_sl
                updated = True
                logger.info(f"Trailing stop moved up: {t['asset']} SL -> {new_sl}")
        else:
            new_sl = round(price * (1 + trail_pct), 6)
            if new_sl < t['stop_loss']:
                t['stop_loss'] = new_sl
                updated = True
                logger.info(f"Trailing stop moved down: {t['asset']} SL -> {new_sl}")
    return updated


# ── Scan cycle ────────────────────────────────────────────────────────────────

def run_scan():
    global _last_signal
    logger.info("SCAN " + "="*40)

    # Step 1: Monitor and close open trades
    open_trades = trade_logger.get_open_trades(cfg)
    if open_trades:
        current_prices = market_scanner.get_current_prices(cfg)

        # Apply trailing stop
        if cfg.TRAILING_STOP_ENABLED:
            _apply_trailing_stop(open_trades, current_prices)

        updated, closed = trade_executor.check_and_close(open_trades, current_prices, cfg)

        all_trades = trade_logger.load_trades(cfg)
        id_map     = {t['id']: t for t in updated}
        all_trades = [id_map.get(t['id'], t) for t in all_trades]
        trade_logger.save_trades(all_trades, cfg)

        for t in closed:
            new_balance = trade_logger.update_equity(t['pnl'], cfg)
            msg = content_generator.generate_trade_closed_alert(t, new_balance, cfg)
            notifier.send(msg, cfg)

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

    # Step 4: Scan markets — 27 assets x 4 strategies
    open_trades_fresh = trade_logger.get_open_trades(cfg)
    signals = market_scanner.scan_markets(cfg, open_trades_fresh)

    for signal in signals:
        if signal['confidence'] < cfg.MIN_CONFIDENCE:
            continue

        _last_signal = signal

        # Alert
        alert = content_generator.generate_signal_alert(signal, cfg)
        notifier.send(alert, cfg)

        # Open trade
        equity = trade_logger.get_equity(cfg)
        trade  = trade_executor.open_trade(signal, equity['balance'], cfg)
        trade_logger.save_trade(trade, cfg)

        logger.info(
            f"Trade opened: {signal['strategy']} {signal['direction']} "
            f"{signal['asset']} @ {signal['price']} | "
            f"TP:{signal['take_profit']} SL:{signal['stop_loss']} | "
            f"ExpProfit:£{signal.get('expected_profit',0)}"
        )
        break  # One trade per scan


# ── Daily content ─────────────────────────────────────────────────────────────

def run_daily_content():
    logger.info("DAILY CONTENT " + "="*30)

    stats   = trade_logger.get_stats(cfg)
    content = content_generator.generate_daily_content(stats, _last_signal, cfg)
    media   = slide_creator.create_daily_content(stats, _last_signal, content, cfg)
    results = social_publisher.publish_all(media, content, cfg)

    sym        = cfg.CURRENCY_SYMBOL
    s          = stats
    daily_pnl  = _daily_pnl()
    sign       = '+' if s['total_pnl'] >= 0 else ''
    dsign      = '+' if daily_pnl >= 0 else ''

    summary = (
        f"DAY {s['days_active']} SUMMARY\n\n"
        f"Balance:       {sym}{s['balance']:.2f}\n"
        f"Today P&L:     {dsign}{sym}{daily_pnl:.2f}\n"
        f"Total P&L:     {sign}{sym}{s['total_pnl']:.2f}\n"
        f"Win rate:      {s['win_rate']}%\n"
        f"Total trades:  {s['total_trades']}\n"
        f"Wins/Losses:   {s['wins']}/{s['losses']}\n\n"
        f"Posts: {', '.join(k+(':OK' if v else ':FAIL') for k,v in results.items())}\n\n"
        f"{cfg.CHANNEL_NAME}"
    )
    notifier.send(summary, cfg)

    if media.get('thumbnail'):
        notifier.send_photo(media['thumbnail'], f"Day {s['days_active']} slides", cfg)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    total_assets = (len(cfg.CRYPTO_ASSETS) + len(cfg.FOREX_ASSETS) +
                    len(cfg.STOCK_ASSETS) + len(cfg.ETF_ASSETS) +
                    len(cfg.COMMODITY_ASSETS))

    logger.info("Trading Bot v4 starting")
    logger.info(f"  Mode:          {'PAPER' if cfg.PAPER_TRADE else 'LIVE'}")
    logger.info(f"  Capital:       £{cfg.INITIAL_CAPITAL}")
    logger.info(f"  Assets:        {total_assets} across 5 classes")
    logger.info(f"  Strategies:    EMA + Bollinger Band + RSI Reversal + Momentum")
    logger.info(f"  Opportunities: {total_assets} x 4 = {total_assets*4} per scan")
    logger.info(f"  Min conf:      {cfg.MIN_CONFIDENCE}%")
    logger.info(f"  Daily limit:   £{cfg.MAX_DAILY_LOSS}")
    logger.info(f"  Trailing stop: {'ON' if cfg.TRAILING_STOP_ENABLED else 'OFF'}")

    notifier.send(
        f"Trading Bot v4 Started\n\n"
        f"Mode: {'Paper' if cfg.PAPER_TRADE else 'LIVE'}\n"
        f"Capital: £{cfg.INITIAL_CAPITAL}\n"
        f"Assets: {total_assets} total\n"
        f"  {len(cfg.CRYPTO_ASSETS)} crypto (24/7)\n"
        f"  {len(cfg.FOREX_ASSETS)} forex (30x leverage)\n"
        f"  {len(cfg.STOCK_ASSETS)} stocks + {len(cfg.ETF_ASSETS)} ETFs\n"
        f"  {len(cfg.COMMODITY_ASSETS)} commodity\n"
        f"Strategies: 4 (EMA, BB, RSI, Momentum)\n"
        f"Signal opportunities: {total_assets*4}/scan\n"
        f"Min confidence: {cfg.MIN_CONFIDENCE}%\n"
        f"Target: Per-asset (Forex:£15/trade, Crypto:£6, Stocks:£15-30)\n"
        f"Daily loss limit: £{cfg.MAX_DAILY_LOSS}",
        cfg
    )

    run_scan()

    schedule.every(cfg.SCAN_INTERVAL_MINUTES).minutes.do(run_scan)
    schedule.every().day.at(f"{cfg.DAILY_POST_HOUR:02d}:00").do(run_daily_content)

    logger.info(f"Running — scan every {cfg.SCAN_INTERVAL_MINUTES}min")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
