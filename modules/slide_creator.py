"""
slide_creator.py
----------------
Creates visual slides and a 30-second Reel video from trade data.
Outputs:
  - slide_00_intro.png        → branding / day number
  - slide_01_signal.png       → trade signal details
  - slide_02_chart.png        → equity curve
  - slide_03_summary.png      → stats summary
  - reel_final.mp4            → assembled video (30s)
"""
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── colour palette ────────────────────────────────────────────────────────────
BG       = (10,  12,  20)
CARD     = (20,  24,  38)
GREEN    = (0,   224, 128)
RED      = (255, 80,  80)
GOLD     = (255, 200, 50)
WHITE    = (255, 255, 255)
GREY     = (140, 150, 170)
ACCENT   = (100, 120, 255)

W, H = 1080, 1920   # 9:16 for Reels

# ── font helper ───────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = False):
    """Returns PIL ImageFont – falls back to default if no TTF available."""
    from PIL import ImageFont
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _centered_text(draw, text: str, y: int, font, color, width: int = W):
    bb = draw.textbbox((0, 0), text, font=font)
    x  = (width - (bb[2] - bb[0])) // 2
    draw.text((x, y), text, font=font, fill=color)


def _rounded_rect(draw, xy, radius: int = 30, fill=CARD):
    from PIL import ImageDraw
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


# ── slide builders ────────────────────────────────────────────────────────────

