"""
MARKET DATA - Tutto cio' che serve da CoinGecko:
- lista delle top 20 crypto
- storico prezzi/volumi per calcolare gli indicatori
"""

import requests
import time
import logging
from config import COINGECKO_BASE, TOP_N_CRYPTO, STABLECOIN_BLACKLIST

logger = logging.getLogger("cryptobot.market")

HEADERS = {"User-Agent": "Mozilla/5.0 (PaperTradingBot/1.0)"}


def _get(url, params=None, retries=3):
    """Wrapper con retry e rispetto del rate limit gratuito di CoinGecko."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                logger.warning(f"Rate limit CoinGecko, attendo {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Errore richiesta CoinGecko ({attempt+1}/{retries}): {e}")
            time.sleep(5)
    return None


def get_top_coins():
    """
    Ritorna le prime TOP_N_CRYPTO crypto per market cap,
    escluse le stablecoin (non hanno senso in una strategia 'punta a salire').
    """
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "eur",
        "order": "market_cap_desc",
        "per_page": TOP_N_CRYPTO + 10,  # margine extra perche' filtriamo le stablecoin
        "page": 1,
        "sparkline": "false",
    }
    data = _get(url, params)
    if not data:
        return []

    coins = [c for c in data if c["id"] not in STABLECOIN_BLACKLIST]
    return coins[:TOP_N_CRYPTO]


def get_ohlc_history(coin_id, days=210):
    """
    Storico prezzi giornalieri (close) per calcolare SMA200 e RSI.
    CoinGecko market_chart ritorna [timestamp, price] a granularita' giornaliera per days>90.
    """
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "eur", "days": days, "interval": "daily"}
    data = _get(url, params)
    if not data or "prices" not in data:
        return None

    prices = [p[1] for p in data["prices"]]
    volumes = [v[1] for v in data.get("total_volumes", [])]
    return {"prices": prices, "volumes": volumes}


def get_current_price(coin_id):
    url = f"{COINGECKO_BASE}/simple/price"
    params = {"ids": coin_id, "vs_currencies": "eur"}
    data = _get(url, params)
    if not data or coin_id not in data:
        return None
    return data[coin_id]["eur"]
