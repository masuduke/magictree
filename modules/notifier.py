"""
notifier.py v2
---------------
Sends Telegram alerts for signals and trade closes.

Fix: parse_mode now defaults to None (plain text) instead of 'Markdown'.
The previous default broke whenever a message contained underscores
(e.g. 'EMA_TREND'), asterisks, or backticks, because Telegram tried to
parse them as Markdown formatting and rejected the whole message.

If you DO want bold/italic formatting in a specific message, pass
parse_mode='Markdown' or parse_mode='HTML' explicitly.
"""
import logging
import requests

logger = logging.getLogger(__name__)


def send(message: str, cfg, parse_mode=None) -> bool:
    """Send a Telegram message. Plain text by default (no Markdown parsing)."""
    token   = cfg.TELEGRAM_BOT_TOKEN
    chat_id = cfg.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        logger.debug("Telegram not configured - skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text':    message,
    }
    if parse_mode:
        payload['parse_mode'] = parse_mode

    try:
        r = requests.post(url, json=payload, timeout=10)
    except Exception as exc:
        logger.error(f"Telegram send exception: {exc}")
        return False

    if r.ok:
        return True
    logger.error(f"Telegram send failed: {r.text}")
    return False


def send_photo(image_path: str, caption: str, cfg) -> bool:
    """Send a photo with caption. Caption is plain text."""
    token   = cfg.TELEGRAM_BOT_TOKEN
    chat_id = cfg.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            r = requests.post(
                url,
                data={'chat_id': chat_id, 'caption': caption},
                files={'photo': photo},
                timeout=20,
            )
        return r.ok
    except Exception as exc:
        logger.error(f"Telegram photo failed: {exc}")
        return False
