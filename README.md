# 🚀 CRYPTO PUMP SCANNER BOT

Scans top 1000 coins by market cap every 5 minutes, scores them across 20+ indicators, and sends the top 10 pump candidates to Telegram with a full metric breakdown.

---

## 📁 FILE STRUCTURE

```
crypto_pump_scanner/
├── config.py        ← ⚠️  PUT YOUR API KEYS HERE
├── main.py          ← Entry point — run this
├── analysis.py      ← All TA indicators + scoring engine
├── fetcher.py       ← Exchange connections + OHLCV fetcher
├── notifier.py      ← Telegram message formatter + sender
├── requirements.txt
└── README.md
```

---

## ⚙️ SETUP (5 minutes)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API keys in `config.py`

#### Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`, follow prompts → copy your **Bot Token**
3. Start a chat with your bot, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Send any message to your bot, refresh the URL → find `"chat":{"id": ...}` → that's your **Chat ID**
5. Paste both into `config.py`

#### Exchange API Keys (optional for public data)
- **Binance**: [binance.com/en/my/settings/api-management](https://www.binance.com/en/my/settings/api-management) — Read-only key
- **Gate.io**: [gate.io/myaccount/api_key_manage](https://www.gate.io/myaccount/api_key_manage) — Read-only key
- **OKX**: [okx.com/account/my-api](https://www.okx.com/account/my-api) — Read-only key

> 💡 You can leave API keys blank — public OHLCV data works without authentication on all three exchanges. Keys only needed for private account data.

### 3. Run
```bash
cd crypto_pump_scanner
python main.py
```

---

## 📊 METRICS EXPLAINED (all scored 1–10)

### Oscillators
| Metric | What it measures |
|--------|-----------------|
| **RSI** | Relative Strength Index — momentum. Best signal: 45–65, rising |
| **MACD** | Moving Average Convergence Divergence — trend momentum crossovers |
| **Stochastic** | Overbought/oversold with crossover signals |
| **MFI** | Money Flow Index — volume-weighted RSI |
| **CCI** | Commodity Channel Index — deviation from mean |
| **Williams %R** | Oversold/overbought with reversal sensitivity |
| **ADX** | Average Directional Index — trend strength |
| **Bollinger %B** | Position within Bollinger Bands |

### Momentum & Velocity
| Metric | What it measures |
|--------|-----------------|
| **Momentum** | 10-period price change percentage |
| **Velocity** | Volume-weighted rate of momentum change |
| **ROC** | Rate of Change — acceleration |

### Volume
| Metric | What it measures |
|--------|-----------------|
| **Volume Ratio** | Current vs 20-period average (>1.8x = surge) |
| **PV Confirm** | Price and volume both rising together |
| **OBV** | On-Balance Volume trend direction |

### Smart Money Concepts (ICT/SMC)
| Metric | What it means |
|--------|--------------|
| **BOS** | Break of Structure — trend continuation confirmed |
| **CHoCH** | Change of Character — potential trend reversal/start |
| **Order Blocks** | Institutional buy/sell zones price returns to |
| **FVG** | Fair Value Gap — imbalance zones price is drawn to fill |
| **Premium/Discount** | Is price cheap (discount) or expensive (premium)? |
| **Liquidity** | Sell-side/buy-side liquidity levels |
| **Inducement** | False breakout to trap retail → reversal signal |

### Trend & Market Maker
| Metric | What it measures |
|--------|-----------------|
| **Trend (EMA stack)** | 9/21/50/100/200 EMA alignment |
| **VWAP** | Above VWAP = bullish intraday bias |
| **MM Accumulation** | Tight range + volume pattern = institutional buildup |

---

## 📱 TELEGRAM SIGNAL FORMAT

```
🚀🔥 #1 │ $SOL │ $180.34
━━━━━━━━━━━━━━━━━━━━━━━━
🏆 PUMP SCORE: 8.7/10  🟢🟢🟢🟢🟢

├─ 📊 OSCILLATORS
│ RSI          62.4  🟢🟢🟢🟢⚪ [8/10]
│ MACD Hist  0.000234  🟢🟢🟢🟢⚪ [8/10]
│ ...

├─ 🧠 SMART MONEY
│ Structure    💥 BOS         [9/10]
│ FVG Active       2  🟢🟢🟢🟢⚪ [9/10]
│ P/D Zone    💚 DISCOUNT     [8/10]
│ Inducement  YES 🎯          [9/10]
...
```

---

## ⚡ HOW SCORING WORKS

Each of the 16 factors is scored 0–10, then weighted:

| Factor | Weight |
|--------|--------|
| Volume | 10% |
| RSI | 9% |
| Market Structure (BOS/CHoCH) | 9% |
| MACD | 8% |
| Trend (EMA) | 8% |
| Velocity | 8% |
| Momentum | 7% |
| Liquidity/Inducement | 7% |
| Order Blocks | 6% |
| ADX | 5% |
| FVG | 5% |
| Premium/Discount | 5% |
| MFI | 4% |
| Stochastic | 4% |
| OBV | 3% |
| Market Maker | 2% |

Multi-timeframe: 15m (20%) + 1h (60%) + 4h (20%)

---

## 🔧 CUSTOMISATION

In `config.py`:
- `SCAN_INTERVAL_MINUTES = 5` — change scan frequency
- `TOP_N_COINS = 10` — how many coins to report
- `MARKET_CAP_TOP = 1000` — how many coins to scan
- `MIN_SIGNAL_SCORE = 5.5` — minimum score to include
- `TIMEFRAMES = ["15m", "1h", "4h"]` — candle timeframes
- `VOLUME_SURGE_MULT = 1.8` — volume surge threshold
- `MIN_LIQUIDITY_USDT = 500000` — minimum 24h volume filter

---

## ⚠️ DISCLAIMER

This tool is for **educational and informational purposes only**.
- Not financial advice
- Cryptocurrency trading carries high risk
- Past signals do not guarantee future performance
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
