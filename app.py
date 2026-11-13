import streamlit as st
import pandas as pd
from config import APP_NAME, DEFAULT_CAPITAL_VND, APP_VERSION
from modules.data_loader import load_market_file
from modules.market_analysis import analyze_universe
from modules.backtest import simple_swing_backtest
from modules.ai_analyzer import run_ai_analysis
from modules import tab5_excel
from modules.data_quality import assess_data_quality
from modules.market_regime import assess_market_regime
from modules.stock_scanner import scan_universe
from modules.strategy_engine import evaluate_strategies
from modules.portfolio_manager import summarize_portfolio
from modules.support_resistance import find_support_resistance
from modules.indicator_summary import summarize_indicators

st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")
st.markdown("""
<style>
/* Sticky tab navigation; content panels remain independently scrollable. */
.stTabs [data-baseweb="tab-list"] {
 position: sticky; top: 0; z-index: 1000; background: var(--background-color);
 overflow-x: auto; flex-wrap: nowrap; white-space: nowrap;
 padding: .45rem .15rem; border-bottom: 1px solid rgba(128,128,128,.25);
 scrollbar-width: thin;
}
.stTabs [data-baseweb="tab"] { flex: 0 0 auto; white-space: nowrap; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }
@media (max-width: 700px) {
 .stTabs [data-baseweb="tab"] { padding-left: .55rem; padding-right: .55rem; font-size: .82rem; }
}
</style>
""", unsafe_allow_html=True)
st.title(APP_NAME)
st.caption(f"Phiên bản V{APP_VERSION} · Công cụ nghiên cứu dữ liệu lịch sử và mô phỏng chiến lược · Không đặt lệnh · Không bảo đảm lợi nhuận")

if "market_data" not in st.session_state: st.session_state.market_data=None
if "analysis" not in st.session_state: st.session_state.analysis=None

tabs=st.tabs(["TAB 1 · Dữ liệu & Tổng quan","TAB 2 · Chỉ báo","TAB 3 · Trợ lý phân tích","TAB 4 · Scanner, Swing & Danh mục","TAB 5 · Excel/CSV độc lập","TAB 6 · Tổng hợp Trading"])

with tabs[0]:
    st.subheader("Nạp dữ liệu OHLCV")
    up=st.file_uploader("Chọn file dữ liệu",type=["csv","xlsx","xls","json","txt","parquet","pdf","docx"],key="market_upload")
    c1,c2=st.columns(2)
    hint=c1.text_input("Mã cổ phiếu nếu file chỉ có một mã",value="")
    sheet=c2.text_input("Tên sheet Excel (để trống = sheet đầu tiên)",value="")
    if up:
        try:
            data=load_market_file(up,sheet_name=sheet if sheet.strip() else 0,symbol_hint=hint or None)
            st.session_state.market_data=data; st.session_state.analysis=None
            st.success(f"Đọc thành công {len(data):,} dòng, {data.symbol.nunique()} mã.")
        except Exception as e: st.error(f"Không thể nạp dữ liệu: {e}")
    data=st.session_state.market_data
    if data is not None:
        quality=assess_data_quality(data)
        regime=assess_market_regime(data)
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Chất lượng cấu trúc",f"{quality['score']}/100")
        m2.metric("Trạng thái dữ liệu",quality["status"])
        m3.metric("Số mã",data.symbol.nunique())
        m4.metric("Trạng thái thị trường",regime["regime"])
        for issue in quality["issues"]:
            (st.warning if quality["status"]!="OK" else st.info)(issue)
        st.write("**Đánh giá thị trường:**", " ".join(regime.get("reasons",[])))
        st.caption("Nếu không có VNINDEX, trạng thái thị trường được ước lượng từ tỷ lệ mã nằm trên MA20 và MA50; độ tin cậy thấp hơn.")
        st.write(f"Khoảng dữ liệu: {data.date.min().date()} → {data.date.max().date()}")
        st.dataframe(data,use_container_width=True)
        st.download_button("Tải dữ liệu đã chuẩn hóa CSV",data.to_csv(index=False).encode("utf-8-sig"),"ohlcv_normalized.csv","text/csv")

