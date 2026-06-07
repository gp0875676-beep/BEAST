"""
=====================================================
  TECHNICAL ANALYSIS ENGINE
  Covers: RSI, MACD, Bollinger, Stoch, ATR, OBV,
  VWAP, EMA/SMA, ADX, CCI, Williams %R, MFI,
  CHoCH, BOS, Order Blocks, FVG, Premium/Discount,
  Liquidity sweeps, Market Structure, Trend analysis
=====================================================
"""

import numpy as np
import pandas as pd
from typing import Optional


# ─────────────────────────────────────────────
#  CORE OSCILLATORS
# ─────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = close.ewm(span=fast, adjust=False).mean()
    ema_slow   = close.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(close: pd.Series, period=20, std_dev=2):
    mid   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    pct_b = (close - lower) / (upper - lower + 1e-10)
    return upper, mid, lower, pct_b


def calc_stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low   = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
    d = k.rolling(d_period).mean()
    return k, d


def calc_atr(high, low, close, period=14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def calc_adx(high, low, close, period=14):
    tr     = calc_atr(high, low, close, period)
    dm_pos = high.diff().clip(lower=0)
    dm_neg = (-low.diff()).clip(lower=0)
    dm_pos = dm_pos.where(dm_pos > dm_neg, 0)
    dm_neg = dm_neg.where(dm_neg > dm_pos, 0)
    di_pos = 100 * dm_pos.ewm(span=period, adjust=False).mean() / (tr + 1e-10)
    di_neg = 100 * dm_neg.ewm(span=period, adjust=False).mean() / (tr + 1e-10)
    dx     = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg + 1e-10)
    adx    = dx.ewm(span=period, adjust=False).mean()
    return adx, di_pos, di_neg


def calc_cci(high, low, close, period=20) -> pd.Series:
    typical = (high + low + close) / 3
    mean_tp = typical.rolling(period).mean()
    mean_dev = typical.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (typical - mean_tp) / (0.015 * mean_dev + 1e-10)


def calc_williams_r(high, low, close, period=14) -> pd.Series:
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    return -100 * (hh - close) / (hh - ll + 1e-10)


def calc_mfi(high, low, close, volume, period=14) -> pd.Series:
    typical = (high + low + close) / 3
    mf      = typical * volume
    pos_mf  = mf.where(typical > typical.shift(), 0)
    neg_mf  = mf.where(typical < typical.shift(), 0)
    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()
    mfr     = pos_sum / (neg_sum + 1e-10)
    return 100 - (100 / (1 + mfr))


def calc_obv(close, volume) -> pd.Series:
    direction = np.sign(close.diff())
    return (direction * volume).fillna(0).cumsum()


def calc_vwap(high, low, close, volume) -> pd.Series:
    typical = (high + low + close) / 3
    cum_tp_vol = (typical * volume).cumsum()
    cum_vol    = volume.cumsum()
    return cum_tp_vol / (cum_vol + 1e-10)


def calc_emas(close):
    return {
        "ema9"  : close.ewm(span=9,   adjust=False).mean(),
        "ema21" : close.ewm(span=21,  adjust=False).mean(),
        "ema50" : close.ewm(span=50,  adjust=False).mean(),
        "ema100": close.ewm(span=100, adjust=False).mean(),
        "ema200": close.ewm(span=200, adjust=False).mean(),
    }


def calc_momentum(close, period=10) -> pd.Series:
    return close.pct_change(period) * 100


def calc_roc(close, period=12) -> pd.Series:
    return ((close - close.shift(period)) / close.shift(period)) * 100


def calc_velocity(close, volume, period=5) -> float:
    """Price velocity = rate of momentum change weighted by volume"""
    price_change = close.pct_change().iloc[-period:]
    vol_weight   = volume.iloc[-period:] / (volume.iloc[-period:].sum() + 1e-10)
    return float((price_change * vol_weight).sum() * 100)


# ─────────────────────────────────────────────
#  SMART MONEY CONCEPTS (ICT / SMC)
# ─────────────────────────────────────────────

def detect_swing_points(high, low, lookback=5):
    """Detect swing highs and lows"""
    swing_highs = []
    swing_lows  = []
    for i in range(lookback, len(high) - lookback):
        if high.iloc[i] == high.iloc[i - lookback:i + lookback + 1].max():
            swing_highs.append(i)
        if low.iloc[i] == low.iloc[i - lookback:i + lookback + 1].min():
            swing_lows.append(i)
    return swing_highs, swing_lows


