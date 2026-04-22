"""
main.py
-------
THE BRAIN OF THE TRADING BOT.

What it does every 15 minutes:
  1. Scans BTC, ETH, Gold for EMA + RSI signals
  2. If signal found and daily trade limit not reached → opens trade
  3. Checks open trades → closes at TP or SL
  4. Sends Telegram alerts

What it does once a day at 8 PM UTC:
  1. Generates AI content (script, captions) via Anthropic
  2. Creates slides + video showing the journey
  3. Posts to Instagram, YouTube, TikTok
  4. Sends daily Telegram summary
"""

import time
import logging
import schedule
from datetime import datetime

import config as cfg
from modules import market_scanner, trade_logger
from modules import etoro_executor as trade_executor
from modules import content_generator, slide_creator, social_publisher, notifier

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = '%(asctime)s [%(levelname)s] %(name)s – %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('main')

# ── state ─────────────────────────────────────────────────────────────────────
_last_signal: dict | None = None   # kept for content generation


# ─────────────────────────────────────────────────────────────────────────────
# SCAN CYCLE  (every 15 minutes)
# ─────────────────────────────────────────────────────────────────────────────

def run_scan():
    global _last_signal
    logger.info("━━━ SCAN CYCLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── 1. Check & close open trades ──────────────────────────────────────────
    open_trades = trade_logger.get_open_trades(cfg)
    if open_trades:
        current_prices = market_scanner.get_current_prices(cfg)
        updated_trades, closed_trades = trade_executor.check_and_close(
            open_trades, current_prices, cfg
        )

        # Persist updated statuses
        all_trades = trade_logger.load_trades(cfg)
        id_map     = {t['id']: t for t in updated_trades}
        all_trades = [id_map.get(t['id'], t) for t in all_trades]
        trade_logger.save_trades(all_trades, cfg)

        # Process each closed trade
        for t in closed_trades:
            new_balance = trade_logger.update_equity(t['pnl'], cfg)
            msg = content_generator.generate_trade_closed_alert(t, new_balance, cfg)
            notifier.send(msg, cfg)

    # ── 2. Scan for new signals ───────────────────────────────────────────────
    today_count = trade_logger.count_today_trades(cfg)
    if today_count >= cfg.MAX_TRADES_PER_DAY:
        logger.info(f"⏸ Daily trade limit reached ({cfg.MAX_TRADES_PER_DAY}). Skipping signal check.")
        return

    signals = market_scanner.scan_markets(cfg)

    for signal in signals:
        # Only take signals with ≥55% confidence
        if signal['confidence'] < 55:
            logger.info(f"⚡ Signal confidence too low ({signal['confidence']}%) – skipped.")
            continue

        _last_signal = signal

        # Notify via Telegram
        alert = content_generator.generate_signal_alert(signal, cfg)
        notifier.send(alert, cfg)

        # Open the trade
        equity = trade_logger.get_equity(cfg)
        trade  = trade_executor.open_trade(signal, equity['balance'], cfg)
        trade_logger.save_trade(trade, cfg)

        # Only one trade per scan cycle
        break


# ─────────────────────────────────────────────────────────────────────────────
# DAILY CONTENT CYCLE  (once per day)
# ─────────────────────────────────────────────────────────────────────────────

def run_daily_content():
    logger.info("━━━ DAILY CONTENT CYCLE ━━━━━━━━━━━━━━━━━━━━━━")

    stats = trade_logger.get_stats(cfg)

    # ── 1. Generate AI content ─────────────────────────────────────────────────
    logger.info("🤖 Generating content with Claude…")
    content = content_generator.generate_daily_content(stats, _last_signal, cfg)

    # ── 2. Create slides + video ───────────────────────────────────────────────
    logger.info("🎨 Creating visual content…")
    media = slide_creator.create_daily_content(stats, _last_signal, content, cfg)

    # ── 3. Post to all platforms ───────────────────────────────────────────────
    publish_results = social_publisher.publish_all(media, content, cfg)

    # ── 4. Send daily Telegram summary ─────────────────────────────────────────
    sym    = cfg.CURRENCY_SYMBOL
    s      = stats
    sign   = '+' if s['total_pnl'] >= 0 else ''
    ok_str = ', '.join(f"{k}: {'✅' if v else '❌'}" for k, v in publish_results.items())
    summary = (
        f"📅 *DAILY SUMMARY – Day {s['days_active']}*\n\n"
        f"Balance:    {sym}{s['balance']:.2f}\n"
        f"P&L today:  {sign}{sym}{s['total_pnl']:.2f}\n"
        f"Win rate:   {s['win_rate']}%\n"
        f"Trades:     {s['total_trades']}\n\n"
        f"Posts: {ok_str}\n\n"
        f"_{cfg.CHANNEL_NAME}_"
    )
    notifier.send(summary, cfg)

    # Also send the intro slide to Telegram for quick preview
    if media.get('thumbnail'):
        notifier.send_photo(media['thumbnail'], f"Day {s['days_active']} summary slide", cfg)

    logger.info("✅ Daily content cycle complete.")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER SETUP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Trading Bot starting…")
    logger.info(f"   Mode:            {'📝 PAPER TRADE' if cfg.PAPER_TRADE else '💰 LIVE TRADE'}")
    logger.info(f"   Capital:         £{cfg.INITIAL_CAPITAL}")
    logger.info(f"   Scan interval:   {cfg.SCAN_INTERVAL_MINUTES} min")
    logger.info(f"   Daily post hour: {cfg.DAILY_POST_HOUR}:00 UTC")
    logger.info(f"   Assets:          {cfg.CRYPTO_ASSETS + list(cfg.COMMODITY_ASSETS.keys())}")

    # Send startup notification
    notifier.send(
        f"🚀 *Bot Started*\n"
        f"Mode: {'Paper' if cfg.PAPER_TRADE else 'LIVE'}\n"
        f"Capital: £{cfg.INITIAL_CAPITAL}\n"
        f"Assets: {', '.join(cfg.CRYPTO_ASSETS + list(cfg.COMMODITY_ASSETS.keys()))}",
        cfg
    )

    # Run once immediately
    run_scan()

    # Schedule scan every N minutes
    schedule.every(cfg.SCAN_INTERVAL_MINUTES).minutes.do(run_scan)

    # Schedule daily content post
    post_time = f"{cfg.DAILY_POST_HOUR:02d}:00"
    schedule.every().day.at(post_time).do(run_daily_content)

    logger.info(f"📅 Scheduler active – scan every {cfg.SCAN_INTERVAL_MINUTES}min, post at {post_time} UTC")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