def _slide_intro(stats: dict, cfg, out_path: str) -> str:
    from PIL import Image, ImageDraw
    img  = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    sym   = cfg.CURRENCY_SYMBOL
    day   = stats['days_active'] or 1
    pnl   = stats['total_pnl']
    bal   = stats['balance']
    color = GREEN if pnl >= 0 else RED
    sign  = '+' if pnl >= 0 else ''

    # Background gradient simulation
    for i in range(H):
        alpha = i / H
        r = int(BG[0] + (20 - BG[0]) * alpha)
        g = int(BG[1] + (10 - BG[1]) * alpha)
        b = int(BG[2] + (40 - BG[2]) * alpha)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # Top label
    _centered_text(draw, cfg.CHANNEL_NAME.upper(), 160, _font(44, True), GOLD)
    _centered_text(draw, cfg.CHANNEL_HANDLE, 220, _font(34), GREY)

    # Day badge
    _rounded_rect(draw, (W//2 - 160, 310, W//2 + 160, 420), fill=ACCENT)
    _centered_text(draw, f"DAY  {day}", 335, _font(56, True), WHITE)

    # Big balance
    _centered_text(draw, f"{sym}{bal:.2f}", 580, _font(130, True), WHITE)
    _centered_text(draw, "CURRENT BALANCE", 730, _font(38), GREY)

    # P&L pill
    pill_col = GREEN if pnl >= 0 else RED
    _rounded_rect(draw, (W//2 - 200, 810, W//2 + 200, 910), fill=pill_col)
    _centered_text(draw, f"{sign}{sym}{pnl:.2f}  ({sign}{stats['total_return']}%)",
                   830, _font(46, True), BG)

    # Stats row
    stats_y = 1050
    for label, val in [
        ('TRADES', str(stats['total_trades'])),
        ('WINS',   str(stats['wins'])),
        ('WIN %',  f"{stats['win_rate']}%"),
    ]:
        col_x = {'TRADES': 180, 'WINS': W//2, 'WIN %': W - 180}[label]
        draw.text((col_x - 60, stats_y), val,  font=_font(70, True), fill=WHITE)
        draw.text((col_x - 60, stats_y + 80), label, font=_font(32), fill=GREY)

    # Mode badge
    mode_text = '🟡 PAPER TRADING' if cfg.PAPER_TRADE else '🟢 LIVE TRADING'
    _centered_text(draw, mode_text, 1300, _font(38), GREY)

    # Footer
    ts = datetime.utcnow().strftime('%d %b %Y')
    _centered_text(draw, ts, H - 120, _font(34), GREY)
    _centered_text(draw, 'AI-powered • Fully automated', H - 80, _font(30), GREY)

    img.save(out_path)
    return out_path


def _slide_signal(signal: dict | None, cfg, out_path: str) -> str:
    from PIL import Image, ImageDraw
    img  = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    _centered_text(draw, "📡  SIGNAL DETECTED", 160, _font(60, True), GOLD)

    if signal is None:
        _centered_text(draw, "No signal today.", H // 2, _font(50), GREY)
        img.save(out_path)
        return out_path

    color = GREEN if signal['direction'] == 'BUY' else RED
    arrow = '▲  BUY' if signal['direction'] == 'BUY' else '▼  SELL'

    _rounded_rect(draw, (80, 300, W - 80, 500), fill=CARD)
    _centered_text(draw, signal['asset'], 320, _font(72, True), WHITE)
    _centered_text(draw, arrow, 410, _font(64, True), color)

    rows = [
        ('Entry price',    str(signal['price'])),
        ('Take profit',    str(signal['take_profit'])),
        ('Stop loss',      str(signal['stop_loss'])),
        ('RSI',            str(signal['rsi'])),
        ('Confidence',     f"{signal['confidence']}%"),
    ]
    y = 560
    for label, val in rows:
        _rounded_rect(draw, (80, y, W - 80, y + 110), fill=CARD)
        draw.text((120, y + 20), label, font=_font(38), fill=GREY)
        draw.text((120, y + 60), val,   font=_font(50, True), fill=WHITE)
        y += 130

    _centered_text(draw, 'EMA 9/21 Crossover  +  RSI Filter', H - 180, _font(34), GREY)
    _centered_text(draw, datetime.utcnow().strftime('%d %b %Y  %H:%M UTC'), H - 130, _font(30), GREY)

    img.save(out_path)
    return out_path


def _slide_chart(stats: dict, cfg, out_path: str) -> str:
    """Equity curve chart."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    history = stats.get('equity_history', [])
    sym     = cfg.CURRENCY_SYMBOL

    fig, ax = plt.subplots(figsize=(10.8, 19.2), dpi=100,
                           facecolor=tuple(c/255 for c in BG))
    ax.set_facecolor(tuple(c/255 for c in BG))

    if len(history) >= 2:
        dates    = [h['date'] for h in history]
        balances = [h['balance'] for h in history]
        xs       = list(range(len(dates)))
        color    = '#00e080' if balances[-1] >= balances[0] else '#ff5050'

        ax.fill_between(xs, balances, alpha=0.18, color=color)
        ax.plot(xs, balances, color=color, linewidth=4, zorder=5)
        ax.scatter([xs[-1]], [balances[-1]], color=color, s=180, zorder=6)

        # Reference line
        ax.axhline(cfg.INITIAL_CAPITAL, linestyle='--', color='#8c96aa', linewidth=1.5, alpha=0.6)
        ax.text(0.02, cfg.INITIAL_CAPITAL + (max(balances) - min(balances)) * 0.02,
                f'Start {sym}{cfg.INITIAL_CAPITAL:.0f}',
                color='#8c96aa', fontsize=22, transform=ax.get_yaxis_transform())

        step = max(1, len(xs) // 6)
        ax.set_xticks(xs[::step])
        ax.set_xticklabels([dates[i][-5:] for i in xs[::step]],
                            color='white', fontsize=18, rotation=30)
    else:
        ax.text(0.5, 0.5, 'Equity curve\ncoming soon…',
                ha='center', va='center', color='white', fontsize=36,
                transform=ax.transAxes)

    ax.set_title(f'{cfg.CHANNEL_NAME}\nEquity Curve', color='white', fontsize=40, pad=20)
    ax.yaxis.set_tick_params(labelcolor='white', labelsize=18)
    ax.spines[['top', 'right', 'bottom', 'left']].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.grid(axis='y', color='#1e2030', linewidth=1)

    plt.tight_layout(pad=3)
    plt.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()
    return out_path


def _slide_summary(stats: dict, cfg, out_path: str) -> str:
    from PIL import Image, ImageDraw
    img  = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    sym  = cfg.CURRENCY_SYMBOL

    _centered_text(draw, '📊  DAILY SUMMARY', 140, _font(60, True), GOLD)

    rows = [
        ('Starting capital',  f"{sym}{stats['initial']:.2f}"),
        ('Current balance',   f"{sym}{stats['balance']:.2f}"),
        ('Total profit/loss', f"{'+' if stats['total_pnl']>=0 else ''}{sym}{stats['total_pnl']:.2f}"),
        ('Return',            f"{'+' if stats['total_return']>=0 else ''}{stats['total_return']}%"),
        ('Total trades',      str(stats['total_trades'])),
        ('Win rate',          f"{stats['win_rate']}%"),
        ('Days active',       str(stats['days_active'])),
    ]

    y = 300
    for label, val in rows:
        val_color = (GREEN if ('+' in val or (val.replace(sym, '').replace('.','').replace('%','').lstrip('-').isdigit()
                                              and float(val.replace(sym,'').replace('%','').replace('+','')) >= 0))
                     else RED) if any(c in val for c in ['+', '-', '%']) else WHITE
        if label in ('Starting capital', 'Current balance', 'Total trades', 'Days active', 'Win rate'):
            val_color = WHITE
        _rounded_rect(draw, (60, y, W - 60, y + 120), fill=CARD)
        draw.text((110, y + 15), label, font=_font(38), fill=GREY)
        draw.text((110, y + 60), val,   font=_font(54, True), fill=val_color)
        y += 140

    # Recent trades
    if stats.get('recent_trades'):
        _centered_text(draw, 'RECENT TRADES', y + 20, _font(38, True), GOLD)
        y += 80
        for t in stats['recent_trades'][-3:]:
            icon  = '✅' if t['result'] == 'WIN' else '❌'
            line  = f"{icon}  {t['asset']}  {t['direction']}  {sym}{t['pnl']:+.2f}"
            color = GREEN if t['result'] == 'WIN' else RED
            _centered_text(draw, line, y, _font(38), color)
            y += 60

    _centered_text(draw, cfg.CHANNEL_HANDLE, H - 100, _font(38, True), ACCENT)
    _centered_text(draw, 'Follow the journey 🚀', H - 60, _font(32), GREY)

    img.save(out_path)
    return out_path


# ── video assembler ───────────────────────────────────────────────────────────

def _make_video(slide_paths: list[str], script: str, out_path: str) -> str | None:
    try:
        from moviepy.editor import (ImageClip, concatenate_videoclips,
                                    AudioFileClip, CompositeVideoClip, TextClip)
        clips = []
        duration_each = 7  # seconds per slide

        for path in slide_paths:
            clip = ImageClip(path).set_duration(duration_each)
            clips.append(clip)

        video = concatenate_videoclips(clips, method='compose')
        video.write_videofile(
            out_path,
            fps=24, codec='libx264', audio=False,
            preset='ultrafast', logger=None
        )
        return out_path
    except Exception as exc:
        logger.warning(f"Video creation skipped (moviepy/ffmpeg issue): {exc}")
        return None


# ── public API ────────────────────────────────────────────────────────────────

def create_daily_content(stats: dict, signal: dict | None, content: dict, cfg) -> dict:
    """
    Generates all slides and a video.
    Returns dict with file paths.
    """
    day   = stats.get('days_active', 1)
    base  = Path(cfg.SLIDES_DIR)
    base.mkdir(parents=True, exist_ok=True)
    Path(cfg.VIDEOS_DIR).mkdir(parents=True, exist_ok=True)

    prefix = base / f"day{day:04d}"

    paths = {
        'intro':   str(prefix) + '_00_intro.png',
        'signal':  str(prefix) + '_01_signal.png',
        'chart':   str(prefix) + '_02_chart.png',
        'summary': str(prefix) + '_03_summary.png',
    }

    logger.info("🎨 Creating slides…")
    try:
        _slide_intro(stats, cfg, paths['intro'])
        _slide_signal(signal, cfg, paths['signal'])
        _slide_chart(stats, cfg, paths['chart'])
        _slide_summary(stats, cfg, paths['summary'])
    except Exception as exc:
        logger.error(f"Slide creation error: {exc}")

    slide_list = [paths['intro'], paths['signal'], paths['chart'], paths['summary']]

    video_path = str(Path(cfg.VIDEOS_DIR) / f"day{day:04d}_reel.mp4")
    logger.info("🎬 Assembling video…")
    result = _make_video(slide_list, content.get('script', ''), video_path)

    return {
        'slides':     slide_list,
        'video':      result,
        'thumbnail':  paths['intro'],
    }
