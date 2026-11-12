from __future__ import annotations
import numpy as np
import pandas as pd

def _safe_div(a, b):
    return a / b.replace(0, np.nan)

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tính chỉ báo trên một mã, dữ liệu phải theo ngày tăng dần."""
    x = df.copy().sort_values("date").reset_index(drop=True)
    o,h,l,c,v = (x[k].astype(float) for k in ("open","high","low","close","volume"))

    # Trend: SMA/EMA
    for n in (10,20,50,100,200):
        x[f"SMA{n}"] = c.rolling(n, min_periods=n).mean()
    for n in (12,20,26,50,200):
        x[f"EMA{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()

    # RSI Wilder
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = _safe_div(avg_gain, avg_loss)
    x["RSI14"] = 100 - (100 / (1 + rs))
    x.loc[(avg_loss == 0) & (avg_gain > 0), "RSI14"] = 100
    x.loc[(avg_loss == 0) & (avg_gain == 0), "RSI14"] = 50

    # MACD 12,26,9
    macd = c.ewm(span=12, adjust=False, min_periods=26).mean() - c.ewm(span=26, adjust=False, min_periods=26).mean()
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    x["MACD"] = macd
    x["MACD_SIGNAL"] = signal
    x["MACD_HIST"] = macd - signal

    # True range, ATR Wilder
    prev = c.shift(1)
    tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    x["TR"] = tr
    x["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    # Bollinger 20,2
    mid = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std(ddof=0)
    x["BB_MID"], x["BB_UPPER"], x["BB_LOWER"] = mid, mid+2*sd, mid-2*sd
    x["BB_WIDTH"] = _safe_div(x["BB_UPPER"]-x["BB_LOWER"], mid)

    # Stochastic 14,3
    ll, hh = l.rolling(14, min_periods=14).min(), h.rolling(14, min_periods=14).max()
    x["STOCH_K"] = 100 * _safe_div(c-ll, hh-ll)
    x["STOCH_D"] = x["STOCH_K"].rolling(3, min_periods=3).mean()

    # CCI 20
    tp = (h+l+c)/3
    tp_ma = tp.rolling(20, min_periods=20).mean()
    mad = tp.rolling(20, min_periods=20).apply(lambda a: np.mean(np.abs(a-a.mean())), raw=True)
    x["CCI20"] = _safe_div(tp-tp_ma, 0.015*mad)

    # ROC 12 and Williams %R
    x["ROC12"] = 100 * (c / c.shift(12) - 1)
    x["WILLIAMS_R14"] = -100 * _safe_div(hh-c, hh-ll)

    # MFI 14
    raw_mf = tp*v
    pos = raw_mf.where(tp > tp.shift(1), 0.0)
    neg = raw_mf.where(tp < tp.shift(1), 0.0)
    pos_sum = pos.rolling(14, min_periods=14).sum()
    neg_sum = neg.rolling(14, min_periods=14).sum()
    mfr = _safe_div(pos_sum, neg_sum)
    x["MFI14"] = 100 - 100/(1+mfr)
    x.loc[(neg_sum == 0) & (pos_sum > 0), "MFI14"] = 100
    x.loc[(neg_sum == 0) & (pos_sum == 0), "MFI14"] = 50

    # Volume and money flow
    x["VOL_MA20"] = v.rolling(20, min_periods=20).mean()
    x["REL_VOLUME20"] = _safe_div(v, x["VOL_MA20"])
    obv_sign = np.sign(c.diff()).fillna(0)
    x["OBV"] = (obv_sign*v).cumsum()
    mfm = _safe_div((c-l)-(h-c), h-l).fillna(0)
    mfv = mfm*v
    x["AD_LINE"] = mfv.cumsum()
    x["CMF20"] = _safe_div(mfv.rolling(20, min_periods=20).sum(), v.rolling(20, min_periods=20).sum())
    typical = tp
    x["VWAP20"] = _safe_div((typical*v).rolling(20,min_periods=20).sum(), v.rolling(20,min_periods=20).sum())

    # ADX 14 (Wilder smoothing)
    up = h.diff()
    down = -l.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=x.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=x.index)
    atr = x["ATR14"]
    plus_di = 100 * _safe_div(plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean(), atr)
    minus_di = 100 * _safe_div(minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean(), atr)
    dx = 100 * _safe_div((plus_di-minus_di).abs(), plus_di+minus_di)
    x["PLUS_DI14"], x["MINUS_DI14"] = plus_di, minus_di
    x["ADX14"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    # Ichimoku (unshifted raw spans; no forward plotting)
    tenkan = (h.rolling(9,min_periods=9).max()+l.rolling(9,min_periods=9).min())/2
    kijun = (h.rolling(26,min_periods=26).max()+l.rolling(26,min_periods=26).min())/2
    span_a = (tenkan+kijun)/2
    span_b = (h.rolling(52,min_periods=52).max()+l.rolling(52,min_periods=52).min())/2
    x["ICHIMOKU_TENKAN"], x["ICHIMOKU_KIJUN"] = tenkan, kijun
    x["ICHIMOKU_SPAN_A_RAW"], x["ICHIMOKU_SPAN_B_RAW"] = span_a, span_b

    # Pivot points from previous candle
    ph, pl, pc = h.shift(1), l.shift(1), c.shift(1)
    pivot = (ph+pl+pc)/3
    x["PIVOT"] = pivot
    x["PIVOT_R1"], x["PIVOT_S1"] = 2*pivot-pl, 2*pivot-ph

    # Supertrend 10,3 (iterative; unavailable until ATR exists)
    atr10 = tr.ewm(alpha=1/10, adjust=False, min_periods=10).mean()
    basic_ub, basic_lb = (h+l)/2 + 3*atr10, (h+l)/2 - 3*atr10
    final_ub = basic_ub.copy(); final_lb = basic_lb.copy()
    st_line = pd.Series(np.nan, index=x.index)
    for i in range(1, len(x)):
        if pd.notna(basic_ub.iloc[i]) and pd.notna(basic_lb.iloc[i]):
            final_ub.iloc[i] = basic_ub.iloc[i] if (basic_ub.iloc[i] < final_ub.iloc[i-1] or c.iloc[i-1] > final_ub.iloc[i-1]) else final_ub.iloc[i-1]
            final_lb.iloc[i] = basic_lb.iloc[i] if (basic_lb.iloc[i] > final_lb.iloc[i-1] or c.iloc[i-1] < final_lb.iloc[i-1]) else final_lb.iloc[i-1]
            prev_st = st_line.iloc[i-1]
            if pd.isna(prev_st):
                st_line.iloc[i] = final_ub.iloc[i] if c.iloc[i] <= final_ub.iloc[i] else final_lb.iloc[i]
            elif prev_st == final_ub.iloc[i-1]:
                st_line.iloc[i] = final_ub.iloc[i] if c.iloc[i] <= final_ub.iloc[i] else final_lb.iloc[i]
            else:
                st_line.iloc[i] = final_lb.iloc[i] if c.iloc[i] >= final_lb.iloc[i] else final_ub.iloc[i]
    x["SUPERTREND10_3"] = st_line
    return x
