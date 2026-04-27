"""
content_generator.py
--------------------
Uses Anthropic API to generate:
  - Video script (voiceover for the Reel)
  - Instagram caption + hashtags
  - YouTube title + description
  - TikTok caption
"""
import logging
import anthropic

logger = logging.getLogger(__name__)


def _call_claude(prompt: str, api_key: str, max_tokens: int = 1000) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg    = client.messages.create(
        model      = "claude-sonnet-4-20250514",
        max_tokens = max_tokens,
        messages   = [{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def generate_daily_content(stats: dict, recent_signal: dict | None, cfg) -> dict:
    """
    Generates all content for the daily post.
    Returns dict with: script, ig_caption, yt_title, yt_description, tiktok_caption
    """
    balance     = stats['balance']
    initial     = stats['initial']
    pnl         = stats['total_pnl']
    win_rate    = stats['win_rate']
    total       = stats['total_trades']
    days        = stats['days_active']
    sym         = cfg.CURRENCY_SYMBOL
    pnl_sign    = '+' if pnl >= 0 else ''
    emoji_trend = '📈' if pnl >= 0 else '📉'

    recent_txt = ''
    if stats.get('recent_trades'):
        lines = []
        for t in stats['recent_trades'][-3:]:
            icon = '✅' if t['result'] == 'WIN' else '❌'
            lines.append(f"  {icon} {t['asset']} {t['direction']} → {sym}{t['pnl']:+.2f}")
        recent_txt = '\n'.join(lines)

    signal_txt = ''
    if recent_signal:
        signal_txt = (f"Today's signal: {recent_signal['direction']} {recent_signal['asset']} "
                      f"@ {recent_signal['price']} | Confidence {recent_signal['confidence']}%")

    prompt = f"""You are the voice behind a viral Instagram/YouTube finance channel called "{cfg.CHANNEL_NAME}".
The creator started with {sym}{initial:.0f} and is documenting their trading journey publicly.
Today is Day {days} of the challenge.

STATS:
• Balance: {sym}{balance:.2f}
• P&L:     {pnl_sign}{sym}{pnl:.2f}
• Trades:  {total} total | Win rate: {win_rate}%
{signal_txt}

Recent trades:
{recent_txt if recent_txt else '  No trades yet today.'}

Generate the following — keep it authentic, conversational, and engaging:

1. VIDEO SCRIPT (30 seconds spoken, energetic, real, use "I" not "we"):
Write a voiceover script that hooks in 3 seconds, shows the numbers honestly, and ends with a CTA to follow.

2. INSTAGRAM CAPTION (max 150 words, with line breaks for readability):
Start with a hook line. Include key numbers. End with a question to drive comments. Add 15–20 relevant hashtags on a new line.

3. YOUTUBE TITLE (max 60 chars, include {sym} amount, clickable):

4. YOUTUBE DESCRIPTION (200 words max, include timestamps placeholder, links placeholder):

5. TIKTOK CAPTION (max 80 chars + 5 hashtags):

Format your response EXACTLY like this:
---SCRIPT---
[script here]
---IG_CAPTION---
[caption here]
---YT_TITLE---
[title here]
---YT_DESC---
[description here]
---TIKTOK---
[tiktok caption here]
"""

    try:
        raw = _call_claude(prompt, cfg.ANTHROPIC_API_KEY, max_tokens=1200)
        return _parse_content(raw, stats, cfg)
    except Exception as exc:
        logger.error(f"Content generation failed: {exc}")
        return _fallback_content(stats, cfg)


def _parse_content(raw: str, stats: dict, cfg) -> dict:
    sections = {
        'script':          _extract(raw, '---SCRIPT---',     '---IG_CAPTION---'),
        'ig_caption':      _extract(raw, '---IG_CAPTION---', '---YT_TITLE---'),
        'yt_title':        _extract(raw, '---YT_TITLE---',   '---YT_DESC---'),
        'yt_description':  _extract(raw, '---YT_DESC---',    '---TIKTOK---'),
        'tiktok_caption':  _extract(raw, '---TIKTOK---',     None),
    }
    return sections


def _extract(text: str, start_marker: str, end_marker: str | None) -> str:
    try:
        start = text.index(start_marker) + len(start_marker)
        if end_marker:
            end = text.index(end_marker, start)
            return text[start:end].strip()
        return text[start:].strip()
    except ValueError:
        return ''


def _fallback_content(stats: dict, cfg) -> dict:
    sym = cfg.CURRENCY_SYMBOL
    b   = stats['balance']
    p   = stats['total_pnl']
    d   = stats['days_active']
    sign = '+' if p >= 0 else ''

    return {
        'script':         f"Day {d} of the {sym}{stats['initial']:.0f} trading challenge. "
                          f"Balance is now {sym}{b:.2f}, that's {sign}{sym}{p:.2f}. "
                          f"Fully automated system doing all the work. Follow to watch it live.",
        'ig_caption':     f"Day {d} update 📊\n\nBalance: {sym}{b:.2f}\nP&L: {sign}{sym}{p:.2f}\n"
                          f"Win rate: {stats['win_rate']}%\n\n"
                          f"AI bot trading on my behalf 24/7 🤖\n\n"
                          f"Would you trust an AI with {sym}500? 👇\n\n"
                          f"#trading #crypto #gold #investing #forex #tradingbot #ai "
                          f"#makemoneyonline #passiveincome #ukfinance #stockmarket",
        'yt_title':       f"Day {d}: {sym}{b:.2f} | {cfg.CHANNEL_NAME}",
        'yt_description': f"Day {d} of the {sym}{stats['initial']:.0f} AI Trading Challenge.\n\n"
                          f"Starting balance: {sym}{stats['initial']:.0f}\n"
                          f"Current balance: {sym}{b:.2f}\n"
                          f"Total P&L: {sign}{sym}{p:.2f}\n\n"
                          f"Follow the full journey on Instagram: {cfg.CHANNEL_HANDLE}",
        'tiktok_caption': f"Day {d} AI trading update: {sym}{b:.2f} #trading #crypto #ai #money",
    }


def generate_signal_alert(signal: dict, cfg) -> str:
def generate_signal_alert(signal: dict, cfg) -> str:
    """Telegram notification when signal fires - shows leverage & expected profit."""
    sym     = cfg.CURRENCY_SYMBOL
    action  = "BUY" if signal["direction"] == "BUY" else "SELL"
    mode    = "PAPER" if cfg.PAPER_TRADE else "LIVE"
    lev     = signal.get("leverage", 1)
    exp_p   = signal.get("expected_profit", 0)
    max_l   = signal.get("max_loss", 0)
    strat   = signal.get("strategy", "SIGNAL")
    label   = signal.get("asset_label", signal["asset"])
    aemoji  = signal.get("asset_emoji", "")
    max_h   = signal.get("max_hours", 24)
    tp_pct  = signal.get("tp_pct", 0) * 100
    sl_pct  = signal.get("sl_pct", 0) * 100
    reasons = signal.get("strategy_reasons", [])
    why     = " | ".join(reasons[:2]) if reasons else "Technical signal"
    dir_arrow = "UP" if action == "BUY" else "DOWN"

    return (
        f"[{mode}] SIGNAL - {signal['confidence']}% confidence\n\n"
        f"{aemoji} {label}\n"
        f"Direction: {action} {dir_arrow}\n"
        f"Strategy:  {strat}\n"
        f"Entry:     {signal['price']}\n"
        f"Target:    {signal['take_profit']} (+{tp_pct:.2f}%)\n"
        f"Stop:      {signal['stop_loss']} (-{sl_pct:.2f}%)\n"
        f"Leverage:  {lev}x\n"
        f"If WIN:    +{sym}{exp_p:.2f}\n"
        f"If LOSS:   -{sym}{max_l:.2f}\n"
        f"Max hold:  {max_h}h\n"
        f"Why:       {why}\n"
        f"Time:      {signal['timestamp'][:19]} UTC"
    )

def generate_trade_closed_alert(trade: dict, balance: float, cfg) -> str:
    sym   = cfg.CURRENCY_SYMBOL
    icon  = '✅ WIN' if trade['result'] == 'WIN' else '❌ LOSS'
    pnl   = trade['pnl']
    mode  = 'PAPER' if trade.get('paper') else 'LIVE'

    return (
        f"{icon} *{mode} TRADE CLOSED*\n\n"
        f"*Asset:*   {trade['asset']}\n"
        f"*Direction:* {trade['direction']}\n"
        f"*Entry:*   {trade['entry_price']}\n"
        f"*Exit:*    {trade['exit_price']}\n"
        f"*P&L:*     {sym}{pnl:+.2f}\n"
        f"*Balance:* {sym}{balance:.2f}"
    )
