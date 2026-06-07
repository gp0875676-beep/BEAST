"""
=====================================================
  CRYPTO PUMP SCANNER - MAIN ORCHESTRATOR
  Run: python main.py
  
  Flow every 5 minutes:
  1. Fetch top 1000 coins by market cap (CoinGecko)
  2. Filter to tradeable pairs on Binance/Gate/OKX
  3. Fetch OHLCV on multiple timeframes
  4. Score every coin across 20+ metrics
  5. Pick top 10 by pump_score
  6. Send formatted signals to Telegram
=====================================================
"""

import time
import logging
import threading
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

from config import (
    SCAN_INTERVAL_MINUTES, TOP_N_COINS, MARKET_CAP_TOP,
    TIMEFRAMES, PRIMARY_TIMEFRAME, MIN_SIGNAL_SCORE, QUOTE_CURRENCY
)
from fetcher  import init_exchanges, fetch_top_coins, get_tradeable_symbols, batch_fetch_ohlcv
from analysis import compute_full_score
from notifier import send_scan_results

# ─── Logging Setup ───────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pump_scanner.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("main")


# ─────────────────────────────────────────────
#  MULTI-TIMEFRAME SCORING
# ─────────────────────────────────────────────

def score_with_multi_tf(
    exchanges: dict,
    coins: List[Dict],
    timeframes: List[str],
    primary: str
) -> List[Dict]:
    """
    Score each coin across all timeframes.
    Primary TF gets 60% weight, others split the rest.
    """
    results = []
    tf_weights = {}
    n_tf = len(timeframes)
    for tf in timeframes:
        tf_weights[tf] = 0.6 if tf == primary else 0.4 / (n_tf - 1)

    for coin_info in coins:
        sym    = coin_info["symbol"]
        ex     = coin_info["exchange"]
        csym   = coin_info["ccxt_symbol"]
        logger.info(f"  Analysing {sym} on {ex} …")

        tf_scores = {}
        primary_result = None

        for tf in timeframes:
            from fetcher import fetch_ohlcv
            df = fetch_ohlcv(exchanges, ex, csym, tf, limit=300)
            if df is None or len(df) < 220:
                logger.debug(f"    {sym} {tf}: insufficient data")
                continue
            result = compute_full_score(df)
            if "error" in result:
                continue
            tf_scores[tf] = result["pump_score"]
            if tf == primary:
                primary_result = result

        if not primary_result:
            continue

        # Weighted composite across timeframes
        if tf_scores:
            composite = sum(
                tf_scores.get(tf, primary_result["pump_score"]) * tf_weights.get(tf, 0)
                for tf in timeframes
            )
        else:
            composite = primary_result["pump_score"]

        composite = round(min(10, composite), 2)
        entry = {**primary_result}
        entry["pump_score"]   = composite
        entry["tf_scores"]    = tf_scores
        entry["symbol"]       = sym
        entry["exchange"]     = ex
        entry["ccxt_symbol"]  = csym
        entry["volume_usdt"]  = coin_info["volume_usdt"]
        results.append(entry)

    return results


# ─────────────────────────────────────────────
#  MAIN SCAN LOOP
# ─────────────────────────────────────────────

_coin_cache: List[str]  = []
_cache_ts: float        = 0
CACHE_TTL_SECONDS       = 3600    # Refresh top-1000 list every hour


def get_top_coins_cached() -> List[str]:
    global _coin_cache, _cache_ts
    now = time.time()
    if not _coin_cache or (now - _cache_ts) > CACHE_TTL_SECONDS:
        logger.info(f"Fetching top {MARKET_CAP_TOP} coins from CoinGecko …")
        _coin_cache = fetch_top_coins(MARKET_CAP_TOP)
        _cache_ts   = now
        logger.info(f"Cached {len(_coin_cache)} coins")
    return _coin_cache