with tabs[1]:
    st.subheader("Chỉ báo kỹ thuật")
    data=st.session_state.market_data
    if data is None: st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        results=st.session_state.analysis
        if results is None: results=analyze_universe(data); st.session_state.analysis=results
        symbols=list(results.keys()); selected=st.selectbox("Chọn mã",symbols,key="indicator_symbol")
        enriched,decision=results[selected]; latest=enriched.iloc[-1]
        cols=st.columns(5)
        for col,key in zip(cols,["SMA20","SMA50","SMA200","RSI14","ATR14"]):
            val=latest.get(key); col.metric(key,"Chưa đủ dữ liệu" if pd.isna(val) else f"{val:,.2f}")
        show=[c for c in ["date","open","high","low","close","volume","SMA20","SMA50","SMA200","EMA20","RSI14","MACD","MACD_SIGNAL","MACD_HIST","ATR14","ADX14","REL_VOLUME20","BB_UPPER","BB_LOWER"] if c in enriched]
        st.dataframe(enriched[show].tail(60),use_container_width=True)
        st.markdown("#### Biểu đồ giá và các đường trung bình")
        available_lines = [c for c in ["close", "SMA5", "SMA10", "SMA20", "SMA30", "SMA40", "SMA50", "HLC3", "VWAP20"] if c in enriched.columns]
        default_lines = [c for c in ["close", "SMA5", "SMA20", "SMA50", "VWAP20"] if c in available_lines]
        selected_lines = st.multiselect("Chọn đường hiển thị", available_lines, default=default_lines, key=f"ma_lines_{selected}")
        if selected_lines:
            chart_data = enriched.tail(180).set_index("date")[selected_lines].copy()
            chart_data = chart_data.rename(columns={"close":"Giá đóng cửa", "HLC3":"Giá bình quân HLC3", "VWAP20":"VWAP 20 phiên"})
            st.line_chart(chart_data, use_container_width=True)
        else:
            st.info("Chọn ít nhất một đường để hiển thị biểu đồ.")
        st.caption("MA dùng giá đóng cửa; HLC3 = (High + Low + Close)/3; VWAP20 là giá bình quân gia quyền khối lượng trong 20 phiên gần nhất. Các chỉ báo cần đủ lịch sử mới hiển thị; NaN không tự động thay bằng 0.")

with tabs[2]:
    st.subheader("Trợ lý phân tích và phản biện")
    data=st.session_state.market_data
    if data is None: st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        results=st.session_state.analysis
        if results is None: results=analyze_universe(data); st.session_state.analysis=results
        for symbol,(enriched,decision) in results.items():
            with st.expander(f"{symbol} · {decision.get('decision','')}",expanded=False):
                st.write("**Xu hướng:**",decision.get("trend","Chưa xác định")," · **Động lượng:**",decision.get("momentum","Chưa xác định"))
                for reason in decision.get("reasons",[]): st.write("•",reason)
                strat=evaluate_strategies(enriched)
                st.write("**Chiến lược tham chiếu:**",strat["primary"])
                for s in strat["signals"]: st.write(f"- {s['strategy']}: {s['signal']} — {s['reason']}")
                analyst=run_ai_analysis(enriched,symbol)
                st.markdown("**Diễn giải offline theo quy tắc**")
                st.write(analyst["summary"])
                st.write("Yếu tố tích cực:",analyst["bullish"] or ["Chưa có xác nhận rõ."])
                st.write("Rủi ro/phản biện:",analyst["risks"] or ["Chưa phát hiện theo bộ luật hiện tại."])
                st.write("Quan sát:",analyst.get("observations",[]))
                st.caption("Đây không phải mô hình AI tạo sinh, không dự báo chắc chắn và không phải khuyến nghị mua/bán.")

