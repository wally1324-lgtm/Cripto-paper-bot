"""
PORTFOLIO - Stato del paper trading, salvato su file JSON
cosi' sopravvive ai riavvii del bot.
"""

import json
import os
import logging
from datetime import datetime, timezone
from config import PORTFOLIO_FILE, HISTORY_FILE, BUDGET_INIZIALE

logger = logging.getLogger("cryptobot.portfolio")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        portfolio = {
            "cash_eur": BUDGET_INIZIALE,
            "positions": {},   # coin_id -> {amount, avg_buy_price, opened_at}
            "created_at": _now_iso(),
        }
        save_portfolio(portfolio)
        return portfolio

    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)


def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def append_history(entry):
    history = load_history()
    entry["timestamp"] = _now_iso()
    history.append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def total_portfolio_value(portfolio, current_prices):
    """
    current_prices: dict coin_id -> prezzo attuale in EUR
    Ritorna il valore totale (cash + posizioni valorizzate al prezzo corrente).
    """
    total = portfolio["cash_eur"]
    for coin_id, pos in portfolio["positions"].items():
        price = current_prices.get(coin_id)
        if price:
            total += pos["amount"] * price
    return total


def open_or_increase_position(portfolio, coin_id, amount, price, eur_spent):
    pos = portfolio["positions"].get(coin_id)
    if pos:
        # media il prezzo di carico se incrementiamo (buy the dip)
        total_amount = pos["amount"] + amount
        total_cost = (pos["amount"] * pos["avg_buy_price"]) + eur_spent
        pos["avg_buy_price"] = total_cost / total_amount
        pos["amount"] = total_amount
    else:
        portfolio["positions"][coin_id] = {
            "amount": amount,
            "avg_buy_price": price,
            "opened_at": _now_iso(),
        }
    portfolio["cash_eur"] -= eur_spent


def close_position(portfolio, coin_id, price):
    pos = portfolio["positions"].pop(coin_id, None)
    if not pos:
        return 0.0
    proceeds = pos["amount"] * price
    portfolio["cash_eur"] += proceeds
    return proceeds
