"""
TELEGRAM NOTIFIER
Invio messaggi semplici via Bot API (no librerie esterne necessarie).
"""

import requests
import logging
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("cryptobot.telegram")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def send_message(text):
    try:
        resp = requests.post(
            API_URL,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"Telegram error {resp.status_code}: {resp.text}")
    except requests.RequestException as e:
        logger.error(f"Errore invio Telegram: {e}")


def notify_buy(coin_name, symbol, amount, price, eur_spent, reason):
    send_message(
        f"🟢 *ACQUISTO* — {coin_name} ({symbol.upper()})\n"
        f"Quantità: {amount:.6f}\n"
        f"Prezzo: €{price:.4f}\n"
        f"Speso: €{eur_spent:.2f}\n"
        f"Motivo: {reason}"
    )


def notify_sell(coin_name, symbol, amount, price, proceeds, pnl_pct, reason):
    emoji = "✅" if pnl_pct >= 0 else "🔴"
    send_message(
        f"{emoji} *VENDITA* — {coin_name} ({symbol.upper()})\n"
        f"Quantità: {amount:.6f}\n"
        f"Prezzo: €{price:.4f}\n"
        f"Incassato: €{proceeds:.2f}\n"
        f"P&L: {pnl_pct:+.2f}%\n"
        f"Motivo: {reason}"
    )


def notify_hold(coin_name, symbol, reason):
    send_message(
        f"🟡 *HOLD* — {coin_name} ({symbol.upper()})\n"
        f"In calo ma mantenuta: {reason}"
    )


def notify_daily_summary(portfolio, total_value, budget_iniziale, positions_detail):
    pnl = total_value - budget_iniziale
    pnl_pct = (pnl / budget_iniziale) * 100

    lines = [
        "📊 *RIEPILOGO SERALE*",
        f"Valore totale: €{total_value:.2f}",
        f"P&L totale: {pnl:+.2f}€ ({pnl_pct:+.2f}%)",
        f"Liquidità: €{portfolio['cash_eur']:.2f}",
        "",
        "*Posizioni aperte:*",
    ]
    if not positions_detail:
        lines.append("Nessuna")
    else:
        for d in positions_detail:
            lines.append(
                f"• {d['name']} ({d['symbol'].upper()}): {d['pnl_pct']:+.2f}% "
                f"— €{d['value']:.2f}"
            )
    send_message("\n".join(lines))


def notify_error(text):
    send_message(f"⚠️ *Errore bot:* {text}")


def notify_startup():
    send_message("🤖 Bot di Paper Trading avviato e operativo!")
