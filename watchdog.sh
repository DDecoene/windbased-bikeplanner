#!/bin/sh
# Watchdog: controleert elke 60 seconden of backend en frontend gezond zijn.
# Stuurt Telegram alert bij statuswijziging (niet bij elke check).

BACKEND_URL="http://backend:8000/health"
FRONTEND_URL="http://frontend:3000"

backend_was_down=false
frontend_was_down=false

send_telegram() {
    msg="$1"
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        echo "[watchdog] Telegram niet geconfigureerd, skip alert: $msg"
        return
    fi
    curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"🚨 RGWND Watchdog\n\n${msg}\"}" \
        > /dev/null 2>&1
}

echo "[watchdog] Gestart, controleer elke 60 seconden..."

while true; do
    # Backend check
    if curl -sf "$BACKEND_URL" > /dev/null 2>&1; then
        if [ "$backend_was_down" = true ]; then
            send_telegram "✅ Backend is weer online"
            backend_was_down=false
        fi
    else
        if [ "$backend_was_down" = false ]; then
            send_telegram "❌ Backend is onbereikbaar ($BACKEND_URL)"
            backend_was_down=true
        fi
    fi

    # Frontend check
    if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
        if [ "$frontend_was_down" = true ]; then
            send_telegram "✅ Frontend is weer online"
            frontend_was_down=false
        fi
    else
        if [ "$frontend_was_down" = false ]; then
            send_telegram "❌ Frontend is onbereikbaar ($FRONTEND_URL)"
            frontend_was_down=true
        fi
    fi

    sleep 60
done