def run_scan(exchanges: dict) -> Optional[List[Dict]]:
    scan_start = datetime.utcnow()
    logger.info(f"\n{'='*55}")
    logger.info(f"  🔍 SCAN STARTED — {scan_start.strftime('%H:%M:%S UTC')}")
    logger.info(f"{'='*55}")

    # 1. Top coins list
    top_coins = get_top_coins_cached()
    if not top_coins:
        logger.error("Failed to fetch top coins list")
        return None

    # 2. Filter to tradeable symbols
    logger.info("Cross-referencing with exchange markets …")
    tradeable = get_tradeable_symbols(exchanges, top_coins, QUOTE_CURRENCY)
    logger.info(f"Found {len(tradeable)} tradeable pairs with sufficient liquidity")

    if not tradeable:
        logger.error("No tradeable pairs found — check exchange connections")
        return None

    # 3. Score all coins (multi-timeframe)
    logger.info(f"Scoring {len(tradeable)} coins across {TIMEFRAMES} …")
    results = score_with_multi_tf(exchanges, tradeable, TIMEFRAMES, PRIMARY_TIMEFRAME)
    logger.info(f"Scored {len(results)} coins successfully")

    # 4. Filter by minimum score
    results = [r for r in results if r["pump_score"] >= MIN_SIGNAL_SCORE]

    # 5. Sort by pump_score descending, take top N
    results.sort(key=lambda x: x["pump_score"], reverse=True)
    top = results[:TOP_N_COINS]

    if not top:
        logger.warning("No coins passed the minimum signal threshold this scan")
        return []

    # 6. Log summary
    logger.info(f"\n{'─'*45}")
    logger.info(f"  🏆 TOP {len(top)} PUMP CANDIDATES:")
    logger.info(f"{'─'*45}")
    for i, r in enumerate(top, 1):
        logger.info(
            f"  {i:>2}. {r['symbol']:<10} Score={r['pump_score']}/10  "
            f"RSI={r['rsi']:.1f}  Vol={r['vol_ratio']:.1f}x  "
            f"Trend={r['trend_label']}"
        )
    logger.info(f"{'─'*45}\n")

    # 7. Send to Telegram
    logger.info("Sending signals to Telegram …")
    send_scan_results(top, len(tradeable))
    logger.info("✅ Signals sent!")

    elapsed = (datetime.utcnow() - scan_start).total_seconds()
    logger.info(f"Scan completed in {elapsed:.1f}s")
    return top


# ─────────────────────────────────────────────
#  SCHEDULER
# ─────────────────────────────────────────────

def scheduler_loop(exchanges: dict):
    interval = SCAN_INTERVAL_MINUTES * 60
    logger.info(f"⏱  Scheduler started — scanning every {SCAN_INTERVAL_MINUTES} minutes")

    # Run immediately on start
    try:
        run_scan(exchanges)
    except Exception as e:
        logger.error(f"First scan failed: {e}", exc_info=True)

    # Then loop
    while True:
        next_scan = time.time() + interval
        logger.info(f"💤 Next scan in {SCAN_INTERVAL_MINUTES} minutes …")
        while time.time() < next_scan:
            time.sleep(10)
        try:
            run_scan(exchanges)
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    print("""
╔══════════════════════════════════════════════╗
║     🚀 CRYPTO PUMP SCANNER - STARTING UP     ║
║                                              ║
║  Exchanges : Binance · Gate.io · OKX         ║
║  Metrics   : RSI · MACD · BOS · CHoCH · OB  ║
║              FVG · Volume · Momentum ·       ║
║              Velocity · ADX · MFI · CCI ·   ║
║              Stoch · Williams%R · VWAP ·     ║
║              OBV · P/D · Liquidity · MM      ║
║  Output    : Telegram + Console              ║
╚══════════════════════════════════════════════╝
""")

    logger.info("Initialising exchanges …")
    try:
        exchanges = init_exchanges()
    except RuntimeError as e:
        logger.critical(f"Cannot start: {e}")
        return

    logger.info(f"Connected exchanges: {list(exchanges.keys())}")
    scheduler_loop(exchanges)


if __name__ == "__main__":
    main()
