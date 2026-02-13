"""
Telegram notificaties voor ops alerts.

Stuurt berichten naar een Telegram chat via de Bot API.
Silent no-op als de env vars niet geconfigureerd zijn (dev-modus).
Deduplicatie: identieke berichten worden max 1x per 5 minuten verstuurd.
"""

import os
import time

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Deduplicatie: {message_hash: timestamp}
_recent_alerts: dict[str, float] = {}
_DEDUP_SECONDS = 300  # 5 minuten


def send_alert(message: str) -> None:
    """Stuur een alert naar Telegram. No-op als niet geconfigureerd."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    # Deduplicatie
    now = time.time()
    if message in _recent_alerts:
        if now - _recent_alerts[message] < _DEDUP_SECONDS:
            return
    _recent_alerts[message] = now

    # Opruimen van oude entries
    expired = [k for k, v in _recent_alerts.items() if now - v > _DEDUP_SECONDS]
    for k in expired:
        del _recent_alerts[k]

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚨 RGWND Alert\n\n{message}",
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception:
        pass  # Telegram zelf is down — we loggen niet recursief
