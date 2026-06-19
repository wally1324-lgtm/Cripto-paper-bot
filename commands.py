"""
COMMAND LISTENER
Gira in un thread separato e risponde a comandi inviati dal tuo telefono:
/status -> stato attuale del portafoglio
/saldo  -> alias di /status
/help   -> elenco comandi

Usa long polling (getUpdates), nessun webhook/server necessario.
"""

import requests
import logging
import threading
import time

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BUDGET_INIZIALE
import portfolio as pf
import market_data
import telegram_notifier as tg

logger = logging.getLogger("cryptobot.commands")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def handle_status_command():
    portfolio = pf.load_portfolio()
    coins = market_data.get_top_coins()
    price_lookup = {c["id"]: c["current_price"] for c in coins}

    for coin_id in portfolio["positions"]:
        if coin_id not in price_lookup:
            p = market_data.get_current_price(coin_id)
            if p:
                price_lookup[coin_id] = p

    total_value = pf.total_portfolio_value(portfolio, price_lookup)
    pnl = total_value - BUDGET_INIZIALE
    pnl_pct = (pnl / BUDGET_INIZIALE) * 100

    lines = [
        "📊 *STATO ATTUALE*",
        f"Valore totale: €{total_value:.2f}",
        f"P&L: {pnl:+.2f}€ ({pnl_pct:+.2f}%)",
        f"Liquidità: €{portfolio['cash_eur']:.2f}",
        "",
        "*Posizioni:*",
    ]
    if not portfolio["positions"]:
        lines.append("Nessuna posizione aperta al momento")
    else:
        for coin_id, pos in portfolio["positions"].items():
            price = price_lookup.get(coin_id)
            if not price:
                continue
            pnl_pos = (price - pos["avg_buy_price"]) / pos["avg_buy_price"] * 100
            value = pos["amount"] * price
            lines.append(f"• {coin_id}: {pnl_pos:+.2f}% — €{value:.2f}")

    tg.send_message("\n".join(lines))


def handle_help_command():
    tg.send_message(
        "*Comandi disponibili:*\n"
        "/status oppure /saldo — stato attuale del portafoglio\n"
        "/help — questo messaggio"
    )


def poll_commands():
    """Loop infinito in un thread separato, controlla nuovi messaggi ogni 3 secondi."""
    last_update_id = None
    while True:
        try:
            params = {"timeout": 20}
            if last_update_id:
                params["offset"] = last_update_id + 1

            resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=25)
            resp.raise_for_status()
            updates = resp.json().get("result", [])

            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").strip().lower()

                if chat_id != str(TELEGRAM_CHAT_ID):
                    continue  # ignora messaggi da chat diverse dalla tua

                if text in ("/status", "/saldo"):
                    handle_status_command()
                elif text == "/help" or text == "/start":
                    handle_help_command()

        except Exception as e:
            logger.error(f"Errore nel polling comandi: {e}")
            time.sleep(5)


def start_command_listener():
    thread = threading.Thread(target=poll_commands, daemon=True)
    thread.start()
    logger.info("Listener comandi Telegram avviato")
