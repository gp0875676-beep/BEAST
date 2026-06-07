"""
=====================================================
  TELEGRAM SIGNAL SENDER
  Sends formatted pump signal reports to Telegram
=====================================================
"""

import requests
import logging
from datetime import datetime
from typing import List, Dict
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("telegram")

SCORE_BAR = {
    (9, 10): "🟢🟢🟢🟢🟢",
    (7,  9): "🟢🟢🟢🟢⚪",
    (5,  7): "🟢🟢🟢⚪⚪",
    (3,  5): "🟡🟡⚪⚪⚪",
    (0,  3): "🔴🔴⚪⚪⚪",
}


def score_bar(score: float) -> str:
    for (low, high), bar in SCORE_BAR.items():
        if low <= score <= high:
            return bar
    return "⚪⚪⚪⚪⚪"


def score_emoji(score: float) -> str:
    if score >= 8.5: return "🚀🔥"
    if score >= 7.5: return "🚀"
    if score >= 6.5: return "📈"
    if score >= 5.5: return "⬆️"
    return "➡️"


def format_signal_message(rank: int, result: Dict, scan_time: str) -> str:
    s      = result["scores"]
    r      = result
    sym    = r["symbol"]
    price  = r["current_price"]
    pump   = r["pump_score"]

    # Format price
    if price < 0.001:
        price_str = f"${price:.8f}"
    elif price < 1:
        price_str = f"${price:.5f}"
    elif price < 100:
        price_str = f"${price:.4f}"
    else:
        price_str = f"${price:,.2f}"

    trend_icon = {
        "strong_uptrend": "📈📈",
        "uptrend"       : "📈",
        "sideways"      : "➡️",
        "downtrend"     : "📉",
    }.get(r["trend_label"], "➡️")

    struct = r["structure"]
    struct_tag = ""
    if struct.get("choch"): struct_tag = "🔄 CHoCH"
    elif struct.get("bos"): struct_tag = "💥 BOS"
    else:                   struct_tag = f"📊 {struct.get('bias','neutral').upper()}"

    pd_icon = "💚 DISCOUNT" if r["pd_zone"] == "discount" else "🔴 PREMIUM"
    vwap_icon = "✅" if r["above_vwap"] else "❌"

    msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
{score_emoji(pump)} #{rank} │ <b>${sym}</b> │ {price_str}
━━━━━━━━━━━━━━━━━━━━━━━━

🏆 <b>PUMP SCORE: {pump}/10</b>  {score_bar(pump)}

┌─ 📊 OSCILLATORS ─────────────────
│ RSI        {r['rsi']:>6.1f}  {score_bar(s['rsi'])} [{s['rsi']}/10]
│ MACD Hist  {r['macd_hist']:>9.6f}  {score_bar(s['macd'])} [{s['macd']}/10]
│ Stoch K    {r['stoch_k']:>6.1f}  {score_bar(s['stoch'])} [{s['stoch']}/10]
│ MFI        {r['mfi']:>6.1f}  {score_bar(s['mfi'])} [{s['mfi']}/10]
│ CCI        {r['cci']:>6.1f}  {score_bar(s['cci'])} [{s['cci']}/10]
│ Williams%R {r['williams_r']:>6.1f}  {score_bar(s['willr'])} [{s['willr']}/10]
│ ADX        {r['adx']:>6.1f}  {score_bar(s['adx'])} [{s['adx']}/10]
│ %B (BB)    {r['pct_b']:>6.3f}  {score_bar(s['macd'])} [{s['macd']}/10]

├─ 🔥 MOMENTUM & VELOCITY ─────────
│ Momentum   {r['momentum_pct']:>+6.2f}%  {score_bar(s['momentum'])} [{s['momentum']}/10]
│ Velocity   {r['velocity']:>+6.4f}  {score_bar(s['velocity'])} [{s['velocity']}/10]
│ ROC        (integrated)

