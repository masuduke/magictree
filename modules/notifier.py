"""
notifier.py
-----------
Sends Telegram alerts for signals and trade closes.
"""
import logging
import requests

logger = logging.getLogger(__name__)


def send(message: str, cfg, parse_mode: str = 'Markdown') -> bool:
    token   = cfg.TELEGRAM_BOT_TOKEN
    chat_id = cfg.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("Telegram not configured – skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r   = requests.post(url, json={
        'chat_id':    chat_id,
        'text':       message,
        'parse_mode': parse_mode,
    }, timeout=10)

    if r.ok:
        return True
    logger.error(f"Telegram send failed: {r.text}")
    return False


def send_photo(image_path: str, caption: str, cfg) -> bool:
    token   = cfg.TELEGRAM_BOT_TOKEN
    chat_id = cfg.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(image_path, 'rb') as photo:
            r = requests.post(url, data={'chat_id': chat_id, 'caption': caption},
                              files={'photo': photo}, timeout=20)
        return r.ok
    except Exception as exc:
        logger.error(f"Telegram photo failed: {exc}")
        return False