def detect_market_structure(close, high, low, lookback=5):
    """
    BOS  = Break of Structure (continuation)
    CHoCH = Change of Character (reversal signal)
    Returns: structure_bias, recent_bos, recent_choch
    """
    swing_highs, swing_lows = detect_swing_points(high, low, lookback)

    result = {
        "bias"  : "neutral",
        "bos"   : False,
        "choch" : False,
        "bos_level"   : None,
        "choch_level" : None,
    }

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return result

    last_sh = swing_highs[-1]
    prev_sh = swing_highs[-2]
    last_sl = swing_lows[-1]
    prev_sl = swing_lows[-2]

    # Higher Highs + Higher Lows → bullish structure
    hh = high.iloc[last_sh] > high.iloc[prev_sh]
    hl = low.iloc[last_sl]  > low.iloc[prev_sl]
    ll = low.iloc[last_sl]  < low.iloc[prev_sl]
    lh = high.iloc[last_sh] < high.iloc[prev_sh]

    if hh and hl:
        result["bias"] = "bullish"
        # BOS: price breaks above last swing high
        if close.iloc[-1] > high.iloc[last_sh]:
            result["bos"]   = True
            result["bos_level"] = high.iloc[last_sh]
    elif ll and lh:
        result["bias"] = "bearish"

    # CHoCH: bullish structure breaks below last swing low
    if result["bias"] == "bullish" and close.iloc[-1] < low.iloc[last_sl]:
        result["choch"]       = True
        result["choch_level"] = low.iloc[last_sl]

    # CHoCH: bearish structure breaks above last swing high
    if result["bias"] == "bearish" and close.iloc[-1] > high.iloc[last_sh]:
        result["choch"]       = True
        result["choch_level"] = high.iloc[last_sh]
        result["bias"]        = "bullish"  # structure shift

    return result


def detect_order_blocks(open_, high, low, close, n=3):
    """
    Order Block = last bearish/bullish candle before a strong impulse move
    Returns list of active bullish OBs near current price
    """
    obs = []
    for i in range(n + 1, len(close) - 1):
        # Bullish OB: bearish candle followed by strong up move
        if close.iloc[i] < open_.iloc[i]:  # bearish candle
            impulse = (close.iloc[i + 1] - close.iloc[i]) / (close.iloc[i] + 1e-10)
            if impulse > 0.008:  # 0.8%+ impulse
                obs.append({
                    "type": "bullish",
                    "top": high.iloc[i],
                    "bottom": low.iloc[i],
                    "index": i,
                })
    # Keep only the 3 most recent
    obs = obs[-3:]
    current_price = close.iloc[-1]
    # Check if price is near any OB (within 2%)
    active_obs = [
        ob for ob in obs
        if ob["bottom"] <= current_price * 1.02
        and ob["top"]    >= current_price * 0.98
    ]
    return active_obs


def detect_fvg(high, low, close, n_candles=50):
    """
    Fair Value Gap = 3-candle pattern where gap exists between candle[i-2].high and candle[i].low
    Bullish FVG: candle[i].low > candle[i-2].high
    """
    fvgs = []
    start = max(2, len(close) - n_candles)
    for i in range(start, len(close)):
        gap = low.iloc[i] - high.iloc[i - 2]
        if gap > 0:
            fvgs.append({
                "type"  : "bullish",
                "top"   : low.iloc[i],
                "bottom": high.iloc[i - 2],
                "mid"   : (low.iloc[i] + high.iloc[i - 2]) / 2,
                "index" : i,
            })
    # Filter: price approaching FVG from below
    current = close.iloc[-1]
    active  = [f for f in fvgs if f["bottom"] <= current * 1.03 and f["top"] >= current * 0.97]
    return active[-2:] if active else []


def detect_premium_discount(high, low, close):
    """
    Premium / Discount zones relative to the current trading range
    Discount = below 50% of range (good to buy)
    Premium  = above 50% of range (good to sell)
    """
    period_high = high.rolling(50).max().iloc[-1]
    period_low  = low.rolling(50).min().iloc[-1]
    equilibrium = (period_high + period_low) / 2
    current     = close.iloc[-1]
    pct_pos     = (current - period_low) / (period_high - period_low + 1e-10)
    zone        = "discount" if pct_pos < 0.5 else "premium"
    return {
        "zone"       : zone,
        "pct_position": round(pct_pos * 100, 1),
        "equilibrium": equilibrium,
        "range_high" : period_high,
        "range_low"  : period_low,
    }


