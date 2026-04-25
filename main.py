"""
main.py  v3 — Full Risk Management Edition
-------------------------------------------
Every 15 min:
  1. Check daily loss limit — stop if exceeded
  2. Check max open trades — skip if at limit
  3. Monitor open trades → close at TP/SL
  4. Scan ALL asset classes for signals
  5. AI approves/rejects each signal
  6. Open trade if approved + correlation check

Every day 8pm UTC:
  1. Generate AI content via Claude
  2. Create slides + video
  3. Post to all social platforms
  4. Send Telegram daily summary
"""
import time
import logging
import schedule
from datetime import datetime, date

import config as cfg
from modules import trade_logger
from modules import etoro_executor as trade_executor
from modules import content_generator, slide_creator, social_publisher, notifier
from modules import market_scanner

logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s [%(levelname)s] %(name)s – %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('main')

_last_signal = None


# ── Daily loss tracking ───────────────────────────────────────────────────────

def _get_daily_pnl():
    """Calculate today's P&L from closed trades."""
    today  = date.today().isoformat()
    trades = trade_logger.load_trades(cfg)
    return sum(
        t.get('pnl', 0) for t in trades
        if t.get('exit_time', '').startswith(today)
        and t.get('status') == 'CLOSED'
        and t.get('pnl') is not None
    )


def _daily_loss_exceeded():
    """Returns True if daily loss limit has been hit."""
    daily_pnl = _get_daily_pnl()
    if daily_pnl <= -cfg.MAX_DAILY_LOSS:
        logger.warning(f"🛑 Daily loss limit hit: £{daily_pnl:.2f} — no more trades today")
        notifier.send(
            f"🛑 *Daily Loss Limit Hit*\n"
            f"P&L today: £{daily_pnl:.2f}\n"
            f"Limit: £{cfg.MAX_DAILY_LOSS}\n"
            f"Bot paused until tomorrow.",
            cfg
        )
        return True
    return False


def _count_open_trades():
    return len(trade_logger.get_open_trades(cfg))


# ── Scan cycle ────────────────────────────────────────────────────────────────

