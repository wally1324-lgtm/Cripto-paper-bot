"""
MAIN - Avvia il bot di paper trading.

Esegue in loop:
1. Ogni CHECK_INTERVAL_SECONDS: scarica dati di mercato, valuta posizioni esistenti
   (sell/hold/buy-the-dip) e valuta nuovi acquisti.
2. Una volta al giorno, all'ora configurata: invia il riepilogo serale.
"""

import logging
import time
from datetime import datetime, timezone

from config import (
    CHECK_INTERVAL_SECONDS, DAILY_SUMMARY_HOUR, BUDGET_INIZIALE,
)
import market_data
import portfolio as pf
import strategy
import telegram_notifier as tg
from commands import start_command_listener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cryptobot.main")

_last_summary_date = None


def fetch_coins_with_history(coins):
    """Arricchisce ogni coin con lo storico prezzi/volumi necessario per gli indicatori."""
    enriched = []
    for coin in coins:
        hist = market_data.get_ohlc_history(coin["id"])
        if not hist or len(hist["prices"]) < 30:
            logger.warning(f"Storico insufficiente per {coin['id']}, salto")
            continue
        enriched.append({
            "id": coin["id"],
            "symbol": coin["symbol"],
            "name": coin["name"],
            "current_price": coin["current_price"],
            "prices": hist["prices"],
            "volumes": hist["volumes"],
        })
        time.sleep(1.5)  # rispetta il rate limit gratuito di CoinGecko
    return enriched


def run_cycle():
    logger.info("=== Inizio ciclo di analisi ===")
    portfolio = pf.load_portfolio()

    coins = market_data.get_top_coins()
    if not coins:
        logger.error("Impossibile ottenere dati di mercato, salto questo ciclo")
        return

    coins_with_history = fetch_coins_with_history(coins)
    if not coins_with_history:
        logger.error("Nessun dato storico disponibile, salto questo ciclo")
        return

    price_lookup = {c["id"]: c["current_price"] for c in coins_with_history}
    by_id = {c["id"]: c for c in coins_with_history}

    # ---------- 1) GESTIONE POSIZIONI ESISTENTI ----------
    for coin_id in list(portfolio["positions"].keys()):
        coin_info = by_id.get(coin_id)
        if not coin_info:
            logger.warning(f"Nessun dato aggiornato per {coin_id} in questo ciclo, salto la valutazione")
            continue

        position = portfolio["positions"][coin_id]
        decision = strategy.evaluate_sell_or_hold(
            coin_id, coin_info["symbol"], coin_info["name"],
            position, coin_info["current_price"],
            coin_info["prices"], coin_info["volumes"],
        )

        if decision["action"] == "SELL":
            amount = position["amount"]
            proceeds = pf.close_position(portfolio, coin_id, coin_info["current_price"])
            tg.notify_sell(
                coin_info["name"], coin_info["symbol"], amount,
                coin_info["current_price"], proceeds, decision["pnl_pct"], decision["reason"],
            )
            pf.append_history({
                "action": "SELL", "coin_id": coin_id, "symbol": coin_info["symbol"],
                "amount": amount, "price": coin_info["current_price"],
                "proceeds": proceeds, "pnl_pct": decision["pnl_pct"], "reason": decision["reason"],
            })
            logger.info(f"SELL {coin_id}: {decision['reason']}")

        elif decision["action"] == "BUY_MORE":
            total_value = pf.total_portfolio_value(portfolio, price_lookup)
            eur_to_add = strategy.size_position(total_value, portfolio["cash_eur"], 1)
            if eur_to_add > 1 and portfolio["cash_eur"] >= eur_to_add:
                amount = eur_to_add / coin_info["current_price"]
                pf.open_or_increase_position(portfolio, coin_id, amount, coin_info["current_price"], eur_to_add)
                tg.notify_buy(
                    coin_info["name"], coin_info["symbol"], amount,
                    coin_info["current_price"], eur_to_add, "Buy the dip: " + decision["reason"],
                )
                pf.append_history({
                    "action": "BUY_MORE", "coin_id": coin_id, "symbol": coin_info["symbol"],
                    "amount": amount, "price": coin_info["current_price"],
                    "eur_spent": eur_to_add, "reason": decision["reason"],
                })
                logger.info(f"BUY_MORE {coin_id}: {decision['reason']}")
            else:
                logger.info(f"HOLD {coin_id} (liquidità insufficiente per incrementare)")

        else:  # HOLD
            logger.info(f"HOLD {coin_id}: {decision['reason']}")
            # Notifica solo se eravamo in zona di rischio (calo), per non spammare in continuazione
            if decision["pnl_pct"] <= -3.0:
                tg.notify_hold(coin_info["name"], coin_info["symbol"], decision["reason"])

        pf.save_portfolio(portfolio)

    # ---------- 2) VALUTAZIONE NUOVI ACQUISTI ----------
    total_value = pf.total_portfolio_value(portfolio, price_lookup)
    candidates = strategy.evaluate_buy_candidates(coins_with_history, portfolio, total_value)

    if candidates and portfolio["cash_eur"] > 5:
        for cand in candidates:
            coin = cand["coin"]
            eur_to_spend = strategy.size_position(total_value, portfolio["cash_eur"], len(candidates))
            if eur_to_spend < 1 or portfolio["cash_eur"] < eur_to_spend:
                continue

            amount = eur_to_spend / coin["current_price"]
            pf.open_or_increase_position(portfolio, coin["id"], amount, coin["current_price"], eur_to_spend)

            snap = cand["snapshot"]
            reason = (f"RSI {snap['rsi']:.1f}, trend rialzista "
                      f"(SMA50 > SMA200), score {cand['score']:.2f}")
            tg.notify_buy(coin["name"], coin["symbol"], amount, coin["current_price"], eur_to_spend, reason)
            pf.append_history({
                "action": "BUY", "coin_id": coin["id"], "symbol": coin["symbol"],
                "amount": amount, "price": coin["current_price"],
                "eur_spent": eur_to_spend, "reason": reason,
            })
            logger.info(f"BUY {coin['id']}: {reason}")
            pf.save_portfolio(portfolio)

    logger.info("=== Fine ciclo di analisi ===")


