"""
=====================================
  CRYPTO PUMP SCANNER - CONFIG FILE
=====================================
Fill in your API keys here before running.
"""

# ─── TELEGRAM ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"       # Get from @BotFather
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID_HERE"         # Your chat/channel ID

# ─── EXCHANGE API KEYS (optional – read-only public data works without keys) ──
BINANCE_API_KEY    = ""
BINANCE_SECRET     = ""

GATE_API_KEY       = ""
GATE_SECRET        = ""

OKX_API_KEY        = ""
OKX_SECRET         = ""
OKX_PASSPHRASE     = ""

# ─── SCANNER SETTINGS ────────────────────────────────────────
SCAN_INTERVAL_MINUTES  = 5          # How often to scan (minutes)
TOP_N_COINS            = 10         # Top N coins to report per scan
MARKET_CAP_TOP         = 1000       # Scan top N coins by market cap
TIMEFRAMES             = ["15m", "1h", "4h"]   # Candle timeframes to analyse
PRIMARY_TIMEFRAME      = "1h"       # Main decision timeframe
QUOTE_CURRENCY         = "USDT"

# ─── SCORING THRESHOLDS ──────────────────────────────────────
MIN_SIGNAL_SCORE       = 5.5        # Minimum score out of 10 to include in report
RSI_OVERSOLD           = 35
RSI_OVERBOUGHT         = 65
RSI_PUMP_ZONE          = 50         # RSI crossing above this = bullish
VOLUME_SURGE_MULT      = 1.8        # Volume must be X times 20-period avg
MIN_LIQUIDITY_USDT     = 500_000    # Minimum 24h volume in USDT

# ─── EXCHANGES TO USE ────────────────────────────────────────
EXCHANGES = ["binance", "gate", "okx"]   # Will try all; use first that works
