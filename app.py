from __future__ import annotations
import io, json, math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import APP_NAME, DEFAULT_CAPITAL_VND, APP_VERSION
from modules.data_loader import load_market_file
from modules.indicators import add_indicators
from modules.support_resistance import find_support_resistance
from modules.data_quality import assess_data_quality
from modules.backtest import simple_swing_backtest
from modules.risk_manager import calculate_position_size
from modules.relative_strength import relative_strength

st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.1rem;padding-bottom:2rem}
[data-testid="stMetricValue"]{font-size:1.35rem}
.stTabs [data-baseweb="tab-list"]{gap:.25rem;flex-wrap:nowrap;overflow-x:auto}
.stTabs [data-baseweb="tab"]{white-space:nowrap;padding:.55rem .7rem}
@media(max-width:700px){.block-container{padding-left:.8rem;padding-right:.8rem}.stTabs [data-baseweb="tab"]{font-size:.78rem}}
.signal-card{padding:1rem;border-radius:12px;background:rgba(128,128,128,.10);border:1px solid rgba(128,128,128,.25)}
</style>
""", unsafe_allow_html=True)
st.title(APP_NAME)
st.caption(f"V{APP_VERSION} · Phân tích dữ liệu lịch sử và mô phỏng · Không đặt lệnh tự động")

# -------------------- Helpers --------------------
def fmt(v, digits=2):
    try:
        if v is None or pd.isna(v) or not np.isfinite(float(v)): return "Chưa đủ dữ liệu"
        return f"{float(v):,.{digits}f}"
    except Exception: return "Chưa đủ dữ liệu"

def read_upload(up, hint=None):
    if up is None: return None
    return load_market_file(up, symbol_hint=hint)

def enrich(frame):
    x=add_indicators(frame.sort_values("date").copy())
    x["LOG_RETURN"] = np.log(x.close / x.close.shift(1))
    x["CLV"] = np.where((x.high-x.low)!=0, ((x.close-x.low)-(x.high-x.close))/(x.high-x.low), np.nan)
    vol_mean=x.volume.rolling(20,min_periods=20).mean()
    vol_std=x.volume.rolling(20,min_periods=20).std(ddof=0)
    x["VOLUME_ZSCORE"]=(x.volume-vol_mean)/vol_std.replace(0,np.nan)
    x["TURNOVER"] = x.close*x.volume
    x["ILLIQUIDITY_AMIHUD"] = (x.LOG_RETURN.abs()/x.TURNOVER.replace(0,np.nan)).rolling(20,min_periods=20).mean()
    return x

def annualized_gk(x):
    if len(x)<20:return None
    term=.5*np.log(x.high/x.low)**2-(2*np.log(2)-1)*np.log(x.close/x.open)**2
    v=term.replace([np.inf,-np.inf],np.nan).dropna()
    return float(np.sqrt(max(v.mean(),0)*252)*100) if len(v)>=10 else None

def annualized_parkinson(x):
    if len(x)<20:return None
    v=(np.log(x.high/x.low)**2).replace([np.inf,-np.inf],np.nan).dropna()
    return float(np.sqrt(v.mean()/(4*np.log(2))*252)*100) if len(v)>=10 else None

def hurst_rs(series):
    s=pd.Series(series).dropna().astype(float).values
    if len(s)<100:return None
    lags=[8,16,32,64]
    vals=[]
    for lag in lags:
        chunks=[]
        for i in range(0,len(s)-lag+1,lag):
            z=s[i:i+lag]; z=z-z.mean(); sd=z.std()
            if sd>0: chunks.append((z.cumsum().max()-z.cumsum().min())/sd)
        if chunks: vals.append((lag,float(np.mean(chunks))))
    if len(vals)<3:return None
    return float(np.polyfit(np.log([a for a,b in vals]),np.log([b for a,b in vals]),1)[0])

def return_entropy(series, bins=10):
    s=pd.Series(series).dropna().astype(float)
    if len(s)<50:return None
    counts=np.histogram(s,bins=bins)[0].astype(float)
    p=counts[counts>0]/counts.sum()
    return float(-(p*np.log(p)).sum()/np.log(bins))

def audit_flags(x):
    flags=[]
    if x.empty:return flags
    last=x.iloc[-1]
    if len(x)>1:
        prev=x.iloc[-2]
        if last.close>0 and prev.close>0 and abs(last.close/prev.close-1)>.25:
            flags.append("Biến động giá ngày gần nhất vượt 25%: kiểm tra điều chỉnh giá, chia tách hoặc dữ liệu lỗi.")
    if (x.volume==0).any(): flags.append(f"Có {(x.volume==0).sum()} phiên khối lượng bằng 0.")
    if x.date.duplicated().any(): flags.append("Có ngày giao dịch trùng lặp.")
    if x.date.is_monotonic_increasing is False: flags.append("Ngày chưa sắp xếp tăng dần.")
    return flags

# -------------------- Sidebar: all inputs --------------------
with st.sidebar:
    st.header("DỮ LIỆU & THÔNG SỐ")
    main_file=st.file_uploader("1. Dữ liệu OHLCV chính",type=["csv","xlsx","xls","txt","json","parquet"],key="main_ohlcv")
    symbol_hint=st.text_input("Mã cổ phiếu (nếu file chỉ có một mã)","",key="symbol_hint")
    sheet=st.text_input("Tên sheet Excel (để trống = sheet đầu)","",key="sheet_name")
    benchmark_file=st.file_uploader("2. Dữ liệu VN-Index (không bắt buộc)",type=["csv","xlsx","xls","txt"],key="benchmark_file")
    sector_file=st.file_uploader("3. Dữ liệu chỉ số ngành / nhóm ngành (không bắt buộc)",type=["csv","xlsx","xls","txt"],key="sector_file")
    st.divider()
    position_mode=st.radio("TRẠNG THÁI VỊ THẾ",["🟢 CHƯA CÓ HÀNG – Cầm tiền","🔵 ĐANG CÓ HÀNG – Cầm cổ phiếu"],key="position_mode")
    nav=st.number_input("Tổng NAV (VND)",min_value=0,value=int(DEFAULT_CAPITAL_VND),step=5_000_000)
    risk_pct=st.number_input("Rủi ro tối đa / giao dịch (%)",min_value=.1,max_value=5.0,value=1.0,step=.1)
    max_alloc=st.number_input("Tỷ trọng tối đa / mã (%)",min_value=1.0,max_value=100.0,value=20.0,step=1.0)
    lot=st.number_input("Bước lô",min_value=1,value=100,step=1)
    fee=st.number_input("Phí mỗi chiều (%)",min_value=0.0,max_value=2.0,value=.15,step=.01)
    slip=st.number_input("Trượt giá mỗi chiều (%)",min_value=0.0,max_value=2.0,value=.10,step=.01)
    st.caption("Các mục bên dưới chỉ dùng khi đang có vị thế.")
    qty=st.number_input("Số lượng đang nắm giữ",min_value=0,value=0,step=100)
    entry=st.number_input("Giá vốn (đồng/cp)",min_value=0.0,value=0.0,step=100.0)
    stop_assumption=st.number_input("Giá dừng lỗ giả định (đồng/cp)",min_value=0.0,value=0.0,step=100.0)
    st.caption("Nếu thiếu dữ liệu benchmark/ngành, tab RS sẽ ghi rõ chưa đủ dữ liệu.")

# Parse uploads with safe error reporting
main_data=bench_data=sector_data=None
load_errors=[]
try:
    if main_file:
        main_data=load_market_file(main_file,sheet_name=(sheet.strip() or 0),symbol_hint=symbol_hint.strip() or None)
except Exception as e: load_errors.append(f"OHLCV: {e}")
try:
    if benchmark_file: bench_data=load_market_file(benchmark_file,symbol_hint="VNINDEX")
except Exception as e: load_errors.append(f"VN-Index: {e}")
try:
    if sector_file: sector_data=load_market_file(sector_file,symbol_hint="SECTOR")
except Exception as e: load_errors.append(f"Ngành: {e}")
for e in load_errors: st.sidebar.error(e)

if main_data is not None:
    symbols=sorted(main_data.symbol.astype(str).unique().tolist())
    with st.sidebar:
        selected_symbol=st.selectbox("Mã phân tích",symbols,index=0)
else: selected_symbol=None

if main_data is not None and selected_symbol:
    raw=main_data[main_data.symbol.astype(str)==selected_symbol].sort_values("date").reset_index(drop=True)
    data=enrich(raw)
else:
    raw=data=None

# -------------------- 5 tabs --------------------
tabs=st.tabs([
    "1 · TRADING DASHBOARD",
    "2 · MONEY FLOW & LIQUIDITY",
    "3 · RELATIVE STRENGTH & SECTOR",
    "4 · QUANT LAB & BACKTEST",
    "5 · RAW DATA & AUDIT",
])

# TAB 1
with tabs[0]:
    st.subheader("Bản đồ giao dịch thực chiến")
    if data is None:
        st.info("Tải dữ liệu OHLCV ở Sidebar để bắt đầu. Các dữ liệu VN-Index/ngành là tùy chọn.")
    else:
        last=data.iloc[-1]; sr=find_support_resistance(data)
        close=float(last.close); atr=last.get("ATR14")
        sup=sr.get("support"); res=sr.get("resistance")
        buy_low=float(sup) if sup is not None else None
        buy_high=float(sup+0.5*atr) if sup is not None and pd.notna(atr) else None
        confirm=float(res+0.1*atr) if res is not None and pd.notna(atr) else None
        stop=float(sup-0.5*atr) if sup is not None and pd.notna(atr) else None
        tp1=float(res) if res is not None else None
        tp2=float(res+2*atr) if res is not None and pd.notna(atr) else None
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Mã",selected_symbol); m2.metric("Giá đóng cửa",fmt(close)); m3.metric("ATR14",fmt(atr)); m4.metric("Xu hướng", "Tăng" if pd.notna(last.get("SMA20")) and pd.notna(last.get("SMA50")) and close>last.SMA20>last.SMA50 else "Chưa xác nhận")
        st.markdown("#### Biểu đồ giá và các vùng tham chiếu")
        chart=data.tail(120)
        fig=go.Figure(data=[go.Candlestick(
            x=chart["date"],open=chart["open"],high=chart["high"],
            low=chart["low"],close=chart["close"],name=selected_symbol
        )])
        if buy_low is not None and buy_high is not None:
            fig.add_hrect(y0=buy_low,y1=buy_high,fillcolor="green",opacity=.13,line_width=0,annotation_text="Mua gom")
        if confirm is not None:
            fig.add_hline(y=confirm,line_dash="dash",line_color="royalblue",annotation_text="Breakout")
        if tp1 is not None:
            fig.add_hline(y=tp1,line_dash="dot",line_color="orange",annotation_text="Chốt lời")
        if stop is not None:
            fig.add_hline(y=stop,line_dash="dash",line_color="red",annotation_text="Stop-loss")
        fig.update_layout(height=430,margin=dict(l=10,r=10,t=25,b=10),xaxis_rangeslider_visible=False,
                          template="plotly_dark",showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":True,"scrollZoom":True})
        st.caption("Biểu đồ nến OHLCV tương tác. Vùng giá được tính từ pivot hỗ trợ/kháng cự và ATR; đây là vùng tham chiếu, không phải mức giá chắc chắn.")
        zone=pd.DataFrame([
            ["🟩 Mua gom",buy_low,buy_high],
            ["🔵 Xác nhận / Breakout",confirm,confirm],
            ["🟠 Chốt lời",tp1,tp2],
            ["🔴 Vô hiệu / Stop-loss",stop,stop],
        ],columns=["Vùng","Từ giá","Đến giá"])
        zone["Từ giá"]=zone["Từ giá"].map(fmt); zone["Đến giá"]=zone["Đến giá"].map(fmt)
        st.dataframe(zone,use_container_width=True,hide_index=True)
        st.markdown("#### Chỉ dẫn hành động theo trạng thái vị thế")
        bullish=bool(pd.notna(last.get("SMA20")) and pd.notna(last.get("SMA50")) and close>last.SMA20>last.SMA50 and pd.notna(last.get("RSI14")) and last.RSI14>=50)
        if position_mode.startswith("🟢"):
            if buy_low is not None and buy_high is not None and buy_low<=close<=buy_high and bullish:
                action="Đang gần vùng mua gom theo mô hình. Chỉ xem xét giải ngân từng phần sau khi kiểm tra thanh khoản và mức dừng lỗ."
            elif confirm is not None and close>=confirm:
                action="Giá đang ở/vượt vùng xác nhận tham chiếu. Tránh mua đuổi nếu biên độ đã mở rộng; cần kiểm tra khối lượng và rủi ro."
            else: action="CHỜ QUAN SÁT. Giá chưa đồng thời thỏa điều kiện vùng giá và xu hướng của bộ quy tắc."
        else:
            pnl_pct=(close/entry-1)*100 if entry>0 else None
            action=f"Đang nắm giữ {qty:,} cổ phiếu. Lãi/lỗ tạm tính {pnl_pct:+.2f}% theo giá đóng cửa." if pnl_pct is not None else "Đã chọn trạng thái đang có hàng nhưng chưa nhập giá vốn; cập nhật giá vốn và số lượng ở Sidebar."
            if stop is not None and close<=stop: action+=" Giá đã xuống dưới mức vô hiệu tham chiếu; cần rà soát rủi ro vị thế."
            elif tp1 is not None and close>=tp1: action+=" Giá đã chạm vùng kháng cự/chốt lời tham chiếu; cân nhắc đánh giá lại tỷ trọng."
        st.markdown(f'<div class="signal-card"><b>HÀNH ĐỘNG:</b><br>{action}</div>',unsafe_allow_html=True)
        if position_mode.startswith("🟢") and nav>0 and buy_high and stop and buy_high>stop:
            sizing=calculate_position_size(nav,buy_high,stop,risk_pct,max_alloc,int(lot))
            st.caption(f"Khối lượng tối đa theo ngân sách rủi ro mô phỏng: {sizing['quantity']:,} cp · Giá trị vị thế {sizing['position_value']:,.0f} VND. Đây là phép tính tham khảo, không phải khuyến nghị mua.")

# TAB 2
with tabs[1]:
    st.subheader("Dòng tiền, thanh khoản & cảnh báo bất thường")
    if data is None: st.info("Cần dữ liệu OHLCV ở Sidebar.")
    else:
        r=data.iloc[-1]
        cols=st.columns(5)
        for col,label,key in zip(cols,["Volume","OBV","MFI14","Volume Z-Score","CMF20"],["volume","OBV","MFI14","VOLUME_ZSCORE","CMF20"]): col.metric(label,fmt(r.get(key),0 if key=="volume" else 2))
        st.line_chart(data.tail(120).set_index("date")[["volume"]],height=220)
        st.markdown("#### Cảnh báo mẫu hình cần kiểm tra")
        flags=[]
        if len(data)>=2:
            prev=data.iloc[-2]
            candle_range=(r.high-r.low)/r.close if r.close else 0
            lower_wick=(min(r.open,r.close)-r.low)/(r.high-r.low) if r.high>r.low else 0
            if lower_wick>.55 and r.volume>1.5*data.volume.tail(20).mean(): flags.append("Râu nến dưới dài kèm khối lượng cao: có thể là nhịp rũ bỏ/quét thanh khoản; cần xác nhận các phiên sau.")
            if candle_range<.01 and r.volume>data.volume.tail(20).median()*1.5: flags.append("Biên độ nến hẹp nhưng khối lượng cao: cần kiểm tra chất lượng giao dịch; không đủ căn cứ kết luận quay tay.")
        if flags:
            for f in flags: st.warning(f)
        else: st.info("Chưa phát hiện mẫu hình cảnh báo theo các ngưỡng sàng lọc đơn giản hiện tại.")
        avg_turnover=float(data.TURNOVER.tail(20).mean()) if len(data)>=20 else None
        amihud=r.get("ILLIQUIDITY_AMIHUD")
        days=(qty/(data.volume.tail(20).mean()*.1)) if qty>0 and len(data)>=20 and data.volume.tail(20).mean()>0 else None
        a,b,c=st.columns(3); a.metric("Amihud 20 phiên",fmt(amihud,8)); b.metric("GTGD bình quân 20 phiên",fmt(avg_turnover,0)); c.metric("Ngày thoát vị thế ước tính",fmt(days,1))
        st.caption("Days to Liquidate giả định tham gia tối đa 10% khối lượng bình quân/ngày. Amihud phụ thuộc đơn vị giá và khối lượng của file; chỉ so sánh tương đối trong cùng quy ước dữ liệu.")

# TAB 3
with tabs[2]:
    st.subheader("Sức mạnh tương đối & cấu trúc ngành")
    if data is None: st.info("Cần dữ liệu OHLCV chính.")
    else:
        bench_frame=bench_data[bench_data.symbol==bench_data.symbol.iloc[0]] if bench_data is not None else None
        sector_frame=sector_data[sector_data.symbol==sector_data.symbol.iloc[0]] if sector_data is not None else None
        rsb=relative_strength(raw,bench_frame,20)
        rss=relative_strength(raw,sector_frame,20)
        a,b,c=st.columns(3); a.metric("Sinh lời mã 20 phiên",fmt(rsb.get("return_pct"))+"%" if rsb.get("return_pct") is not None else "Chưa đủ dữ liệu")
        b.metric("Vượt/trội VN-Index",fmt(rsb.get("relative_return_pct"))+"%" if rsb.get("relative_return_pct") is not None else "Cần tải VN-Index")
        c.metric("Vượt/trội chỉ số ngành",fmt(rss.get("relative_return_pct"))+"%" if rss.get("relative_return_pct") is not None else "Cần tải chỉ số ngành")
        if bench_frame is None: st.warning("Chưa có dữ liệu VN-Index: tải file VN-Index ở Sidebar để tính RS so với thị trường.")
        if sector_frame is None: st.warning("Chưa có dữ liệu chỉ số ngành: tải file chỉ số ngành ở Sidebar để tính RS ngành.")
        st.markdown("#### Cấu trúc xu hướng đa khung tham chiếu")
        def trend(n):
            z=data.tail(n)
            if len(z)<min(n,50): return "Chưa đủ dữ liệu"
            highs=z.high; lows=z.low
            return "HH-HL (đỉnh/đáy cao dần)" if highs.iloc[-1]>highs.iloc[0] and lows.iloc[-1]>lows.iloc[0] else ("LH-LL (đỉnh/đáy thấp dần)" if highs.iloc[-1]<highs.iloc[0] and lows.iloc[-1]<lows.iloc[0] else "Đi ngang / hỗn hợp")
        t1,t2,t3=st.columns(3); t1.metric("Ngắn hạn · 20 phiên",trend(20)); t2.metric("Trung hạn · 60 phiên",trend(60)); t3.metric("Dài hạn · 120 phiên",trend(120))
        if main_data.symbol.nunique()>1:
            st.markdown("#### Tương quan lợi suất các mã trong file OHLCV")
            wide=main_data.pivot_table(index="date",columns="symbol",values="close").sort_index()
            corr=wide.pct_change().tail(60).corr() if len(wide)>20 else pd.DataFrame()
            if not corr.empty: st.dataframe(corr.style.format("{:.2f}"),use_container_width=True)
            else: st.info("Chưa đủ lịch sử đồng bộ để tính tương quan.")
        else: st.info("Muốn xem tương quan nhóm ngành, tải OHLCV nhiều mã cùng ngành trong file chính.")

# TAB 4
with tabs[3]:
    st.subheader("Quant Lab & Backtesting")
    if data is None: st.info("Cần dữ liệu OHLCV ở Sidebar.")
    else:
        h=hurst_rs(data.LOG_RETURN); ent=return_entropy(data.LOG_RETURN)
        gk=annualized_gk(data); park=annualized_parkinson(data); last=data.iloc[-1]
        c1,c2,c3,c4=st.columns(4); c1.metric("Hurst R/S",fmt(h,3)); c2.metric("Entropy chuẩn hóa",fmt(ent,3)); c3.metric("Garman–Klass ann.",fmt(gk)+"%" if gk is not None else "Chưa đủ dữ liệu"); c4.metric("Parkinson ann.",fmt(park)+"%" if park is not None else "Chưa đủ dữ liệu")
        st.caption("Hurst và Entropy là ước lượng thống kê trên chuỗi lợi suất; độ nhạy cao với độ dài mẫu và không dự báo chắc chắn trạng thái tương lai.")
        st.markdown("#### Máy tính quản trị vốn")
        entry_ref=float(last.close)
        stop_input=float(stop_assumption) if stop_assumption>0 else None
        if nav>0 and stop_input is not None and stop_input<entry_ref:
            calc=calculate_position_size(nav,entry_ref,stop_input,risk_pct,max_alloc,int(lot))
            q1,q2,q3=st.columns(3); q1.metric("Khối lượng tối đa",f"{calc['quantity']:,} cp"); q2.metric("Giá trị vị thế",f"{calc['position_value']:,.0f} VND"); q3.metric("Rủi ro ước tính",f"{calc['risk_amount']:,.0f} VND")
        else: st.info("Nhập giá dừng lỗ thấp hơn giá hiện tại ở Sidebar để tính khối lượng. Không tự suy diễn khi thiếu đầu vào.")
        st.markdown("#### Backtest chiến lược mẫu")
        if st.button("CHẠY BACKTEST",type="primary",key="run_backtest"):
            bt=simple_swing_backtest(raw.copy(),fee_pct=fee,slippage_pct=slip,initial_capital=float(nav or 1))
            st.session_state["last_backtest_v3"]={k:v for k,v in bt.items() if k!="equity_curve"}
            st.session_state["last_backtest_curve_v3"]=bt.get("equity_curve")
        bt=st.session_state.get("last_backtest_v3")
        if bt:
            if "error" in bt: st.warning(bt["error"])
            else:
                trades=bt.get("closed_trades",0); k=st.columns(5)
                k[0].metric("Tổng lợi nhuận",fmt(bt.get("total_return_pct"))+"%")
                k[1].metric("Số lệnh đóng",str(trades))
                k[2].metric("Tỷ lệ thắng",fmt(bt.get("win_rate_pct"))+"%" if bt.get("win_rate_pct") is not None else "Chưa có giao dịch")
                k[3].metric("Max Drawdown",fmt(bt.get("max_drawdown_pct"))+"%")
                k[4].metric("Profit Factor",fmt(bt.get("profit_factor")))
                curve=st.session_state.get("last_backtest_curve_v3")
                if curve: st.line_chart(pd.DataFrame({"Vốn mô phỏng":curve}))
                with st.expander("Chi tiết và giả định Backtest"):
                    st.json(bt)
                    st.caption("Không có giao dịch đóng thì Win rate, Profit Factor và Expectancy không có ý nghĩa; không diễn giải thành 0%.")
        else: st.caption("Chưa chạy Backtest trong phiên làm việc này.")

# TAB 5
with tabs[4]:
    st.subheader("Dữ liệu thô & kiểm toán chất lượng")
    if data is None: st.info("Tải OHLCV ở Sidebar để xem dữ liệu và kiểm toán.")
    else:
        quality=assess_data_quality(main_data)
        q1,q2,q3,q4=st.columns(4); q1.metric("Điểm chất lượng",f"{quality.get('score',0)}/100"); q2.metric("Trạng thái",quality.get("status","—")); q3.metric("Số dòng",f"{len(main_data):,}"); q4.metric("Số mã",str(main_data.symbol.nunique()))
        for issue in quality.get("issues",[]): st.warning(issue)
        flags=audit_flags(data)
        if flags:
            for f in flags: st.warning(f)
        else: st.success("Chưa phát hiện bất thường cơ bản theo các quy tắc kiểm tra hiện tại.")
        st.markdown("#### OHLCV và các cột kiểm toán")
        st.dataframe(data,use_container_width=True,hide_index=True)
        csv=data.to_csv(index=False).encode("utf-8-sig")
        xlsx_buf=io.BytesIO()
        with pd.ExcelWriter(xlsx_buf,engine="openpyxl") as writer: data.to_excel(writer,index=False,sheet_name="OHLCV_Audit")
        json_bytes=data.to_json(orient="records",date_format="iso",force_ascii=False,indent=2).encode("utf-8")
        d1,d2,d3=st.columns(3)
        d1.download_button("TẢI CSV",csv,file_name=f"{selected_symbol}_audit.csv",mime="text/csv")
        d2.download_button("TẢI EXCEL",xlsx_buf.getvalue(),file_name=f"{selected_symbol}_audit.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d3.download_button("TẢI JSON",json_bytes,file_name=f"{selected_symbol}_audit.json",mime="application/json")
        with st.expander("Kiểm toán dữ liệu gốc và giới hạn"):
            st.write("Cột gốc được giữ: date, symbol, open, high, low, close, volume.")
            st.write("Cột tính thêm: LOG_RETURN, CLV, VOLUME_ZSCORE, TURNOVER, ILLIQUIDITY_AMIHUD và các chỉ báo kỹ thuật.")
            st.write("Phát hiện biến động giá lớn chỉ tạo cảnh báo kiểm tra điều chỉnh giá; không thể xác định chắc chắn cổ tức/chia tách nếu không có dữ liệu sự kiện doanh nghiệp.")

st.divider()
st.caption("Công cụ nghiên cứu và mô phỏng. Mọi vùng giá, cảnh báo và kết quả định lượng phụ thuộc chất lượng dữ liệu, giả định và độ dài lịch sử; không phải khuyến nghị đầu tư.")