def run_scan():
    global _last_signal
    logger.info("━━━ SCAN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── Step 1: Close open trades at TP/SL ────────────────────────────────────
    open_trades = trade_logger.get_open_trades(cfg)
    if open_trades:
        current_prices = market_scanner.get_current_prices(cfg)
        updated, closed = trade_executor.check_and_close(open_trades, current_prices, cfg)

        all_trades = trade_logger.load_trades(cfg)
        id_map     = {t['id']: t for t in updated}
        all_trades = [id_map.get(t['id'], t) for t in all_trades]
        trade_logger.save_trades(all_trades, cfg)

        for t in closed:
            new_balance = trade_logger.update_equity(t['pnl'], cfg)
            msg = content_generator.generate_trade_closed_alert(t, new_balance, cfg)
            notifier.send(msg, cfg)
            logger.info(f"{'✅' if t['result']=='WIN' else '❌'} "
                        f"{t['asset']} {t['direction']} | "
                        f"PnL:£{t['pnl']:.2f} | Balance:£{new_balance:.2f}")

    # ── Step 2: Check daily loss limit ────────────────────────────────────────
    if _daily_loss_exceeded():
        return

    # ── Step 3: Check trade limits ────────────────────────────────────────────
    today_count = trade_logger.count_today_trades(cfg)
    if today_count >= cfg.MAX_TRADES_PER_DAY:
        logger.info(f"⏸ Max trades/day reached ({cfg.MAX_TRADES_PER_DAY})")
        return

    if _count_open_trades() >= cfg.MAX_OPEN_TRADES:
        logger.info(f"⏸ Max open trades reached ({cfg.MAX_OPEN_TRADES})")
        return

    # ── Step 4: Scan markets ───────────────────────────────────────────────────
    open_trades_fresh = trade_logger.get_open_trades(cfg)
    signals = market_scanner.scan_markets(cfg, open_trades_fresh)

    for signal in signals:
        if signal['confidence'] < cfg.MIN_CONFIDENCE:
            continue

        _last_signal = signal

        # Send Telegram alert
        alert = content_generator.generate_signal_alert(signal, cfg)
        notifier.send(alert, cfg)

        # Open trade
        equity = trade_logger.get_equity(cfg)
        trade  = trade_executor.open_trade(signal, equity['balance'], cfg)
        trade_logger.save_trade(trade, cfg)

        logger.info(f"📈 Trade opened: {signal['direction']} {signal['asset']} "
                    f"@ {signal['price']} | TP:{signal['take_profit']} | SL:{signal['stop_loss']}")

        # Only take ONE trade per scan
        break


# ── Daily content cycle ───────────────────────────────────────────────────────

def run_daily_content():
    logger.info("━━━ DAILY CONTENT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    stats   = trade_logger.get_stats(cfg)
    content = content_generator.generate_daily_content(stats, _last_signal, cfg)
    media   = slide_creator.create_daily_content(stats, _last_signal, content, cfg)
    results = social_publisher.publish_all(media, content, cfg)

    sym    = cfg.CURRENCY_SYMBOL
    s      = stats
    sign   = '+' if s['total_pnl'] >= 0 else ''
    daily_pnl = _get_daily_pnl()
    daily_sign = '+' if daily_pnl >= 0 else ''

    summary = (
        f"📅 *Day {s['days_active']} Summary*\n\n"
        f"💰 Balance:      {sym}{s['balance']:.2f}\n"
        f"📊 Today P&L:    {daily_sign}{sym}{daily_pnl:.2f}\n"
        f"📈 Total P&L:    {sign}{sym}{s['total_pnl']:.2f}\n"
        f"🎯 Win rate:     {s['win_rate']}%\n"
        f"🔢 Total trades: {s['total_trades']}\n"
        f"✅ Wins:         {s['wins']}\n"
        f"❌ Losses:       {s['losses']}\n\n"
        f"Posts: {', '.join(k + (':OK' if v else ':FAIL') for k,v in results.items())}\n\n"
        f"_{cfg.CHANNEL_NAME}_"
    )
    notifier.send(summary, cfg)

    if media.get('thumbnail'):
        notifier.send_photo(media['thumbnail'], f"Day {s['days_active']} slides", cfg)

    logger.info("✅ Daily content cycle complete.")


# ── Startup ───────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Trading Bot v3 starting…")
    logger.info(f"   Mode:         {'📝 PAPER' if cfg.PAPER_TRADE else '💰 LIVE'}")
    logger.info(f"   Capital:      £{cfg.INITIAL_CAPITAL}")
    logger.info(f"   Assets:       Crypto({len(cfg.CRYPTO_ASSETS)}) + "
                f"Forex({len(cfg.FOREX_ASSETS)}) + "
                f"Stocks({len(cfg.STOCK_ASSETS)}) + "
                f"ETFs({len(cfg.ETF_ASSETS)}) + "
                f"Commodities({len(cfg.COMMODITY_ASSETS)})")
    logger.info(f"   Min conf:     {cfg.MIN_CONFIDENCE}%")
    logger.info(f"   TP/SL:        Per-asset (BTC:3%/1% SOL:4%/1.3% Forex:0.5%/0.2% Stocks:1.5-3%)")
    logger.info(f"   Daily limit:  £{cfg.MAX_DAILY_LOSS} max loss")
    logger.info(f"   Max trades:   {cfg.MAX_TRADES_PER_DAY}/day | {cfg.MAX_OPEN_TRADES} open")

    notifier.send(
        f"🚀 *Trading Bot v3 Started*\n\n"
        f"Mode: {'Paper' if cfg.PAPER_TRADE else 'LIVE'}\n"
        f"Capital: £{cfg.INITIAL_CAPITAL}\n"
        f"Assets: {len(cfg.CRYPTO_ASSETS)} crypto, {len(cfg.FOREX_ASSETS)} forex, "
        f"{len(cfg.STOCK_ASSETS)} stocks, {len(cfg.ETF_ASSETS)} ETFs, "
        f"{len(cfg.COMMODITY_ASSETS)} commodities\n"
        f"Min confidence: {cfg.MIN_CONFIDENCE}%\n"
        f"Target: £{cfg.TAKE_PROFIT_PCT*100:.0f}% profit / £{cfg.STOP_LOSS_PCT*100:.0f}% stop\n"
        f"Daily loss limit: £{cfg.MAX_DAILY_LOSS}",
        cfg
    )

    run_scan()

    schedule.every(cfg.SCAN_INTERVAL_MINUTES).minutes.do(run_scan)
    schedule.every().day.at(f"{cfg.DAILY_POST_HOUR:02d}:00").do(run_daily_content)

    logger.info(f"✅ Running — scan every {cfg.SCAN_INTERVAL_MINUTES}min | "
                f"post at {cfg.DAILY_POST_HOUR:02d}:00 UTC")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
