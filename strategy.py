"""
STRATEGY - Il "cervello" del bot.

Logica di ACQUISTO: scansiona le top 20, calcola RSI + trend (SMA50 vs SMA200),
sceglie le crypto piu' promettenti.

Logica di VENDITA (la parte "da analista" richiesta):
- Take profit fisso a +5% -> vende sempre.
- News fortemente negative -> vende sempre, a prescindere dal prezzo.
- Hard stop loss a -8% -> vende sempre (paracadute di sicurezza).
- Calo tra -3% e -8% -> NON vende automaticamente. Analizza:
    - trend di fondo (SMA200) ancora rialzista? 
    - volume di vendita debole (calo poco "supportato")?
    -> se si' a entrambe: HOLD (ritracciamento temporaneo), eventualmente BUY THE DIP
    -> se il trend si e' invertito al ribasso: SELL
"""

import logging
from config import (
    TAKE_PROFIT_PCT, SOFT_STOP_LOSS_PCT, HARD_STOP_LOSS_PCT,
    RSI_OVERSOLD, RSI_OVERBOUGHT, MAX_POSIZIONI_APERTE,
    QUOTA_MAX_PER_POSIZIONE, QUOTA_MIN_PER_POSIZIONE,
)
from indicators import build_technical_snapshot
from news_sentiment import get_negative_signals

logger = logging.getLogger("cryptobot.strategy")


