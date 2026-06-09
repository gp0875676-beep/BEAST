"""
EXCHANGE DATA FETCHER
Supports: Gate.io, OKX, Binance (via ccxt)
Coins fetched directly from exchange — no CoinGecko dependency
"""

import ccxt
import pandas as pd
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


def fetch_top_coins_from_exchange(exchanges: Dict, limit: int = 1000) -> List[str]:
    """
    Get top coins by volume directly from connected exchanges.
    No CoinGecko needed — 100% reliable.
    """
    quote   = QUOTE_CURRENCY
    tickers = {}

    for ex_name, ex in exchanges.items():
        try:
            logger.info(f"Fetching tickers from {ex_name} …")
            all_tickers = ex.fetch_tickers()
            for sym, t in all_tickers.items():
                if not sym.endswith(f"/{quote}"):
                    continue
                base      = sym.replace(f"/{quote}", "")
                vol       = t.get("quoteVolume") or 0
                # Keep highest volume across exchanges
                if base not in tickers or vol > tickers[base]["vol"]:
                    tickers[base] = {"vol": vol, "exchange": ex_name, "ccxt_sym": sym}
        except Exception as e:
            logger.warning(f"Ticker fetch from {ex_name} failed: {e}")

    # Sort by volume, take top N
    sorted_coins = sorted(tickers.items(), key=lambda x: x[1]["vol"], reverse=True)
    top = sorted_coins[:limit]
    logger.info(f"Got {len(top)} coins from exchanges")
    return [c[0] for c in top]


def fetch_top_coins(limit: int = 1000) -> List[str]:
    """Alias — kept for compatibility."""
    return []   # Not used anymore — see get_tradeable_symbols_direct


def get_tradeable_symbols_direct(
    exchanges: Dict[str, ccxt.Exchange],
    limit: int = 1000,
    quote: str = QUOTE_CURRENCY
) -> List[Dict]:
    """
    Get top tradeable symbols by 24h volume directly from exchanges.
    Fast, reliable, no external API needed.
    """
    quote   = QUOTE_CURRENCY
    seen    = {}

    for ex_name, ex in exchanges.items():
        try:
            logger.info(f"Fetching tickers from {ex_name} …")
            all_tickers = ex.fetch_tickers()
            for sym, t in all_tickers.items():
                if not sym.endswith(f"/{quote}"):
                    continue
                base = sym.replace(f"/{quote}", "")
                vol  = float(t.get("quoteVolume") or 0)
                if vol < MIN_LIQUIDITY_USDT:
                    continue
                if base not in seen or vol > seen[base]["volume_usdt"]:
                    seen[base] = {
                        "symbol"     : base,
                        "exchange"   : ex_name,
                        "ccxt_symbol": sym,
                        "volume_usdt": vol,
                    }
        except Exception as e:
            logger.warning(f"Tickers from {ex_name} failed: {e}")

    # Sort by volume
    result = sorted(seen.values(), key=lambda x: x["volume_usdt"], reverse=True)
    logger.info(f"Total tradeable pairs: {len(result)}")
    return result[:limit]


# Keep old function name for compatibility
def get_tradeable_symbols(exchanges, coin_list, quote=QUOTE_CURRENCY) -> List[Dict]:
    """Redirect to direct method — ignores coin_list."""
    return get_tradeable_symbols_direct(exchanges, limit=1000, quote=quote)


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
        sym_to_use = ccxt_symbol
        if sym_to_use not in (ex.markets or {}):
            base = ccxt_symbol.split("/")[0]
            alt  = f"{base}/{QUOTE_CURRENCY}"
            if alt not in (ex.markets or {}):
                continue
            sym_to_use = alt
        try:
            raw = ex.fetch_ohlcv(sym_to_use, timeframe=timeframe, limit=limit)
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
            logger.debug(f"{name} error for {sym_to_use}: {e}")
        time.sleep(0.2)

    return None
