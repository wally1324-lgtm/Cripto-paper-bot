"""
CONFIGURAZIONE DEL BOT
Tutti i parametri della strategia sono qui, cosi' puoi modificarli
senza toccare il resto del codice.
"""

import os

# ============== TELEGRAM ==============
# Le prendi da @BotFather (token) e @userinfobot (chat id) - vedi guida
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "INSERISCI_QUI_IL_TUO_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "INSERISCI_QUI_IL_TUO_CHAT_ID")

# ============== NEWS API ==============
# CryptoCompare ha un tier gratuito senza nemmeno serve key per le news base
CRYPTOCOMPARE_API_KEY = os.environ.get("CRYPTOCOMPARE_API_KEY", "")  # opzionale

# ============== BUDGET E PORTAFOGLIO ==============
BUDGET_INIZIALE = 100.0          # euro virtuali di partenza
MAX_POSIZIONI_APERTE = 5         # tetto di sicurezza, il bot decide quante aprirne fino a qui
QUOTA_MAX_PER_POSIZIONE = 0.35   # max 35% del capitale totale su una singola crypto
QUOTA_MIN_PER_POSIZIONE = 0.10   # min 10% per evitare posizioni "spazzatura"

# ============== UNIVERSO DI INVESTIMENTO ==============
TOP_N_CRYPTO = 20                # scansiona le prime 20 per market cap
STABLECOIN_BLACKLIST = [         # le stablecoin non vanno "comprate per salire"
    "tether", "usd-coin", "dai", "true-usd", "first-digital-usd",
    "usdd", "frax", "paypal-usd", "ethena-usde", "binance-usd"
]

# ============== INDICATORI TECNICI ==============
RSI_PERIOD = 14
RSI_OVERSOLD = 30        # sotto questa soglia = ipervenduto -> possibile BUY
RSI_OVERBOUGHT = 70      # sopra questa soglia = ipercomprato -> evita BUY

SMA_SHORT = 50            # media mobile breve (trend medio periodo)
SMA_LONG = 200             # media mobile lunga (trend di fondo / lungo periodo)

# ============== GESTIONE DEL RISCHIO ==============
TAKE_PROFIT_PCT = 0.05        # +5% -> vendi e incassa
SOFT_STOP_LOSS_PCT = 0.03     # -3% -> NON vendita automatica, scatta l'analisi "da analista"
HARD_STOP_LOSS_PCT = 0.08     # -8% -> vendita FORZATA qualunque sia il trend (paracadute)

VOLUME_DROP_THRESHOLD = 0.7   # se il volume di vendita corrente è < 70% della media,
                                # consideriamo il calo "poco supportato" -> probabile ritracciamento

# ============== SENTIMENT / NEWS ==============
NEGATIVE_KEYWORDS = [
    "hacked", "hack", "exploit", "banned", "ban", "scam", "fraud",
    "crash", "collapse", "lawsuit", "sec charges", "rug pull",
    "insolvent", "bankruptcy", "halted", "delisted", "investigation"
]
NEWS_LOOKBACK_HOURS = 6   # considera solo notizie delle ultime N ore

# ============== TIMING ==============
CHECK_INTERVAL_SECONDS = 5 * 60   # ogni 5 minuti controlla il mercato
DAILY_SUMMARY_HOUR = 21            # ora (24h, ora del server!) per il riepilogo serale

# ============== FILE DATI ==============
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "trade_history.json"

# ============== API ENDPOINTS ==============
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
CRYPTOCOMPARE_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/"
