"""
content_generator.py v2 - Comprehensive Rewrite
------------------------------------------------
Generates Telegram alerts and daily social media content.

Fixes from v1:
  - Replaced 'cfg.CURRENCY_SYMBOL' (corrupted 'A£') with literal 'GBP'
  - Replaced corrupted UTF-8 emoji bytes with plain ASCII tags ([WIN]/[LOSS]/etc)
  - Removed Markdown asterisks (notifier is now plain-text by default)
  - Fixed signal dict key names: 'expected_loss' (was 'max_loss')
                                 removed 'strategy_reasons' (doesn't exist)
                                 use 'ai_reasoning' for the 'why' line
  - Cleaned up Instagram captions to remove garbled emoji bytes
  - Added defensive .get() for every dict access (no KeyErrors on edge cases)
"""
import logging
import anthropic

logger = logging.getLogger(__name__)


def _call_claude(prompt: str, api_key: str, max_tokens: int = 1000) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=max_tokens,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text


# -- Telegram alerts ----------------------------------------------------------

def generate_signal_alert(signal: dict, cfg) -> str:
    """Telegram message when a signal fires (a trade is about to open)."""
    action = signal.get('direction', 'BUY')
    mode   = 'PAPER' if cfg.PAPER_TRADE else 'LIVE'

    label    = signal.get('asset_label', signal.get('asset', '?'))
    asset    = signal.get('asset', '?')
    strategy = signal.get('strategy', 'EMA_TREND')
    lev      = signal.get('leverage', 1)
    price    = signal.get('price', 0)
    tp       = signal.get('take_profit', 0)
    sl       = signal.get('stop_loss', 0)
    tp_pct   = signal.get('tp_pct', 0) * 100
    sl_pct   = signal.get('sl_pct', 0) * 100
    max_h    = signal.get('max_hours', 24)
    conf     = signal.get('confidence', 0)
    exp_p    = signal.get('expected_profit', 0)
    exp_l    = signal.get('expected_loss', 0)
    regime   = signal.get('regime', 'neutral')
    why      = signal.get('ai_reasoning', 'Technical signal aligned with regime')

    arrow = 'UP' if action == 'BUY' else 'DOWN'

    return (
        f"[{mode}] SIGNAL - {conf}% confidence\n\n"
        f"Asset:     {label} ({asset})\n"
        f"Direction: {action} {arrow}\n"
        f"Strategy:  {strategy}\n"
        f"Regime:    {regime}\n"
        f"Entry:     {price}\n"
        f"Target:    {tp} (+{tp_pct:.2f}%)\n"
        f"Stop:      {sl} (-{sl_pct:.2f}%)\n"
        f"Leverage:  {lev}x\n"
        f"If WIN:    +GBP{exp_p:.2f}\n"
        f"If LOSS:   -GBP{exp_l:.2f}\n"
        f"Max hold:  {max_h}h\n"
        f"Why:       {why}\n"
        f"Time:      {signal.get('timestamp', '')[:19]} UTC"
    )


def generate_trade_closed_alert(trade: dict, balance: float, cfg) -> str:
    """Telegram message when a trade closes (TP / SL / TIME)."""
    result = trade.get('result', 'BREAKEVEN')
    tag    = '[WIN]' if result == 'WIN' else '[LOSS]' if result == 'LOSS' else '[EVEN]'
    mode   = 'PAPER' if trade.get('paper') else 'LIVE'

    asset     = trade.get('asset', '?')
    direction = trade.get('direction', '?')
    entry     = trade.get('entry_price', 0)
    exit_p    = trade.get('exit_price', 0)
    pnl       = trade.get('pnl', 0)
    reason    = trade.get('close_reason', '?')
    leverage  = trade.get('leverage', 1)
    capital   = trade.get('capital_before', 0)
    pnl_pct   = trade.get('pnl_pct', 0)

    return (
        f"{tag} {mode} TRADE CLOSED\n\n"
        f"Asset:     {asset}\n"
        f"Direction: {direction}\n"
        f"Entry:     {entry}\n"
        f"Exit:      {exit_p}\n"
        f"Reason:    {reason}\n"
        f"Leverage:  {leverage}x on GBP{capital:.2f}\n"
        f"PnL:       GBP{pnl:+.2f} ({pnl_pct:+.2f}%)\n"
        f"Balance:   GBP{balance:.2f}"
    )


# -- Social media daily content ----------------------------------------------

