import streamlit as st
import pandas as pd
from config import APP_NAME, DEFAULT_CAPITAL_VND
from modules.data_loader import load_market_file
from modules.market_analysis import analyze_universe
from modules.backtest import simple_swing_backtest
from modules.ai_analyzer import run_ai_analysis
from modules import tab5_excel

st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")
st.title(APP_NAME)
st.caption("Phân tích offline từ dữ liệu người dùng tải lên • Không có dữ liệu mẫu • Không tự đặt lệnh")

if "market_data" not in st.session_state:
    st.session_state.market_data = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None

tabs = st.tabs(["TAB 1 · Dữ liệu & Tổng quan","TAB 2 · Chỉ báo","TAB 3 · Trợ lý phân tích","TAB 4 · Swing & Backtest","TAB 5 · Excel/CSV độc lập"])

with tabs[0]:
    st.subheader("Nạp dữ liệu thị trường")
    up = st.file_uploader("Chọn file OHLCV", type=["csv","xlsx","xls","json","txt","parquet","pdf","docx"], key="market_upload")
    hint = st.text_input("Mã cổ phiếu nếu file chỉ có một mã (không bắt buộc)", value="")
    sheet = st.text_input("Tên sheet Excel (để trống = sheet đầu tiên)", value="")
    if up:
        try:
            sheet_arg = sheet if sheet.strip() else 0
            data = load_market_file(up, sheet_name=sheet_arg, symbol_hint=hint or None)
            st.session_state.market_data = data
            st.session_state.analysis = None
            st.success(f"Đọc thành công {len(data)} dòng, {data['symbol'].nunique()} mã.")
        except Exception as e:
            st.error(f"Không thể nạp dữ liệu: {e}")
    data = st.session_state.market_data
    if data is not None:
        st.dataframe(data, use_container_width=True)
        st.write("Số mã:", data.symbol.nunique(), "• Khoảng ngày:", data.date.min().date(), "→", data.date.max().date())
        st.download_button("Tải dữ liệu đã chuẩn hóa CSV", data.to_csv(index=False).encode("utf-8-sig"),
                           "ohlcv_normalized.csv","text/csv")

with tabs[1]:
    st.subheader("Phân tích chỉ báo kỹ thuật")
    data = st.session_state.market_data
    if data is None:
        st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        results = st.session_state.analysis
        if results is None:
            results = analyze_universe(data)
            st.session_state.analysis = results
        symbols = list(results.keys())
        selected = st.selectbox("Chọn mã", symbols, key="indicator_symbol")
        enriched, decision = results[selected]
        st.dataframe(enriched.tail(30), use_container_width=True)
        latest = enriched.iloc[-1]
        cols = st.columns(4)
        for col, key in zip(cols, ["SMA20","SMA50","SMA200","RSI14"]):
            val=latest.get(key)
            col.metric(key, "Chưa đủ dữ liệu" if pd.isna(val) else f"{val:,.2f}")

with tabs[2]:
    st.subheader("Trợ lý phân tích chuyên sâu")
    data = st.session_state.market_data
    results = st.session_state.analysis
    if data is None:
        st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        if results is None:
            results=analyze_universe(data); st.session_state.analysis=results
        for symbol,(enriched,decision) in results.items():
            with st.expander(f"{symbol} · {decision.get('decision','')}"):
                st.write("Xu hướng:", decision.get("trend","Chưa xác định"))
                st.write("Động lượng:", decision.get("momentum","Chưa xác định"))
                for reason in decision.get("reasons",[]): st.write("•",reason)
                analyst = run_ai_analysis(enriched, symbol)
                st.markdown("**Nhận định trợ lý offline**")
                st.write(analyst["summary"])
                st.write("Yếu tố tích cực:", analyst["bullish"] or ["Chưa có xác nhận rõ."])
                st.write("Rủi ro / phản biện:", analyst["risks"] or ["Chưa phát hiện từ bộ luật hiện tại."])
                for item in analyst.get("observations", []): st.write("•", item)
                last=enriched.iloc[-1]
                for key in ["ADX14","MFI14","CMF20","OBV","ATR14","MACD_HIST","STOCH_K","CCI20","WILLIAMS_R14"]:
                    val=last.get(key)
                    st.write(f"{key}: {'Chưa đủ dữ liệu' if pd.isna(val) else round(float(val),4)}")
                st.caption("Trợ lý này diễn giải offline theo quy tắc; không phải mô hình ngôn ngữ AI. Chỉ báo thiếu lịch sử được giữ là NaN.")

with tabs[3]:
    st.subheader("Quyết định Swing & quản trị vốn")
    data=st.session_state.market_data
    results=st.session_state.analysis
    if data is None:
        st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        capital=st.number_input("Vốn (VND)",min_value=1_000_000,value=DEFAULT_CAPITAL_VND,step=1_000_000)
        risk=st.number_input("Rủi ro mỗi lệnh (%)",min_value=0.1,max_value=5.0,value=1.0,step=0.1)
        allocation=st.number_input("Tỷ trọng tối đa mỗi mã (%)",min_value=1.0,max_value=100.0,value=20.0,step=1.0)
        lot=st.number_input("Bước lô",min_value=1,value=100,step=1)
        multiplier=st.number_input("Hệ số quy đổi giá sang VND",min_value=0.0001,value=1.0,format="%.4f")
        if st.button("Tính lại quyết định và khối lượng"):
            results=analyze_universe(data,capital_vnd=capital,risk_pct=risk,max_alloc_pct=allocation,
                                     lot_size=int(lot),price_multiplier=multiplier)
            st.session_state.analysis=results
        if results is None:
            results=analyze_universe(data); st.session_state.analysis=results
        rows=[]
        for symbol,(enriched,d) in results.items():
            rows.append({"Mã":symbol,"Đóng cửa":d.get("close"),"Tín hiệu":d.get("decision"),
                         "Vùng mua thấp":d.get("buy_zone_low"),"Vùng mua cao":d.get("buy_zone_high"),
                         "Cắt lỗ":d.get("stop_loss"),"Mục tiêu":d.get("target"),
                         "R:R":d.get("reward_risk"),"Khối lượng gợi ý":d.get("suggested_quantity")})
        st.dataframe(pd.DataFrame(rows),use_container_width=True)
        sym=st.selectbox("Mã để backtest",list(data.symbol.unique()),key="bt_symbol")
        if st.button("Chạy backtest mã đã chọn"):
            frame=data[data.symbol==sym].copy()
            bt=simple_swing_backtest(frame)
            st.json(bt)

with tabs[4]:
    st.subheader("TAB 5 – Công cụ Excel/CSV độc lập")
    st.caption("TAB này không gọi, không sửa và không phụ thuộc lõi phân tích chứng khoán.")
    file5=st.file_uploader("Tải Excel/CSV để xử lý riêng",type=["csv","txt","xlsx","xls"],key="tab5_upload")
    if file5:
        try:
            sheet5=st.text_input("Sheet TAB 5 (tên hoặc chỉ số)",value="0")
            arg=int(sheet5) if sheet5.isdigit() else sheet5
            table=tab5_excel.read_table(file5,arg)
            st.dataframe(table,use_container_width=True)
            c1,c2=st.columns(2)
            c1.download_button("Xuất CSV",tab5_excel.to_csv_bytes(table),"tab5_export.csv","text/csv")
            c2.download_button("Xuất Excel",tab5_excel.to_excel_bytes(table),"tab5_export.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"Lỗi TAB 5: {e}")
