"""
NEWS / SENTIMENT
Usa l'API gratuita di CryptoCompare (non serve nemmeno una key per l'uso base,
ma se ne hai una la puoi mettere in config.py per limiti piu' alti).
"""

import requests
import logging
import time
from datetime import datetime, timezone, timedelta
from config import CRYPTOCOMPARE_NEWS_URL, CRYPTOCOMPARE_API_KEY, NEGATIVE_KEYWORDS, NEWS_LOOKBACK_HOURS

logger = logging.getLogger("cryptobot.news")

_news_cache = {"timestamp": 0, "data": []}
CACHE_TTL = 300  # 5 minuti, evita di martellare l'API ad ogni coin nello stesso ciclo


def _fetch_news():
    """Scarica le news recenti, con piccola cache per non sprecare richieste."""
    now = time.time()
    if now - _news_cache["timestamp"] < CACHE_TTL and _news_cache["data"]:
        return _news_cache["data"]

    params = {"lang": "EN"}
    headers = {}
    if CRYPTOCOMPARE_API_KEY:
        headers["authorization"] = f"Apikey {CRYPTOCOMPARE_API_KEY}"

    try:
        resp = requests.get(CRYPTOCOMPARE_NEWS_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("Data", [])
        _news_cache["timestamp"] = now
        _news_cache["data"] = data
        return data
    except requests.RequestException as e:
        logger.error(f"Errore fetch news: {e}")
        return _news_cache["data"]  # ritorna la cache vecchia piuttosto che niente


def get_negative_signals(coin_id, coin_symbol, coin_name):
    """
    Controlla se ci sono notizie recenti e negative che menzionano questa crypto.
    Ritorna (has_negative_news: bool, matched_headlines: list[str])
    """
    news = _fetch_news()
    if not news:
        return False, []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    matched = []

    search_terms = {coin_symbol.lower(), coin_name.lower(), coin_id.lower()}

    for item in news:
        try:
            published = datetime.fromtimestamp(item.get("published_on", 0), tz=timezone.utc)
        except (ValueError, OSError):
            continue
        if published < cutoff:
            continue

        title = item.get("title", "").lower()
        body_categories = item.get("categories", "").lower()

        # la notizia deve riguardare la coin (titolo o categorie) E contenere parole negative
        mentions_coin = any(term in title or term in body_categories for term in search_terms)
        if not mentions_coin:
            continue

        if any(neg_word in title for neg_word in NEGATIVE_KEYWORDS):
            matched.append(item.get("title"))

    return (len(matched) > 0), matched
