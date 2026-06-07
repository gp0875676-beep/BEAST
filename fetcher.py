"""
=====================================================
  EXCHANGE DATA FETCHER
  Supports: Binance, Gate.io, OKX (via ccxt)
  - Top 1000 coins by market cap (CoinGecko)
  - OHLCV fetching with fallback across exchanges
=====================================================
"""

import ccxt
import pandas as pd
import numpy as np
import requests
import time
import logging
from typing import Optional, List, Dict
from config import (
    BINANCE_API_KEY, BINANCE_SECRET,
    GATE_API_KEY, GATE_SECRET,
    OKX_API_KEY, OKX_SECRET, OKX_PASSPHRASE,
    QUOTE_CURRENCY, MARKET_CAP_TOP, EXCHANGES,
    MIN_LIQUIDITY_USDT
)

logger = logging.getLogger("fetcher")


def init_exchanges() -> Dict[str, ccxt.Exchange]:
    exs = {}

    if "binance" in EXCHANGES:
        try:
            ex = ccxt.binance({
                "apiKey": BINANCE_API_KEY or None,
                "secret": BINANCE_SECRET or None,
                "options": {"defaultType": "spot"},
                "enableRateLimit": True,
            })
            ex.load_markets()
            exs["binance"] = ex
            logger.info("✅ Binance connected")
        except Exception as e:
            logger.warning(f"Binance init failed: {e}")

    if "gate" in EXCHANGES:
        try:
            ex = ccxt.gateio({
                "apiKey": GATE_API_KEY or None,
                "secret": GATE_SECRET or None,
                "enableRateLimit": True,
            })
            ex.load_markets()
            exs["gate"] = ex
            logger.info("✅ Gate.io connected")
        except Exception as e:
            logger.warning(f"Gate init failed: {e}")

    if "okx" in EXCHANGES:
        try:
            ex = ccxt.okx({
                "apiKey"    : OKX_API_KEY or None,
                "secret"    : OKX_SECRET or None,
                "password"  : OKX_PASSPHRASE or None,
                "enableRateLimit": True,
            })
            ex.load_markets()
            exs["okx"] = ex
            logger.info("✅ OKX connected")
        except Exception as e:
            logger.warning(f"OKX init failed: {e}")

    if not exs:
        raise RuntimeError("No exchanges connected — check config.py")

    return exs


def fetch_top_coins(limit: int = 1000) -> List[str]:
    """Fetch top coins by market cap from CoinGecko with retry + fallback."""
    symbols  = []
    per_page = 250
    pages    = (limit // per_page) + 1
    base_url = "https://api.coingecko.com/api/v3/coins/markets"
    headers  = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

    for page in range(1, pages + 1):
        for attempt in range(3):
            try:
                resp = requests.get(base_url, headers=headers, params={
                    "vs_currency": "usd",
                    "order"      : "market_cap_desc",
                    "per_page"   : per_page,
                    "page"       : page,
                    "sparkline"  : False,
                }, timeout=30)

                if resp.status_code == 429:
                    logger.warning("CoinGecko rate limit — waiting 60s")
                    time.sleep(60)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"CoinGecko HTTP {resp.status_code}")
                    time.sleep(10)
                    continue

                data = resp.json()
                if not isinstance(data, list):
                    break

                for coin in data:
                    sym = coin.get("symbol", "").upper()
                    if sym:
                        symbols.append(sym)

                logger.info(f"CoinGecko page {page}: {len(data)} coins (total {len(symbols)})")
                time.sleep(2.5)
                break

            except Exception as e:
                logger.warning(f"CoinGecko page {page} attempt {attempt+1}: {e}")
                time.sleep(15)

        if len(symbols) >= limit:
            break

    # Fallback if CoinGecko fails
    if len(symbols) < 10:
        logger.warning("CoinGecko failed — using hardcoded top 100 fallback")
        symbols = [
            "BTC","ETH","BNB","SOL","XRP","ADA","AVAX","DOGE","TRX","TON",
            "LINK","DOT","MATIC","SHIB","LTC","BCH","UNI","ATOM","XLM","ETC",
            "APT","FIL","HBAR","ICP","VET","ARB","OP","NEAR","ALGO","GRT",
            "AAVE","STX","FTM","SAND","MANA","AXS","CHZ","EGLD","FLOW","THETA",
            "XTZ","EOS","CAKE","NEO","ZEC","DASH","BAT","ENJ","ZIL","IOTA",
            "SUI","SEI","TIA","INJ","WLD","PEPE","FLOKI","BONK","WIF","JUP",
            "NOT","ZK","1INCH","COMP","MKR","SNX","YFI","SUSHI","CRV","DYDX",
            "RENDER","FET","OCEAN","AGIX","RNDR","IMX","LDO","RPL","SSV","PENDLE",
            "GMX","GNS","RDNT","VELA","HMX","MYRO","BOME","SLERF","MEW","POPCAT",
            "NEIRO","TURBO","MOG","BRETT","TOSHI","GIGA","PNUT","ACT","GOAT","MOODENG"
        ]

    return symbols[:limit]