├─ 📦 VOLUME ANALYSIS ─────────────
│ Vol Ratio  {r['vol_ratio']:>6.2f}x  {score_bar(s['volume'])} [{s['volume']}/10]
│ Vol Surge  {'YES 🔥' if r['vol_surge'] else 'NO':>8}
│ PV Confirm {'YES ✅' if r['pv_confirm'] else 'NO ❌':>8}
│ OBV Trend  {score_bar(s['obv'])} [{s['obv']}/10]

├─ 🧠 SMART MONEY (ICT/SMC) ───────
│ Structure  {struct_tag:>18}  [{s['structure']}/10]
│ Order Blks {r['order_blocks']:>6}  {score_bar(s['ob'])} [{s['ob']}/10]
│ FVG Active {r['fvg_count']:>6}  {score_bar(s['fvg'])} [{s['fvg']}/10]
│ P/D Zone   {pd_icon:>18}  [{s['pd']}/10]
│ Inducement {'YES 🎯' if r['inducement'] else 'NO':>8}  [{s['liquidity']}/10]
│ MM Accum   {'YES 🏦' if r['mm_accumulation'] else 'NO':>8}  [{s['mm']}/10]

├─ 📐 TREND & STRUCTURE ───────────
│ Trend      {trend_icon} {r['trend_label']:>15}  [{s['trend']}/10]
│ VWAP       {'Above' if r['above_vwap'] else 'Below':>8} {vwap_icon}

└─ ⚡ SIGNAL STRENGTH ─────────────
  Reliability: {score_bar(pump)}
  Score: <b>{pump}/10</b>

🕐 {scan_time}
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return msg.strip()


def format_summary_header(n_scanned: int, n_top: int, scan_time: str) -> str:
    return f"""
╔══════════════════════════════╗
║  🤖 CRYPTO PUMP SCANNER      ║
║  ⏱ Every 5 min · Top {n_top} Picks ║
╚══════════════════════════════╝

📡 Scanned: <b>{n_scanned} coins</b>
🕐 Time: <b>{scan_time}</b>
🔍 Metrics: RSI • MACD • BOS • CHoCH • OB • FVG • Volume • Momentum • Velocity • ADX • MFI • CCI • Stoch • Williams%R • VWAP • OBV • Premium/Discount • Liquidity • Market Maker

━━━━━━━━━━━━━━━━━━━━━━━━
🏆 TOP PUMP CANDIDATES:
━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()


def format_summary_footer(top_coins: List[Dict]) -> str:
    lines = ["", "━━━━━━━━━━━━━━━━━━━━━━━━",
             "📋 QUICK REFERENCE:", ""]
    for i, r in enumerate(top_coins, 1):
        bar  = score_bar(r["pump_score"])
        lines.append(f"{i:>2}. <b>${r['symbol']:<8}</b> {bar} {r['pump_score']}/10")
    lines += ["", "⚠️ <i>Not financial advice. DYOR. Trade responsibly.</i>",
              "━━━━━━━━━━━━━━━━━━━━━━━━"]
    return "\n".join(lines)


def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("[TG] Token not configured — printing to console instead")
        print(message)
        return True
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id"   : TELEGRAM_CHAT_ID,
        "text"      : message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, data=data, timeout=15)
        if resp.status_code == 200:
            return True
        logger.error(f"TG error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"TG send failed: {e}")
        return False


def send_scan_results(top_coins: List[Dict], n_scanned: int):
    """Send full scan report to Telegram"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Header
    header = format_summary_header(n_scanned, len(top_coins), now)
    send_telegram(header)

    # Individual coin signals
    for i, coin in enumerate(top_coins, 1):
        msg = format_signal_message(i, coin, now)
        ok  = send_telegram(msg)
        if not ok:
            logger.warning(f"Failed to send signal for {coin['symbol']}")
        import time; time.sleep(0.5)   # Telegram rate limit

    # Footer summary
    footer = format_summary_footer(top_coins)
    send_telegram(footer)
