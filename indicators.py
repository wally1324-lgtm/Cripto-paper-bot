"""
INDICATORI TECNICI
Implementazione "pura" senza librerie esterne pesanti (solo numpy),
cosi' il deploy su hosting gratuito resta leggero.
"""

import numpy as np
from config import RSI_PERIOD, SMA_SHORT, SMA_LONG, VOLUME_DROP_THRESHOLD


def calculate_sma(prices, period):
    """Media mobile semplice sugli ultimi 'period' valori."""
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def calculate_rsi(prices, period=RSI_PERIOD):
    """
    RSI classico (Wilder). Richiede almeno period+1 prezzi.
    Ritorna un valore 0-100. >70 ipercomprato, <30 ipervenduto.
    """
    if len(prices) < period + 1:
        return None

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # smoothing alla Wilder per il resto della serie
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


def trend_direction(prices):
    """
    Determina il trend di fondo confrontando SMA50 vs SMA200.
    Ritorna: 'bullish', 'bearish', o 'unknown' (dati insufficienti).
    """
    sma_short = calculate_sma(prices, SMA_SHORT)
    sma_long = calculate_sma(prices, SMA_LONG)
    if sma_short is None or sma_long is None:
        return "unknown", None, None
    return ("bullish" if sma_short > sma_long else "bearish"), sma_short, sma_long


def volume_is_weak(volumes, lookback=20):
    """
    Confronta il volume odierno con la media dei volumi recenti.
    True = volume di oggi e' "debole" rispetto alla media
    (utile per capire se un calo di prezzo e' supportato da vendite forti o no).
    """
    if len(volumes) < lookback + 1:
        return None
    avg_volume = np.mean(volumes[-(lookback + 1):-1])
    today_volume = volumes[-1]
    if avg_volume == 0:
        return None
    return (today_volume / avg_volume) < VOLUME_DROP_THRESHOLD


def build_technical_snapshot(prices, volumes):
    """
    Raccoglie tutti gli indicatori in un unico dizionario,
    usato sia dalla logica di acquisto che da quella di vendita "intelligente".
    """
    rsi = calculate_rsi(prices)
    trend, sma_short, sma_long = trend_direction(prices)
    vol_weak = volume_is_weak(volumes)

    return {
        "rsi": rsi,
        "trend": trend,
        "sma_short": sma_short,
        "sma_long": sma_long,
        "volume_weak": vol_weak,
        "last_price": prices[-1] if prices else None,
    }