def get_tradeable_symbols(
    exchanges: Dict[str, ccxt.Exchange],
    coin_list: List[str],
    quote: str = QUOTE_CURRENCY
) -> List[Dict]:
    tradeable = []
    seen      = set()

    for ex_name, ex in exchanges.items():
        markets = ex.markets or {}
        for coin in coin_list:
            ccxt_sym = f"{coin}/{quote}"
            if ccxt_sym not in markets:
                continue
            if coin in seen:
                continue
            market = markets[ccxt_sym]
            if not market.get("active", True):
                continue
            try:
                ticker   = ex.fetch_ticker(ccxt_sym)
                vol_usd  = ticker.get("quoteVolume", 0) or 0
                if vol_usd < MIN_LIQUIDITY_USDT:
                    continue
                tradeable.append({
                    "symbol"     : coin,
                    "exchange"   : ex_name,
                    "ccxt_symbol": ccxt_sym,
                    "volume_usdt": vol_usd,
                })
                seen.add(coin)
            except Exception:
                continue

    tradeable.sort(key=lambda x: x["volume_usdt"], reverse=True)
    return tradeable


def fetch_ohlcv(
    exchanges: Dict[str, ccxt.Exchange],
    ex_name: str,
    ccxt_symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
) -> Optional[pd.DataFrame]:
    exchange_order = [ex_name] + [e for e in exchanges if e != ex_name]

    for name in exchange_order:
        ex = exchanges.get(name)
        if not ex:
            continue
        if ccxt_symbol not in (ex.markets or {}):
            base = ccxt_symbol.split("/")[0]
            alt  = f"{base}/{QUOTE_CURRENCY}"
            if alt not in (ex.markets or {}):
                continue
            ccxt_symbol = alt
        try:
            raw = ex.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit)
            if not raw or len(raw) < 50:
                continue
            df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp").sort_index()
            for col in ["open","high","low","close","volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df.dropna(inplace=True)
            return df
        except Exception as e:
            logger.debug(f"{name} error for {ccxt_symbol}: {e}")
        time.sleep(0.2)

    return None


def batch_fetch_ohlcv(
    exchanges: Dict[str, ccxt.Exchange],
    coins: List[Dict],
    timeframe: str = "1h",
    limit: int = 300,
) -> Dict[str, pd.DataFrame]:
    result = {}
    for coin_info in coins:
        sym  = coin_info["symbol"]
        ex   = coin_info["exchange"]
        csym = coin_info["ccxt_symbol"]
        df   = fetch_ohlcv(exchanges, ex, csym, timeframe, limit)
        if df is not None and len(df) >= 220:
            result[sym] = df
        time.sleep(0.1)
    return result