def maybe_send_daily_summary():
    global _last_summary_date
    now = datetime.now(timezone.utc)
    today = now.date()

    if now.hour == DAILY_SUMMARY_HOUR and _last_summary_date != today:
        portfolio = pf.load_portfolio()
        coins = market_data.get_top_coins()
        price_lookup = {c["id"]: c["current_price"] for c in coins}

        # per posizioni non più tra le top 20, recupera il prezzo singolarmente
        for coin_id in portfolio["positions"]:
            if coin_id not in price_lookup:
                p = market_data.get_current_price(coin_id)
                if p:
                    price_lookup[coin_id] = p

        total_value = pf.total_portfolio_value(portfolio, price_lookup)

        positions_detail = []
        for coin_id, pos in portfolio["positions"].items():
            price = price_lookup.get(coin_id)
            if not price:
                continue
            pnl_pct = (price - pos["avg_buy_price"]) / pos["avg_buy_price"] * 100
            positions_detail.append({
                "name": coin_id, "symbol": coin_id[:4],
                "pnl_pct": pnl_pct, "value": pos["amount"] * price,
            })

        tg.notify_daily_summary(portfolio, total_value, BUDGET_INIZIALE, positions_detail)
        _last_summary_date = today
        logger.info("Riepilogo serale inviato")


def main():
    logger.info("Avvio bot di paper trading...")
    start_command_listener()
    tg.notify_startup()

    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.exception("Errore nel ciclo principale")
            tg.notify_error(str(e))

        try:
            maybe_send_daily_summary()
        except Exception as e:
            logger.exception("Errore nell'invio del riepilogo")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