def evaluate_buy_candidates(coins_with_history, portfolio, total_value):
    """
    coins_with_history: lista di dict {id, symbol, name, current_price, prices, volumes}
    Ritorna una lista ordinata di candidati BUY con un punteggio (score),
    scartando quelli con segnali negativi o gia' in portafoglio al massimo consentito.
    """
    candidates = []
    open_positions = len(portfolio["positions"])

    if open_positions >= MAX_POSIZIONI_APERTE:
        return []  # gia' al tetto massimo, non aprire nuove posizioni

    for coin in coins_with_history:
        coin_id = coin["id"]
        if coin_id in portfolio["positions"]:
            continue  # la gestione di posizioni esistenti e' in evaluate_sell

        snap = build_technical_snapshot(coin["prices"], coin["volumes"])
        if snap["rsi"] is None or snap["trend"] == "unknown":
            continue  # dati storici insufficienti, salta

        # controllo news negative anche prima di comprare
        has_negative, headlines = get_negative_signals(coin_id, coin["symbol"], coin["name"])
        if has_negative:
            continue

        # criteri di "probabilita' di salita":
        # 1) trend di fondo rialzista (SMA50 > SMA200)
        # 2) RSI in zona di ipervenduto o neutra-bassa (non comprare chi e' gia' ipercomprato)
        if snap["trend"] != "bullish":
            continue
        if snap["rsi"] >= RSI_OVERBOUGHT:
            continue

        # punteggio: piu' e' vicino/sotto la soglia di ipervenduto, meglio e';
        # premiamo anche la distanza percentuale tra SMA50 e SMA200 (forza del trend)
        rsi_score = max(0, RSI_OVERSOLD + 20 - snap["rsi"])  # piu' alto se RSI basso
        trend_strength = (snap["sma_short"] - snap["sma_long"]) / snap["sma_long"] * 100
        score = rsi_score + trend_strength

        candidates.append({
            "coin": coin,
            "snapshot": snap,
            "score": score,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    slots_available = MAX_POSIZIONI_APERTE - open_positions
    return candidates[:slots_available]


def size_position(total_value, cash_available, n_candidates_chosen):
    """
    Decide quanto investire in una posizione, rispettando i limiti min/max
    e senza svuotare la liquidità disponibile.
    """
    max_eur = total_value * QUOTA_MAX_PER_POSIZIONE
    min_eur = total_value * QUOTA_MIN_PER_POSIZIONE
    # dividi equamente il cash disponibile tra i candidati scelti in questo ciclo
    fair_share = cash_available / max(1, n_candidates_chosen)
    size = max(min_eur, min(max_eur, fair_share))
    return min(size, cash_available)


def evaluate_sell_or_hold(coin_id, coin_symbol, coin_name, position, current_price, prices, volumes):
    """
    Decide cosa fare con una posizione gia' aperta.
    Ritorna un dizionario: {action: 'SELL'|'HOLD'|'BUY_MORE', reason: str, urgency: str}
    """
    avg_price = position["avg_buy_price"]
    pnl_pct = (current_price - avg_price) / avg_price

    # 1) Controllo news negative: priorita' assoluta, vende sempre
    has_negative, headlines = get_negative_signals(coin_id, coin_symbol, coin_name)
    if has_negative:
        headline_preview = headlines[0] if headlines else "notizia negativa rilevata"
        return {
            "action": "SELL",
            "reason": f"Notizia fortemente negativa: \"{headline_preview}\"",
            "pnl_pct": pnl_pct * 100,
        }

    # 2) Take profit: vende sempre se raggiunto
    if pnl_pct >= TAKE_PROFIT_PCT:
        return {
            "action": "SELL",
            "reason": f"Take profit raggiunto (+{pnl_pct*100:.2f}%)",
            "pnl_pct": pnl_pct * 100,
        }

    # 3) Hard stop loss: paracadute di sicurezza, vende sempre
    if pnl_pct <= -HARD_STOP_LOSS_PCT:
        return {
            "action": "SELL",
            "reason": f"Stop loss di emergenza ({pnl_pct*100:.2f}%), perdita eccessiva",
            "pnl_pct": pnl_pct * 100,
        }

    # 4) Zona "soft stop loss" tra -3% e -8%: qui il bot fa l'analista
    if pnl_pct <= -SOFT_STOP_LOSS_PCT:
        snap = build_technical_snapshot(prices, volumes)

        if snap["trend"] == "unknown":
            # dati insufficienti per un giudizio informato -> prudenza, vendi
            return {
                "action": "SELL",
                "reason": f"Calo del {pnl_pct*100:.2f}% e dati insufficienti per valutare il trend di fondo",
                "pnl_pct": pnl_pct * 100,
            }

        trend_bullish = snap["trend"] == "bullish"
        volume_weak = snap["volume_weak"]  # True = vendite poco "convinte"

        if not trend_bullish:
            # il trend di lungo periodo si e' invertito: motivo valido per vendere
            return {
                "action": "SELL",
                "reason": f"Trend di fondo (SMA200) invertito al ribasso, calo del {pnl_pct*100:.2f}%",
                "pnl_pct": pnl_pct * 100,
            }

        # trend di fondo ancora rialzista
        if volume_weak:
            # calo poco supportato da volumi -> probabile ritracciamento temporaneo
            if snap["rsi"] is not None and snap["rsi"] < RSI_OVERSOLD:
                return {
                    "action": "BUY_MORE",
                    "reason": (f"Ritracciamento del {pnl_pct*100:.2f}% con trend di fondo rialzista, "
                               f"volumi di vendita deboli e RSI in ipervenduto ({snap['rsi']:.1f}): "
                               f"buy the dip"),
                    "pnl_pct": pnl_pct * 100,
                }
            return {
                "action": "HOLD",
                "reason": (f"Calo del {pnl_pct*100:.2f}% ma trend di fondo ancora rialzista "
                           f"e volumi di vendita deboli: probabile ritracciamento temporaneo"),
                "pnl_pct": pnl_pct * 100,
            }
        else:
            # trend ancora rialzista ma il calo e' supportato da volumi alti -> piu' cautela
            return {
                "action": "HOLD",
                "reason": (f"Calo del {pnl_pct*100:.2f}% con volumi piu' sostenuti, ma trend di fondo "
                           f"(SMA200) ancora rialzista: monitoraggio attivo, nessuna vendita"),
                "pnl_pct": pnl_pct * 100,
            }

    # 5) Nessuna soglia rilevante toccata
    return {
        "action": "HOLD",
        "reason": f"Posizione in linea ({pnl_pct*100:+.2f}%), nessuna soglia raggiunta",
        "pnl_pct": pnl_pct * 100,
    }
