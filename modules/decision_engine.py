from __future__ import annotations
import math
import pandas as pd

def make_trading_decision(df: pd.DataFrame, capital_vnd=100_000_000,
                          risk_per_trade_pct=1.0, max_allocation_pct=20.0,
                          lot_size=100, price_multiplier=1.0):
    if df is None or len(df) < 20:
        return {"decision":"CHƯA ĐỦ DỮ LIỆU","reasons":["Cần tối thiểu 20 phiên OHLCV hợp lệ."]}
    last = df.iloc[-1]
    needed = ["close","SMA20","RSI14","ATR14","VOL_MA20","REL_VOLUME20"]
    missing = [k for k in needed if k not in df.columns or pd.isna(last.get(k))]
    if missing:
        return {"decision":"CHƯA ĐỦ DỮ LIỆU","reasons":["Thiếu chỉ báo: "+", ".join(missing)]}
    close=float(last.close); ma20=float(last.SMA20); rsi=float(last.RSI14); atr=float(last.ATR14)
    ma50 = last.get("SMA50"); macdh = last.get("MACD_HIST"); adx=last.get("ADX14")
    if close <= 0 or atr <= 0:
        return {"decision":"KHÔNG ĐỦ ĐIỀU KIỆN","reasons":["Giá hoặc ATR không hợp lệ."]}
    trend = "TĂNG" if close > ma20 and (pd.isna(ma50) or close > ma50) else ("GIẢM" if close < ma20 else "ĐI NGANG")
    momentum = "TÍCH CỰC" if rsi >= 50 and (pd.isna(macdh) or macdh >= 0) else "YẾU"
    relvol=float(last.REL_VOLUME20)
    entry_low=max(0.01, close-0.5*atr)
    entry_high=close
    stop=max(0.01, close-1.5*atr)
    target=close+3*atr
    rr=(target-close)/(close-stop) if close>stop else 0
    reasons=[f"Xu hướng: {trend}.",f"Động lượng: {momentum}; RSI14={rsi:.2f}.",
             f"Khối lượng tương đối 20 phiên: {relvol:.2f} lần."]
    if pd.notna(adx): reasons.append(f"ADX14={float(adx):.2f}.")
    if trend=="TĂNG" and momentum=="TÍCH CỰC" and relvol>=1 and rr>=1.5:
        decision="THEO DÕI ĐIỂM MUA"
    elif trend=="GIẢM":
        decision="KHÔNG MUA MỚI"
    else:
        decision="CHỜ XÁC NHẬN"
    risk_budget=capital_vnd*risk_per_trade_pct/100
    risk_per_share=(close-stop)*price_multiplier
    qty_risk=int(risk_budget/risk_per_share) if risk_per_share>0 else 0
    qty_cap=int((capital_vnd*max_allocation_pct/100)/(close*price_multiplier))
    qty=max(0,min(qty_risk,qty_cap)); qty=(qty//lot_size)*lot_size
    return {"decision":decision,"trend":trend,"momentum":momentum,"reasons":reasons,
            "close":close,"buy_zone_low":entry_low,"buy_zone_high":entry_high,
            "stop_loss":stop,"target":target,"reward_risk":rr,
            "suggested_quantity":qty,"position_value":qty*close*price_multiplier,
            "risk_budget":risk_budget,"rel_volume20":relvol}
