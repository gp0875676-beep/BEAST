"""
CRYPTO PUMP SCANNER - RENDER FREE WEB SERVICE
No CoinGecko — coins fetched directly from Gate.io + OKX
"""

import os
import time
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict

from config import (
    SCAN_INTERVAL_MINUTES, TOP_N_COINS,
    TIMEFRAMES, PRIMARY_TIMEFRAME, MIN_SIGNAL_SCORE, QUOTE_CURRENCY
)
from fetcher  import init_exchanges, get_tradeable_symbols_direct, fetch_ohlcv
from analysis import compute_full_score
from notifier import send_scan_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("main")

STATUS = {
    "last_scan" : "Not yet run",
    "scanned"   : 0,
    "top_coins" : [],
    "scan_count": 0,
    "status"    : "starting",
}


# ── HTTP Health Server ────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        top  = STATUS["top_coins"]
        rows = "".join(
            f"<tr><td>{i+1}</td><td><b>${c['symbol']}</b></td>"
            f"<td>{c['pump_score']}/10</td>"
            f"<td>{c.get('rsi','-')}</td>"
            f"<td>{c.get('trend_label','-')}</td></tr>"
            for i, c in enumerate(top)
        )
        html = f"""<!DOCTYPE html><html>
<head><title>🚀 Pump Scanner</title>
<meta http-equiv="refresh" content="60">
<style>
body{{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}}
h1{{color:#58a6ff}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #30363d;padding:8px 12px;text-align:left}}
th{{background:#161b22;color:#58a6ff}}
.badge{{background:#238636;padding:2px 8px;border-radius:4px;color:#fff}}
</style></head>
<body>
<h1>🚀 Crypto Pump Scanner</h1>
<p>Status: <span class="badge">{STATUS['status']}</span>
&nbsp;|&nbsp; Last scan: <b>{STATUS['last_scan']}</b>
&nbsp;|&nbsp; Scans done: <b>{STATUS['scan_count']}</b>
&nbsp;|&nbsp; Coins scanned: <b>{STATUS['scanned']}</b></p>
<h2>🏆 Top Pump Candidates</h2>
<table><tr><th>#</th><th>Symbol</th><th>Score</th><th>RSI</th><th>Trend</th></tr>
{rows if rows else '<tr><td colspan=5>Waiting for first scan...</td></tr>'}
</table>
<p style="color:#8b949e;font-size:12px">⚠️ Not financial advice.</p>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *args):
        pass


# ── Scoring ───────────────────────────────────────────────────

def score_coins(exchanges, coins):
    n_tf       = len(TIMEFRAMES)
    tf_weights = {tf: (0.6 if tf == PRIMARY_TIMEFRAME else 0.4 / (n_tf - 1)) for tf in TIMEFRAMES}
    results    = []

    for coin_info in coins:
        sym, ex, csym = coin_info["symbol"], coin_info["exchange"], coin_info["ccxt_symbol"]
        logger.info(f"  → {sym}")
        tf_scores, primary_result = {}, None

        for tf in TIMEFRAMES:
            df = fetch_ohlcv(exchanges, ex, csym, tf, limit=300)
            if df is None or len(df) < 220:
                continue
            res = compute_full_score(df)
            if "error" in res:
                continue
            tf_scores[tf] = res["pump_score"]
            if tf == PRIMARY_TIMEFRAME:
                primary_result = res

        if not primary_result:
            continue

        composite = round(min(10, sum(
            tf_scores.get(tf, primary_result["pump_score"]) * tf_weights.get(tf, 0)
            for tf in TIMEFRAMES
        )), 2)

        results.append({**primary_result,
                        "pump_score" : composite,
                        "symbol"     : sym,
                        "exchange"   : ex,
                        "ccxt_symbol": csym,
                        "volume_usdt": coin_info["volume_usdt"]})
    return results


# ── Main Scan ─────────────────────────────────────────────────

def run_scan(exchanges):
    STATUS["status"] = "scanning"
    start = datetime.now()
    logger.info(f"\n{'='*50}\n  🔍 SCAN — {start.strftime('%H:%M:%S UTC')}\n{'='*50}")

    # Get coins directly from exchange — no CoinGecko
    tradeable = get_tradeable_symbols_direct(exchanges, limit=1000)
    logger.info(f"{len(tradeable)} tradeable pairs found")
    STATUS["scanned"] = len(tradeable)

    if not tradeable:
        STATUS["status"] = "error: no pairs"
        return

    results = score_coins(exchanges, tradeable)
    results = [r for r in results if r["pump_score"] >= MIN_SIGNAL_SCORE]
    results.sort(key=lambda x: x["pump_score"], reverse=True)
    top = results[:TOP_N_COINS]

    logger.info(f"\n{'─'*40}  TOP {len(top)} RESULTS:")
    for i, r in enumerate(top, 1):
        logger.info(f"  {i:>2}. {r['symbol']:<10} {r['pump_score']}/10  RSI={r['rsi']:.1f}  {r['trend_label']}")

    STATUS.update({
        "last_scan" : start.strftime("%Y-%m-%d %H:%M UTC"),
        "top_coins" : top,
        "scan_count": STATUS["scan_count"] + 1,
        "status"    : "idle",
    })

    send_scan_results(top, len(tradeable))
    logger.info(f"✅ Done in {(datetime.now()-start).total_seconds():.1f}s — signals sent to Telegram")


# ── Scanner Loop (background thread) ─────────────────────────

def scanner_loop(exchanges):
    interval = SCAN_INTERVAL_MINUTES * 60
    logger.info(f"⏱  Scanner: every {SCAN_INTERVAL_MINUTES} min")
    time.sleep(5)   # let HTTP server settle

    try:
        run_scan(exchanges)
    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)
        STATUS["status"] = f"error: {e}"

    while True:
        next_at = time.time() + interval
        logger.info(f"💤 Next scan in {SCAN_INTERVAL_MINUTES} min")
        while time.time() < next_at:
            time.sleep(15)
        try:
            run_scan(exchanges)
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            STATUS["status"] = f"error: {e}"


# ── Entry Point ───────────────────────────────────────────────

def main():
    PORT = int(os.environ.get("PORT", 10000))
    print("\n🚀 CRYPTO PUMP SCANNER — STARTING\n")

    # 1. HTTP server FIRST — Render needs port immediately
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"🌐 HTTP server on port {PORT}")

    # 2. Init exchanges + start scanner in background
    def start_scanner():
        try:
            exchanges = init_exchanges()
            logger.info(f"Exchanges: {list(exchanges.keys())}")
            scanner_loop(exchanges)
        except Exception as e:
            logger.critical(f"Fatal: {e}", exc_info=True)
            STATUS["status"] = f"fatal: {e}"

    threading.Thread(target=start_scanner, daemon=True).start()

    # 3. HTTP runs forever on main thread
    logger.info("✅ Bot live — scanner starting…")
    server.serve_forever()


if __name__ == "__main__":
    main()