with tabs[3]:
    st.subheader("Scanner đa mã, mô phỏng Swing và quản trị danh mục")
    data=st.session_state.market_data
    if data is None: st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        results=st.session_state.analysis
        c1,c2,c3,c4=st.columns(4)
        capital=c1.number_input("Vốn mô phỏng (VND)",min_value=1_000_000,value=DEFAULT_CAPITAL_VND,step=1_000_000)
        risk=c2.number_input("Ngân sách rủi ro/mã (%)",min_value=.1,max_value=5.0,value=1.0,step=.1)
        allocation=c3.number_input("Tỷ trọng tối đa/mã (%)",min_value=1.0,max_value=100.0,value=20.0,step=1.0)
        lot=c4.number_input("Bước lô",min_value=1,value=100,step=1)
        if st.button("Tính lại phân tích toàn bộ mã"):
            results=analyze_universe(data,capital_vnd=capital,risk_pct=risk,max_alloc_pct=allocation,lot_size=int(lot))
            st.session_state.analysis=results
        if results is None: results=analyze_universe(data); st.session_state.analysis=results
        scanner=scan_universe(results,data)
        st.markdown("**Bảng xếp hạng nghiên cứu**")
        st.dataframe(scanner,use_container_width=True)
        st.download_button("Xuất bảng Scanner CSV",scanner.to_csv(index=False).encode("utf-8-sig"),"scanner_ranking.csv","text/csv")
        st.caption("Điểm tổng là thang điểm heuristic nội bộ để sắp xếp dữ liệu, không phải xác suất tăng giá hay khuyến nghị đầu tư.")
        st.markdown("**Mô phỏng chiến lược trên một mã**")
        sym=st.selectbox("Mã để mô phỏng",list(data.symbol.unique()),key="bt_symbol")
        if st.button("Chạy backtest"):
            bt=simple_swing_backtest(data[data.symbol==sym].copy())
            if "error" in bt: st.warning(bt["error"])
            else:
                k1,k2,k3,k4=st.columns(4)
                k1.metric("Tổng lợi nhuận mô phỏng",f"{bt['total_return_pct']:.2f}%")
                k2.metric("Max Drawdown",f"{bt['max_drawdown_pct']:.2f}%")
                k3.metric("Số giao dịch đóng",bt["closed_trades"])
                k4.metric("Win rate", "—" if bt["win_rate_pct"] is None else f"{bt['win_rate_pct']:.1f}%")
                k5,k6,k7,k8=st.columns(4)
                k5.metric("CAGR mô phỏng", "Chưa đủ dữ liệu" if bt.get("cagr_pct") is None else f"{bt['cagr_pct']:.2f}%")
                k6.metric("Sharpe", "Chưa đủ dữ liệu" if bt.get("sharpe") is None else f"{bt['sharpe']:.2f}")
                k7.metric("Profit Factor", "Chưa đủ dữ liệu" if bt.get("profit_factor") is None else f"{bt['profit_factor']:.2f}")
                k8.metric("Expectancy", "Chưa đủ dữ liệu" if bt.get("expectancy_pct") is None else f"{bt['expectancy_pct']:.2f}%")
                st.caption("Vị thế cuối kỳ: " + ("Còn mở, định giá theo giá đóng cửa cuối kỳ" if bt.get("open_position") else "Không còn vị thế mở"))
                st.line_chart(pd.DataFrame({"Equity mô phỏng":bt["equity_curve"]}))
                with st.expander("Chi tiết giao dịch đã đóng"):
                    if bt.get("trades"):
                        trades_df = pd.DataFrame(bt["trades"]).rename(columns={
                            "entry_date":"Ngày vào", "exit_date":"Ngày thoát",
                            "entry":"Giá vào", "exit":"Giá thoát", "return_pct":"Lợi nhuận (%)"
                        })
                        st.dataframe(trades_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Chưa có giao dịch nào được đóng trong giai đoạn mô phỏng.")
                with st.expander("Giả định và giới hạn mô phỏng"):
                    assumptions = bt.get("assumptions", {})
                    st.write(f"Phí mỗi chiều: {assumptions.get('fee_pct_each_side', '—')}%")
                    st.write(f"Trượt giá mỗi chiều: {assumptions.get('slippage_pct_each_side', '—')}%")
                    st.write(assumptions.get("execution", ""))
                    st.warning(bt.get("note", "Mô phỏng chỉ mang tính tham khảo."))
        st.markdown("**Theo dõi danh mục (nhập CSV)**")
        st.caption("Cột bắt buộc: symbol, quantity, entry_price. Cột tùy chọn: market_price, stop_price. Không kết nối tài khoản hay gửi lệnh.")
        pf=st.file_uploader("Tải CSV vị thế mô phỏng",type=["csv"],key="portfolio_upload")
        if pf:
            try:
                positions=pd.read_csv(pf)
                st.session_state["portfolio_positions_df"] = positions.copy()
                summary=summarize_portfolio(positions,capital)
                p1,p2,p3=st.columns(3); p1.metric("Giá trị thị trường",f"{summary['market_value']:,.0f} VND")
                p2.metric("Lãi/lỗ chưa thực hiện",f"{summary['unrealized_pnl']:,.0f} VND")
                p3.metric("Tỷ trọng vốn",f"{summary['exposure_pct']:.1f}%")
                st.write(f"Rủi ro tới stop tham chiếu: {summary['total_risk']:,.0f} VND ({summary['risk_pct_of_capital']:.2f}% vốn)")
                st.dataframe(summary["positions"],use_container_width=True)
            except Exception as e: st.error(f"Không đọc được danh mục: {e}")

with tabs[4]:
    import hashlib

    st.subheader("Công cụ Excel/CSV độc lập")
    st.caption(
        "Tab 5 có kho dữ liệu riêng. Dữ liệu tại đây không được chuyển sang "
        "Tab 1, không thay đổi market_data và không tác động đến phân tích."
    )

    # Tách biệt hoàn toàn trạng thái của Tab 5 khỏi market_data/analysis.
    if "tab5_table" not in st.session_state:
        st.session_state.tab5_table = None
    if "tab5_revision" not in st.session_state:
        st.session_state.tab5_revision = 0
    if "tab5_source_hash" not in st.session_state:
        st.session_state.tab5_source_hash = None

    st.markdown("### 1. Dán dữ liệu trực tiếp như Excel")
    pasted5 = st.text_area(
        "Dán dữ liệu từ Excel, website hoặc văn bản vào đây",
        height=190,
        placeholder=(
            "Date\tOpen\tHigh\tLow\tClose\tVolume\n"
            "2026-11-09\t25000\t25500\t24800\t25300\t1200000\n"
            "2026-11-10\t25300\t25800\t25100\t25700\t1500000"
        ),
        key="tab5_paste_text",
    )
    pc1, pc2, pc3 = st.columns([1, 1, 1])
    delimiter5 = pc1.selectbox(
        "Dấu phân cách",
        ["Tự nhận diện", "Tab", "Dấu phẩy (,)", "Chấm phẩy (;)", "Gạch đứng (|)"],
        key="tab5_delimiter",
    )
    header5 = pc2.checkbox("Dòng đầu là tiêu đề cột", value=True, key="tab5_has_header")
    if pc3.button("TÁCH DỮ LIỆU THÀNH BẢNG", key="tab5_parse_paste", type="primary"):
        try:
            sep_map = {
                "Tự nhận diện": "Tự nhận diện",
                "Tab": "\t",
                "Dấu phẩy (,)": ",",
                "Chấm phẩy (;)": ";",
                "Gạch đứng (|)": "|",
            }
            pasted_df = tab5_excel.parse_pasted_text(
                pasted5, delimiter=sep_map[delimiter5], header=header5
            )
            pasted_df, _ = tab5_excel.normalize_columns(pasted_df)
            st.session_state.tab5_table = pasted_df
            st.session_state.tab5_revision += 1
            st.success(
                f"Đã tách thành {len(pasted_df):,} dòng và "
                f"{len(pasted_df.columns)} cột."
            )
        except Exception as e:
            st.error(f"Không tách được dữ liệu: {e}")

    st.divider()
    st.markdown("### 2. Nhập file Excel / CSV / TXT")
    file5 = st.file_uploader(
        "Chọn file chỉ dùng riêng trong Tab 5",
        type=["csv", "txt", "xlsx", "xls"],
        key="tab5_upload",
    )
    sheet5 = st.text_input(
        "Sheet Excel (tên hoặc chỉ số; mặc định 0)",
        value="0",
        key="tab5_sheet_name",
    )
    if file5 is not None:
        try:
            raw5 = file5.getvalue()
            digest5 = hashlib.sha256(file5.name.encode("utf-8") + raw5).hexdigest()
            if digest5 != st.session_state.tab5_source_hash:
                sheet_arg5 = int(sheet5) if sheet5.strip().isdigit() else sheet5
                uploaded_df5 = tab5_excel.read_table(file5, sheet_arg5)
                uploaded_df5, _ = tab5_excel.normalize_columns(uploaded_df5)
                st.session_state.tab5_table = uploaded_df5
                st.session_state.tab5_revision += 1
                st.session_state.tab5_source_hash = digest5
                st.success(
                    f"Đã đọc {len(uploaded_df5):,} dòng từ {file5.name}."
                )
        except Exception as e:
            st.error(f"Không đọc được file Tab 5: {e}")

    st.divider()
    st.markdown("### 3. Bảng dữ liệu có thể chỉnh sửa")
    table5 = st.session_state.tab5_table
    if table5 is None:
        st.info("Dán dữ liệu hoặc tải file lên để tạo bảng.")
    else:
        st.caption(
            f"{len(table5):,} dòng · {len(table5.columns)} cột · "
            "Có thể sửa trực tiếp từng ô, thêm dòng hoặc xóa dòng trong bảng."
        )
        edited5 = st.data_editor(
            table5,
            key=f"tab5_editor_{st.session_state.tab5_revision}",
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
        )
        st.session_state.tab5_table = edited5
        table5 = edited5

        # Kiểm tra OHLCV chỉ để cảnh báo trong bảng độc lập; không chuyển dữ liệu sang Tab 1.
        ohlcv_required5 = {"date", "open", "high", "low", "close", "volume"}
        if ohlcv_required5.issubset(set(table5.columns)):
            issues5 = tab5_excel.validate_table(table5)
            if issues5:
                for issue5 in issues5:
                    st.warning(issue5)
            else:
                st.success("Kiểm tra OHLCV cơ bản: chưa phát hiện lỗi.")
        else:
            st.info("Bảng được xử lý ở chế độ dữ liệu tổng quát; không ép thành OHLCV.")

        st.divider()
        st.markdown("### 4. Lưu thành file mới")
        sc1, sc2 = st.columns([2, 1])
        filename5 = sc1.text_input(
            "Tên file (không cần phần mở rộng)",
            value="du_lieu_tab5",
            key="tab5_new_filename",
        )
        format5 = sc2.selectbox(
            "Định dạng lưu", ["xlsx", "csv"], key="tab5_new_format"
        )
        if st.button("LƯU FILE MỚI", key="tab5_save_new", type="primary"):
            try:
                saved5 = tab5_excel.save_new_file(table5, filename5, format5)
                st.success(f"Đã lưu file mới: {saved5.name}")
            except Exception as e:
                st.error(f"Không lưu được file: {e}")

        st.divider()
        st.markdown("### 5. Cập nhật file cũ")
        saved_files5 = tab5_excel.list_saved_files()
        if not saved_files5:
            st.info("Chưa có file trong kho Tab 5. Hãy lưu file mới trước.")
        else:
            old_file5 = st.selectbox(
                "Chọn file cần cập nhật", saved_files5, key="tab5_old_file"
            )
            key_options5 = [c for c in ["symbol", "date"] if c in table5.columns]
            if not key_options5:
                key_options5 = list(table5.columns)
            if "symbol" in key_options5 and "date" in key_options5:
                default_keys5 = ["symbol", "date"]
            elif "date" in key_options5:
                default_keys5 = ["date"]
            else:
                default_keys5 = key_options5[:1]
            selected_keys5 = st.multiselect(
                "Chọn cột khóa để nhận diện dòng trùng",
                options=key_options5,
                default=default_keys5,
                key="tab5_merge_keys",
            )
            st.caption(
                "Dữ liệu mới trùng khóa sẽ thay thế bản ghi cũ. "
                "File cũ được sao lưu trước khi cập nhật. Với OHLCV nên dùng symbol + date."
            )
            confirm5 = st.checkbox(
                "Tôi đã kiểm tra và đồng ý cập nhật file đã chọn.",
                key="tab5_confirm_update",
            )
            if st.button(
                "ĐỐI CHIẾU VÀ CẬP NHẬT FILE CŨ",
                key="tab5_update_old",
                disabled=not confirm5,
            ):
                try:
                    old_df5 = tab5_excel.load_saved_file(old_file5)
                    missing_keys5 = [
                        k for k in selected_keys5
                        if k not in old_df5.columns or k not in table5.columns
                    ]
                    if not selected_keys5:
                        st.error("Bạn cần chọn ít nhất một cột khóa.")
                    elif missing_keys5:
                        st.error("File cũ hoặc dữ liệu mới thiếu cột khóa: " + ", ".join(missing_keys5))
                    else:
                        merged5, duplicate5, backup5 = tab5_excel.update_saved_file(
                            table5, old_file5, keys=selected_keys5
                        )
                        st.success(
                            f"Cập nhật thành công: {len(merged5):,} dòng. "
                            f"Số dòng cũ bị thay thế do trùng khóa: {duplicate5}."
                        )
                        st.info(f"Bản sao lưu: {backup5.name}")
                        st.dataframe(merged5.tail(100), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Không cập nhật được file: {e}")

        st.divider()
        st.markdown("### 6. Xuất bảng hiện tại")
        ec1, ec2 = st.columns(2)
        ec1.download_button(
            "TẢI CSV",
            data=tab5_excel.to_csv_bytes(table5),
            file_name="tab5_du_lieu.csv",
            mime="text/csv",
            key="tab5_download_csv",
        )
        ec2.download_button(
            "TẢI EXCEL",
            data=tab5_excel.to_excel_bytes(table5),
            file_name="tab5_du_lieu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="tab5_download_xlsx",
        )

    st.divider()
    st.markdown("### 7. Kho file riêng của Tab 5")
    try:
        saved_listing5 = tab5_excel.list_saved_files()
        if saved_listing5:
            st.dataframe(
                pd.DataFrame({"File đã lưu": saved_listing5}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Kho Tab 5 chưa có file.")
    except Exception as e:
        st.error(f"Không đọc được kho Tab 5: {e}")


# =========================================================
# TAB 6 · TRUNG TÂM TỔNG HỢP PHÂN TÍCH VÀ HỖ TRỢ QUYẾT ĐỊNH
# =========================================================
with tabs[5]:
    st.subheader("Trung tâm tổng hợp phân tích Trading")
    st.caption("Tổng hợp tín hiệu, vùng giá và quản trị vị thế. Đây là công cụ nghiên cứu, không đặt lệnh và không bảo đảm lợi nhuận.")
    data = st.session_state.market_data
    if data is None:
        st.info("Hãy nạp dữ liệu OHLCV tại TAB 1 trước.")
    else:
        results = st.session_state.analysis
        if results is None:
            results = analyze_universe(data)
            st.session_state.analysis = results
        symbols = list(results.keys())
        selected_summary = st.selectbox("Chọn mã cần tổng hợp", symbols, key="summary_symbol")
        enriched_summary, decision_summary = results[selected_summary]
        sr_summary = find_support_resistance(enriched_summary)
        report = summarize_indicators(enriched_summary, decision_summary, sr_summary)

        # Các tiện ích định dạng chỉ dùng trong Tab 6.
        def _price_text(value):
            try:
                return "Chưa có dữ liệu" if value is None or pd.isna(value) else f"{float(value):,.0f}"
            except (TypeError, ValueError):
                return "Chưa có dữ liệu"

        def _pct_text(value):
            try:
                return "Chưa có dữ liệu" if value is None or pd.isna(value) else f"{float(value):+.2f}%"
            except (TypeError, ValueError):
                return "Chưa có dữ liệu"

        if report.get("status") != "OK":
            st.warning("Chưa đủ dữ liệu hợp lệ để tổng hợp mã này.")
            for reason in report.get("reasons", []):
                st.write("•", reason)
        else:
            p = report.get("plan", {})
            sr = report.get("support_resistance", {})
            close_price = float(report["close"])

            st.markdown("### 1. Tổng quan tín hiệu")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Điểm tổng hợp", "Chưa đủ" if report.get("score") is None else f"{report['score']:.1f}/100")
            m2.metric("Kết luận kỹ thuật", report.get("label", "Chưa xác định"))
            m3.metric("Độ phủ chỉ báo", f"{report.get('coverage_pct', 0):.0f}%")
            m4.metric("Xu hướng", decision_summary.get("trend", "Chưa rõ"))
            m5.metric("Động lượng", decision_summary.get("momentum", "Chưa rõ"))

            regime_summary = assess_market_regime(data)
            st.caption(f"Bối cảnh thị trường chung: {regime_summary.get('regime', 'Chưa xác định')} · " + " ".join(regime_summary.get("reasons", [])))

            st.markdown("### 2. Đánh giá theo nhóm chỉ báo")
            if report.get("groups"):
                group_table = pd.DataFrame(report["groups"])[["name", "signal", "score", "available", "detail"]]
                group_table = group_table.rename(columns={"name":"Nhóm chỉ báo", "signal":"Tín hiệu", "score":"Điểm", "available":"Đủ dữ liệu", "detail":"Căn cứ"})
                st.dataframe(group_table, use_container_width=True, hide_index=True)
            left, right = st.columns(2)
            with left:
                st.markdown("**Các dữ kiện ủng hộ kết luận**")
                for reason in report.get("reasons", []):
                    st.write("•", reason)
            with right:
                st.markdown("**Tín hiệu mâu thuẫn cần lưu ý**")
                if report.get("conflicts"):
                    for conflict in report["conflicts"]:
                        st.warning(conflict)
                else:
                    st.success("Chưa phát hiện mâu thuẫn lớn trong các nhóm chỉ báo đang đủ dữ liệu.")

            st.markdown("### 3. Bản đồ vùng giá")
            pc = st.columns(4)
            pc[0].metric("Giá đóng cửa", _price_text(close_price))
            pc[1].metric("Hỗ trợ gần", _price_text(sr.get("support")))
            pc[2].metric("Kháng cự gần", _price_text(sr.get("resistance")))
            pc[3].metric("Giá xác nhận", _price_text(p.get("confirmation_price")))
            st.caption(p.get("confirmation_note", ""))
            if sr.get("distance_to_support_pct") is not None and sr.get("distance_to_resistance_pct") is not None:
                st.write(f"Khoảng cách tới hỗ trợ: **{sr['distance_to_support_pct']:.2f}%** · Khoảng cách tới kháng cự: **{sr['distance_to_resistance_pct']:.2f}%**")
                st.caption(f"Số lần phản ứng pivot tham chiếu — hỗ trợ: {sr.get('support_touches', 0)} · kháng cự: {sr.get('resistance_touches', 0)}. {sr.get('method', '')}")

            st.markdown("### 4. Kế hoạch giá tham chiếu")
            plan_rows = [
                {"Mốc giá":"Vùng mua thấp", "Giá":p.get("buy_zone_low")},
                {"Mốc giá":"Vùng mua cao", "Giá":p.get("buy_zone_high")},
                {"Mốc giá":"Giá xác nhận", "Giá":p.get("confirmation_price")},
                {"Mốc giá":"Chốt lời mục tiêu 1 (TP1)", "Giá":p.get("target_1")},
                {"Mốc giá":"Chốt lời mục tiêu 2 (TP2)", "Giá":p.get("target_2")},
                {"Mốc giá":"Cắt lỗ tham chiếu (SL)", "Giá":p.get("stop_loss")},
            ]
            plan_table = pd.DataFrame(plan_rows)
            plan_table["Giá"] = plan_table["Giá"].map(_price_text)
            st.dataframe(plan_table, use_container_width=True, hide_index=True)
            st.write("**Tỷ lệ R:R tham chiếu:**", "Chưa xác định" if p.get("reward_risk") is None else f"{float(p['reward_risk']):.2f}")
            st.caption(p.get("note", ""))

            st.markdown("### 5. Kịch bản theo trạng thái tài khoản")
            holding_state = st.radio(
                "Hiện tại bạn đang ở trạng thái nào với mã này?",
                ["Chưa có hàng", "Đang có hàng"],
                horizontal=True,
                key=f"summary_holding_state_{selected_summary}",
            )

            if holding_state == "Chưa có hàng":
                st.markdown("#### Kịch bản tìm điểm mua")
                buy_low = p.get("buy_zone_low")
                buy_high = p.get("buy_zone_high")
                confirm_price = p.get("confirmation_price")
                if buy_low is not None and buy_high is not None and buy_low <= close_price <= buy_high:
                    entry_status = "Giá hiện tại đang nằm trong vùng mua tham chiếu; vẫn cần chờ xác nhận tín hiệu và thanh khoản."
                    st.info(entry_status)
                elif buy_high is not None and close_price < buy_high:
                    st.info("Giá hiện tại chưa vào vùng mua tham chiếu. Có thể tiếp tục theo dõi, không cần mua đuổi.")
                elif confirm_price is not None and close_price >= confirm_price:
                    st.warning("Giá đã ở trên mốc xác nhận tham chiếu. Cần kiểm tra đóng cửa, khối lượng và rủi ro vượt vùng giá trước khi cân nhắc.")
                else:
                    st.warning("Chưa có điểm vào lệnh đủ điều kiện theo các mốc giá hiện có. Tiếp tục chờ xác nhận.")
                b1, b2, b3 = st.columns(3)
                b1.metric("Vùng mua", f"{_price_text(buy_low)} – {_price_text(buy_high)}" if buy_low is not None and buy_high is not None else "Chưa có dữ liệu")
                b2.metric("Giá xác nhận", _price_text(confirm_price))
                b3.metric("Giá hiện tại", _price_text(close_price))
                st.caption("Không mở vị thế chỉ vì giá chạm vùng mua. Ưu tiên xác nhận bằng giá đóng cửa, thanh khoản và tín hiệu không mâu thuẫn.")

            else:
                st.markdown("#### Kịch bản quản lý vị thế đang nắm giữ")
                saved_positions = st.session_state.get("portfolio_positions_df")
                default_qty, default_cost = 0.0, close_price
                if isinstance(saved_positions, pd.DataFrame) and not saved_positions.empty and "symbol" in saved_positions.columns:
                    matched = saved_positions[saved_positions["symbol"].astype(str).str.upper() == str(selected_summary).upper()]
                    if not matched.empty:
                        row_pos = matched.iloc[0]
                        try: default_qty = float(row_pos.get("quantity", 0))
                        except (TypeError, ValueError): default_qty = 0.0
                        try: default_cost = float(row_pos.get("entry_price", close_price))
                        except (TypeError, ValueError): default_cost = close_price
                        st.caption("Đã tìm thấy mã này trong CSV danh mục đã nạp ở Tab 4. Bạn có thể điều chỉnh số lượng và giá vốn bên dưới.")
                h1, h2 = st.columns(2)
                quantity = h1.number_input("Số lượng đang nắm giữ (cổ phiếu)", min_value=0.0, value=max(0.0, default_qty), step=100.0, key=f"holding_qty_{selected_summary}")
                entry_price = h2.number_input("Giá vốn bình quân", min_value=0.0, value=max(0.0, default_cost), step=100.0, key=f"holding_cost_{selected_summary}")
                if quantity > 0 and entry_price > 0:
                    market_value = quantity * close_price
                    cost_value = quantity * entry_price
                    pnl_value = market_value - cost_value
                    pnl_pct = (close_price / entry_price - 1) * 100
                    hcols = st.columns(4)
                    hcols[0].metric("Giá trị hiện tại", f"{market_value:,.0f}")
                    hcols[1].metric("Giá vốn", f"{cost_value:,.0f}")
                    hcols[2].metric("Lãi/lỗ tạm tính", f"{pnl_value:+,.0f}", delta=f"{pnl_pct:+.2f}%")
                    hcols[3].metric("Số lượng", f"{quantity:,.0f}")
                    stop_price, tp1, tp2 = p.get("stop_loss"), p.get("target_1"), p.get("target_2")
                    if stop_price is not None and close_price <= float(stop_price):
                        st.error("Giá đóng cửa đã chạm hoặc thấp hơn mức SL tham chiếu. Cần rà soát lại luận điểm và mức rủi ro của vị thế.")
                    elif tp1 is not None and close_price >= float(tp1):
                        st.success("Giá đã đạt/vượt TP1 tham chiếu. Có thể đánh giá phương án bảo vệ thành quả và cập nhật điểm dừng theo kế hoạch.")
                    else:
                        st.info("Giá chưa chạm các mốc TP/SL tham chiếu. Tiếp tục theo dõi xu hướng, hỗ trợ và điều kiện vô hiệu kịch bản.")
                    st.write(f"**TP1:** {_price_text(tp1)} · **TP2:** {_price_text(tp2)} · **SL tham chiếu:** {_price_text(stop_price)}")
                else:
                    st.info("Nhập số lượng và giá vốn lớn hơn 0 để tính lãi/lỗ và đánh giá vị thế.")

            st.markdown("### 6. Kết luận và điều kiện theo dõi")
            st.info(f"**Kết luận từ bộ máy quyết định:** {report.get('decision_engine', 'Chưa có')}\n\n**Kết luận tổng hợp:** {report.get('label', 'Chưa xác định')}.")
            st.write("**Điều kiện xác nhận:** theo dõi giá đóng cửa, khối lượng và động lượng; không xác nhận chỉ bằng việc giá chạm một mốc trong phiên.")
            st.write("**Điều kiện vô hiệu:** đánh giá lại kịch bản nếu giá xuyên thủng vùng hỗ trợ hoặc chạm ngưỡng SL tham chiếu.")
            st.caption(report.get("disclaimer", ""))