def detect_liquidity_zones(high, low, close, volume, lookback=30):
    """
    Liquidity = areas where stop-losses cluster (near swing highs/lows)
    Inducement = false breakout above/below liquidity to trap retail
    """
    recent_high = high.rolling(lookback).max().iloc[-1]
    recent_low  = low.rolling(lookback).min().iloc[-1]
    current     = close.iloc[-1]
    avg_volume  = volume.rolling(20).mean().iloc[-1]
    last_volume = volume.iloc[-1]

    # Inducement: price swept above recent high but closed back below
    inducement_up   = (high.iloc[-1] > recent_high * 0.995) and (close.iloc[-1] < recent_high)
    inducement_down = (low.iloc[-1]  < recent_low  * 1.005) and (close.iloc[-1] > recent_low)

    # Volume surge at key level = institutional activity
    vol_surge = last_volume > avg_volume * 1.5

    return {
        "buy_side_liquidity" : recent_high,
        "sell_side_liquidity": recent_low,
        "inducement_bullish" : inducement_down and vol_surge,   # swept lows → buy
        "inducement_bearish" : inducement_up   and vol_surge,
        "volume_surge"       : vol_surge,
    }


# ─────────────────────────────────────────────
#  TREND ANALYSIS
# ─────────────────────────────────────────────

def analyse_trend(close, emas):
    """Multi-EMA trend scoring"""
    e = {k: v.iloc[-1] for k, v in emas.items()}
    c = close.iloc[-1]
    score = 0
    # Price above each EMA
    if c > e["ema9"]:   score += 1
    if c > e["ema21"]:  score += 1
    if c > e["ema50"]:  score += 1.5
    if c > e["ema100"]: score += 1.5
    if c > e["ema200"]: score += 2
    # EMA alignment (bullish stack)
    if e["ema9"] > e["ema21"] > e["ema50"]:  score += 1
    if e["ema50"] > e["ema100"] > e["ema200"]: score += 1
    max_score = 9
    strength  = round(score / max_score * 10, 2)
    if   strength >= 7: label = "strong_uptrend"
    elif strength >= 5: label = "uptrend"
    elif strength >= 3: label = "sideways"
    else:               label = "downtrend"
    return {"label": label, "score": strength, "ema_vals": e}


# ─────────────────────────────────────────────
#  VOLUME ANALYSIS
# ─────────────────────────────────────────────

def analyse_volume(volume, close):
    avg_vol_20 = volume.rolling(20).mean().iloc[-1]
    avg_vol_5  = volume.rolling(5).mean().iloc[-1]
    last_vol   = volume.iloc[-1]
    vol_ratio  = last_vol / (avg_vol_20 + 1e-10)
    # Volume momentum
    vol_mom    = (avg_vol_5 - avg_vol_20) / (avg_vol_20 + 1e-10)
    # Price-volume confirmation
    price_up   = close.iloc[-1] > close.iloc[-5]
    vol_up     = avg_vol_5 > avg_vol_20
    pv_confirm = price_up and vol_up
    return {
        "vol_ratio"  : round(vol_ratio, 2),
        "vol_momentum": round(vol_mom * 100, 2),
        "pv_confirm" : pv_confirm,
        "surge"      : vol_ratio > 1.8,
    }


# ─────────────────────────────────────────────
#  INVESTOR / MARKET MAKER BEHAVIOUR
# ─────────────────────────────────────────────

def detect_market_maker_activity(open_, high, low, close, volume):
    """
    Market Maker signals:
    - Wicks above/below candle body (stop hunting)
    - Low volume consolidation before breakout (accumulation)
    - Wick-to-body ratio analysis
    """
    body     = (close - open_).abs()
    upper_wk = high  - pd.concat([close, open_], axis=1).max(axis=1)
    lower_wk = pd.concat([close, open_], axis=1).min(axis=1) - low
    wk_ratio = (upper_wk + lower_wk) / (body + 1e-10)
    avg_wk_ratio = wk_ratio.rolling(10).mean().iloc[-1]

    # Accumulation: narrow price range, low-ish volume, before expansion
    price_range_ratio = (
        (high.rolling(10).max() - low.rolling(10).min()) /
        (high.rolling(20).max() - low.rolling(20).min() + 1e-10)
    ).iloc[-1]

    accumulation = price_range_ratio < 0.5 and volume.iloc[-1] < volume.rolling(20).mean().iloc[-1]
    stop_hunt    = avg_wk_ratio > 1.5

    return {
        "accumulation": accumulation,
        "stop_hunt"   : stop_hunt,
        "mm_score"    : int(accumulation) * 3 + int(stop_hunt) * 2,
    }


# ─────────────────────────────────────────────
#  MASTER SCORING ENGINE
# ─────────────────────────────────────────────

