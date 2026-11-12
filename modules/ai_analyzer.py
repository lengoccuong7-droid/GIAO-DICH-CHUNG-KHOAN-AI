"""Trợ lý diễn giải offline theo luật; không gọi mô hình AI/Internet."""
import pandas as pd
from .support_resistance import find_support_resistance

def run_ai_analysis(enriched: pd.DataFrame, symbol: str):
    if enriched is None or enriched.empty:
        return {"summary": "Không có dữ liệu để phân tích.", "bullish": [], "risks": []}
    r = enriched.iloc[-1]
    bullish, risks, observations = [], [], []
    def val(k):
        x = r.get(k)
        return None if pd.isna(x) else float(x)
    close, sma20, sma50 = val('close'), val('SMA20'), val('SMA50')
    rsi, macdh, relvol, adx = val('RSI14'), val('MACD_HIST'), val('REL_VOLUME20'), val('ADX14')
    if close is not None and sma20 is not None:
        (bullish if close > sma20 else risks).append('Giá đóng cửa nằm trên MA20.' if close > sma20 else 'Giá đóng cửa nằm dưới MA20.')
    if close is not None and sma50 is not None:
        (bullish if close > sma50 else risks).append('Giá nằm trên MA50.' if close > sma50 else 'Giá nằm dưới MA50.')
    if rsi is not None:
        observations.append(f'RSI14 = {rsi:.2f}.')
        if rsi >= 70: risks.append('RSI vào vùng quá mua; tránh mua đuổi.')
        elif rsi >= 50: bullish.append('RSI trên 50, động lượng nghiêng tích cực.')
        else: risks.append('RSI dưới 50, động lượng chưa xác nhận tăng.')
    if macdh is not None:
        (bullish if macdh > 0 else risks).append('MACD Histogram dương.' if macdh > 0 else 'MACD Histogram âm.')
    if relvol is not None:
        observations.append(f'Khối lượng tương đối 20 phiên = {relvol:.2f} lần.')
        if relvol < 1: risks.append('Khối lượng thấp hơn trung bình 20 phiên.')
        else: bullish.append('Khối lượng đạt/vượt trung bình 20 phiên.')
    if adx is not None: observations.append(f'ADX14 = {adx:.2f}.')
    sr = find_support_resistance(enriched)
    if sr['support'] is not None:
        observations.append(f'Hỗ trợ tham chiếu: {sr["support"]:,.2f}; kháng cự tham chiếu: {sr["resistance"]:,.2f}.')
    summary = f'{symbol}: có {len(bullish)} yếu tố tích cực và {len(risks)} yếu tố rủi ro được nhận diện. Đây là diễn giải theo luật cố định, không phải dự báo chắc chắn.'
    return {"summary": summary, "bullish": bullish, "risks": risks,
            "observations": observations, "support_resistance": sr,
            "engine": "Offline rule-based; không gọi AI cloud"}