def generate_daily_content(stats: dict, recent_signal: dict | None, cfg) -> dict:
    """Generates the daily post bundle: video script, IG, YT, TikTok captions."""
    balance  = stats.get('balance', 0)
    initial  = stats.get('initial', 500)
    pnl      = stats.get('total_pnl', 0)
    win_rate = stats.get('win_rate', 0)
    total    = stats.get('total_trades', 0)
    days     = stats.get('days_active', 0)
    pnl_sign = '+' if pnl >= 0 else ''

    recent_txt = ''
    recent_trades = stats.get('recent_trades', [])
    if recent_trades:
        lines = []
        for t in recent_trades[-3:]:
            tag = '[WIN]' if t.get('result') == 'WIN' else '[LOSS]'
            asset = t.get('asset', '?')
            tdir  = t.get('direction', '?')
            tpnl  = t.get('pnl', 0)
            lines.append(f"  {tag} {asset} {tdir} -> GBP{tpnl:+.2f}")
        recent_txt = '\n'.join(lines)

    signal_txt = ''
    if recent_signal:
        sa  = recent_signal.get('asset', '?')
        sd  = recent_signal.get('direction', '?')
        sp  = recent_signal.get('price', 0)
        sc  = recent_signal.get('confidence', 0)
        signal_txt = f"Today's signal: {sd} {sa} @ {sp} | Confidence {sc}%"

    channel_name = getattr(cfg, 'CHANNEL_NAME', 'Trading Challenge')

    prompt = f"""You are the voice behind a viral Instagram/YouTube finance channel called "{channel_name}".
The creator started with GBP{initial:.0f} and is documenting their trading journey publicly.
Today is Day {days} of the challenge.

STATS:
- Balance: GBP{balance:.2f}
- P&L:     {pnl_sign}GBP{pnl:.2f}
- Trades:  {total} total | Win rate: {win_rate}%
{signal_txt}

Recent trades:
{recent_txt if recent_txt else '  No trades yet today.'}

Generate the following - keep it authentic, conversational, and engaging:

1. VIDEO SCRIPT (30 seconds spoken, energetic, real, use "I" not "we"):
Write a voiceover script that hooks in 3 seconds, shows the numbers honestly, and ends with a CTA to follow.

2. INSTAGRAM CAPTION (max 150 words, with line breaks):
Start with a hook line. Include key numbers. End with a question to drive comments. Add 15-20 relevant hashtags on a new line.

3. YOUTUBE TITLE (max 60 chars, include GBP amount, clickable):

4. YOUTUBE DESCRIPTION (200 words max, timestamps placeholder, links placeholder):

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
        api_key = getattr(cfg, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            logger.warning("No ANTHROPIC_API_KEY - using fallback content")
            return _fallback_content(stats, cfg)
        raw = _call_claude(prompt, api_key, max_tokens=1200)
        return _parse_content(raw)
    except Exception as exc:
        logger.error(f"Content generation failed: {exc}")
        return _fallback_content(stats, cfg)


def _parse_content(raw: str) -> dict:
    return {
        'script':         _extract(raw, '---SCRIPT---',     '---IG_CAPTION---'),
        'ig_caption':     _extract(raw, '---IG_CAPTION---', '---YT_TITLE---'),
        'yt_title':       _extract(raw, '---YT_TITLE---',   '---YT_DESC---'),
        'yt_description': _extract(raw, '---YT_DESC---',    '---TIKTOK---'),
        'tiktok_caption': _extract(raw, '---TIKTOK---',     None),
    }


def _extract(text: str, start_marker: str, end_marker) -> str:
    try:
        start = text.index(start_marker) + len(start_marker)
        if end_marker:
            end = text.index(end_marker, start)
            return text[start:end].strip()
        return text[start:].strip()
    except ValueError:
        return ''


def _fallback_content(stats: dict, cfg) -> dict:
    """Used when Claude API call fails - basic templated content."""
    b = stats.get('balance', 0)
    p = stats.get('total_pnl', 0)
    d = stats.get('days_active', 0)
    initial = stats.get('initial', 500)
    win_rate = stats.get('win_rate', 0)
    sign = '+' if p >= 0 else ''

    channel_name   = getattr(cfg, 'CHANNEL_NAME',   'Trading Challenge')
    channel_handle = getattr(cfg, 'CHANNEL_HANDLE', '@channel')

    return {
        'script': (
            f"Day {d} of the GBP{initial:.0f} trading challenge. "
            f"Balance is now GBP{b:.2f}, that is {sign}GBP{p:.2f} change. "
            f"Fully automated AI system doing all the work. Follow to watch it live."
        ),
        'ig_caption': (
            f"Day {d} update.\n\n"
            f"Balance: GBP{b:.2f}\n"
            f"P&L: {sign}GBP{p:.2f}\n"
            f"Win rate: {win_rate}%\n\n"
            f"AI bot trading on my behalf 24/7.\n\n"
            f"Would you trust an AI with GBP500?\n\n"
            f"#trading #crypto #gold #investing #forex #tradingbot #ai "
            f"#makemoneyonline #passiveincome #ukfinance #stockmarket"
        ),
        'yt_title': f"Day {d}: GBP{b:.2f} | {channel_name}",
        'yt_description': (
            f"Day {d} of the GBP{initial:.0f} AI Trading Challenge.\n\n"
            f"Starting balance: GBP{initial:.0f}\n"
            f"Current balance: GBP{b:.2f}\n"
            f"Total P&L: {sign}GBP{p:.2f}\n"
            f"Win rate: {win_rate}%\n\n"
            f"Follow the full journey on Instagram: {channel_handle}"
        ),
        'tiktok_caption': f"Day {d} AI trading update: GBP{b:.2f} #trading #crypto #ai #money",
    }