def compute_full_score(df: pd.DataFrame) -> dict:
    """
    Input df columns: open, high, low, close, volume
    Returns full scoring dict with individual metric scores (1-10 each)
    and composite pump_score (1-10)
    """
    o = df["open"];  h = df["high"]
    l = df["low"];   c = df["close"]; v = df["volume"]

    if len(c) < 220:
        return {"error": "insufficient_data", "pump_score": 0}

    # ── Compute all indicators ──────────────────
    rsi      = calc_rsi(c)
    macd, macd_sig, macd_hist = calc_macd(c)
    bb_up, bb_mid, bb_low, pct_b = calc_bollinger(c)
    k_stoch, d_stoch  = calc_stochastic(h, l, c)
    atr      = calc_atr(h, l, c)
    adx, di_pos, di_neg = calc_adx(h, l, c)
    cci      = calc_cci(h, l, c)
    willr    = calc_williams_r(h, l, c)
    mfi      = calc_mfi(h, l, c, v)
    obv      = calc_obv(c, v)
    vwap     = calc_vwap(h, l, c, v)
    emas     = calc_emas(c)
    momentum = calc_momentum(c)
    roc      = calc_roc(c)
    velocity = calc_velocity(c, v)

    # SMC
    structure  = detect_market_structure(c, h, l)
    obs        = detect_order_blocks(o, h, l, c)
    fvgs       = detect_fvg(h, l, c)
    pd_zone    = detect_premium_discount(h, l, c)
    liquidity  = detect_liquidity_zones(h, l, c, v)
    trend      = analyse_trend(c, emas)
    vol_data   = analyse_volume(v, c)
    mm_data    = detect_market_maker_activity(o, h, l, c, v)

    # ── Latest values ───────────────────────────
    rsi_val    = rsi.iloc[-1]
    macd_val   = macd.iloc[-1]
    msig_val   = macd_sig.iloc[-1]
    mhist_val  = macd_hist.iloc[-1]
    stoch_k    = k_stoch.iloc[-1]
    adx_val    = adx.iloc[-1]
    cci_val    = cci.iloc[-1]
    willr_val  = willr.iloc[-1]
    mfi_val    = mfi.iloc[-1]
    pct_b_val  = pct_b.iloc[-1]
    obv_slope  = float(np.polyfit(range(5), obv.iloc[-5:], 1)[0])
    cur_price  = c.iloc[-1]
    vwap_val   = vwap.iloc[-1]

    # ── Score each factor 0-10 ──────────────────

    # RSI score: best when 40-60 (momentum building), rising
    rsi_rising = rsi.diff().iloc[-3:].mean() > 0
    if   50 <= rsi_val <= 65 and rsi_rising: rsi_score = 9
    elif 45 <= rsi_val < 50  and rsi_rising: rsi_score = 7
    elif 35 <= rsi_val < 45  and rsi_rising: rsi_score = 6
    elif rsi_val > 65:                       rsi_score = 4   # overbought
    elif rsi_val < 35:                       rsi_score = 3   # oversold (no momentum yet)
    else:                                    rsi_score = 5

    # MACD score
    macd_cross = (macd.iloc[-2] < macd_sig.iloc[-2]) and (macd_val > msig_val)
    if   macd_cross:                              macd_score = 9
    elif macd_val > msig_val and mhist_val > 0:  macd_score = 7
    elif mhist_val > 0:                           macd_score = 5
    else:                                         macd_score = 3

    # Bollinger score: price above mid, not overbought
    if   0.5 <= pct_b_val <= 0.75: bb_score = 8
    elif 0.3 <= pct_b_val < 0.5:   bb_score = 6
    elif pct_b_val > 0.9:          bb_score = 3   # overbought band
    else:                          bb_score = 5

    # Stochastic score
    stoch_cross = (k_stoch.iloc[-2] < d_stoch.iloc[-2]) and (stoch_k > d_stoch.iloc[-1])
    if   stoch_cross and stoch_k < 80:  stoch_score = 9
    elif stoch_k > d_stoch.iloc[-1] and stoch_k < 70: stoch_score = 7
    elif stoch_k > 80:                  stoch_score = 3
    else:                               stoch_score = 5

    # ADX score: strong trend = good
    if   adx_val > 35:  adx_score = 9
    elif adx_val > 25:  adx_score = 7
    elif adx_val > 20:  adx_score = 5
    else:               adx_score = 3   # no trend

    # Volume score
    vol_score = min(10, round(vol_data["vol_ratio"] * 4))
    if vol_data["pv_confirm"]: vol_score = min(10, vol_score + 2)

    # OBV trend score
    if   obv_slope > 0: obv_score = 8
    else:               obv_score = 3

    # VWAP score: price above VWAP = bullish
    if   cur_price > vwap_val * 1.005: vwap_score = 8
    elif cur_price > vwap_val:         vwap_score = 6
    else:                              vwap_score = 3

    # Trend EMA score
    trend_score = round(trend["score"])

    # MFI score (money flow)
    if   50 < mfi_val < 80:  mfi_score = 8
    elif mfi_val >= 80:      mfi_score = 4
    elif mfi_val <= 30:      mfi_score = 3
    else:                    mfi_score = 5

    # CCI score
    if   100 < cci_val < 200: cci_score = 8
    elif cci_val > 200:       cci_score = 4
    elif 0 < cci_val <= 100:  cci_score = 6
    else:                     cci_score = 3

    # Williams %R score
    if   -50 < willr_val < -20: willr_score = 8
    elif willr_val > -20:       willr_score = 4
    elif willr_val < -80:       willr_score = 3
    else:                       willr_score = 5

    # SMC Scores
    struct_score = 5
    if structure["bias"] == "bullish":  struct_score = 7
    if structure["bos"]:                struct_score = 9
    if structure["choch"] and structure["bias"] == "bullish": struct_score = 10

    ob_score  = min(10, 5 + len(obs) * 2)
    fvg_score = min(10, 5 + len(fvgs) * 2)

    pd_score  = 8 if pd_zone["zone"] == "discount" else 4

    liq_score = 5
    if liquidity["inducement_bullish"]: liq_score = 9
    if liquidity["volume_surge"]:       liq_score = min(10, liq_score + 1)

    mm_score  = min(10, 5 + mm_data["mm_score"])

    # Velocity / Momentum score
    if   velocity > 2:   vel_score = 9
    elif velocity > 0.5: vel_score = 7
    elif velocity > 0:   vel_score = 5
    else:                vel_score = 2

    mom_val = momentum.iloc[-1]
    if   mom_val > 10:  mom_score = 9
    elif mom_val > 3:   mom_score = 7
    elif mom_val > 0:   mom_score = 5
    else:               mom_score = 2

    # ── Weighted composite pump score ───────────
    weights = {
        "rsi"       : 0.09,
        "macd"      : 0.08,
        "volume"    : 0.10,
        "velocity"  : 0.08,
        "momentum"  : 0.07,
        "structure" : 0.09,
        "liquidity" : 0.07,
        "trend"     : 0.08,
        "ob"        : 0.06,
        "fvg"       : 0.05,
        "pd"        : 0.05,
        "adx"       : 0.05,
        "mfi"       : 0.04,
        "stoch"     : 0.04,
        "obv"       : 0.03,
        "mm"        : 0.02,
    }
    scores = {
        "rsi"       : rsi_score,
        "macd"      : macd_score,
        "volume"    : vol_score,
        "velocity"  : vel_score,
        "momentum"  : mom_score,
        "structure" : struct_score,
        "liquidity" : liq_score,
        "trend"     : trend_score,
        "ob"        : ob_score,
        "fvg"       : fvg_score,
        "pd"        : pd_score,
        "adx"       : adx_score,
        "mfi"       : mfi_score,
        "stoch"     : stoch_score,
        "obv"       : obv_score,
        "mm"        : mm_score,
        "cci"       : cci_score,
        "willr"     : willr_score,
    }
    pump_score = sum(scores[k] * weights[k] for k in weights)
    pump_score = round(min(10, pump_score), 2)

    return {
        "pump_score"    : pump_score,
        "scores"        : scores,
        "rsi"           : round(rsi_val, 2),
        "macd_hist"     : round(mhist_val, 6),
        "adx"           : round(adx_val, 2),
        "stoch_k"       : round(stoch_k, 2),
        "pct_b"         : round(pct_b_val, 3),
        "mfi"           : round(mfi_val, 2),
        "cci"           : round(cci_val, 2),
        "williams_r"    : round(willr_val, 2),
        "velocity"      : round(velocity, 4),
        "momentum_pct"  : round(mom_val, 2),
        "vol_ratio"     : vol_data["vol_ratio"],
        "vol_surge"     : vol_data["surge"],
        "pv_confirm"    : vol_data["pv_confirm"],
        "trend_label"   : trend["label"],
        "trend_score"   : trend["score"],
        "structure"     : structure,
        "order_blocks"  : len(obs),
        "fvg_count"     : len(fvgs),
        "pd_zone"       : pd_zone["zone"],
        "pd_pct"        : pd_zone["pct_position"],
        "inducement"    : liquidity["inducement_bullish"],
        "mm_accumulation": mm_data["accumulation"],
        "current_price" : cur_price,
        "vwap"          : round(vwap_val, 6),
        "above_vwap"    : cur_price > vwap_val,
    }
