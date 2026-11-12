import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

from config import APP_NAME, DEFAULT_CAPITAL_VND
from modules.data_loader import load_market_file
from modules.market_analysis import analyze_universe
from modules.backtest import simple_swing_backtest
from modules.ai_analyzer import run_ai_analysis
from modules.support_resistance import find_support_resistance
from modules import tab5_excel


# =========================================================
# CẤU HÌNH GIAO DIỆN
# =========================================================
st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.15rem; padding-bottom: 2rem; max-width: 1500px;}
    [data-testid="stMetric"] {background: rgba(128,128,128,.07); padding: .65rem .8rem; border-radius: 10px;}
    div[data-testid="stTabs"] button {font-weight: 600; padding-left: .55rem; padding-right: .55rem;}
    div[data-testid="stExpander"] {border-radius: 10px;}
    @media (max-width: 700px) {
        .block-container {padding-left: .75rem; padding-right: .75rem;}
        h1 {font-size: 1.55rem !important;}
        h2 {font-size: 1.25rem !important;}
        h3 {font-size: 1.08rem !important;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_NAME)
st.caption(
    "Phân tích offline từ dữ liệu người dùng tải lên • Không có dữ liệu mẫu • "
    "Không tự đặt lệnh"
)

# Giữ nguyên các khóa session_state hiện có.
if "market_data" not in st.session_state:
    st.session_state.market_data = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None

tabs = st.tabs([
    "TAB 1 · Dữ liệu & Tổng quan",
    "TAB 2 · Chỉ báo",
    "TAB 3 · Trợ lý phân tích",
    "TAB 4 · Swing & Backtest",
    "TAB 5 · Excel/CSV độc lập",
])


# =========================================================
# HÀM HIỂN THỊ BỔ SUNG - KHÔNG THAY ĐỔI MODULE PHÂN TÍCH
# =========================================================
def _fmt_price(value):
    """Định dạng giá; giá trị thiếu được hiển thị rõ, không tự điền."""
    try:
        if value is None or pd.isna(value):
            return "Chưa có dữ liệu"
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "Chưa có dữ liệu"


def _fmt_number(value, digits=2):
    try:
        if value is None or pd.isna(value):
            return "Chưa đủ dữ liệu"
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "Chưa đủ dữ liệu"


def _candlestick_chart(enriched, decision, symbol, history=120):
    """
    Vẽ nến trực tiếp bằng matplotlib để không phát sinh thư viện biểu đồ mới.
    Tất cả đường giá lấy từ dữ liệu OHLCV hoặc kết quả module hiện có.
    """
    if enriched is None or enriched.empty:
        st.info("Không có dữ liệu để vẽ biểu đồ.")
        return

    x = enriched.tail(history).copy() if history else enriched.copy()
    x = x.reset_index(drop=True)
    required = ["date", "open", "high", "low", "close", "volume"]
    if any(col not in x.columns for col in required):
        st.warning("Dữ liệu thiếu cột cần thiết để vẽ biểu đồ nến.")
        return

    x["date"] = pd.to_datetime(x["date"])
    dates = mdates.date2num(x["date"].tolist())
    width = 0.62

    fig, axes = plt.subplots(
        5, 1, figsize=(13, 12),
        gridspec_kw={"height_ratios": [3.2, 1.0, 1.0, 1.15, 1.0]},
        sharex=True
    )
    ax_price, ax_volume, ax_rsi, ax_macd, ax_flow = axes

    # Nến OHLC
    for i, row in x.iterrows():
        o, h, low, c = [float(row[k]) for k in ("open", "high", "low", "close")]
        rising = c >= o
        candle_color = "#16a085" if rising else "#e74c3c"
        ax_price.vlines(dates[i], low, h, color=candle_color, linewidth=1.0)
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height == 0:
            body_height = max(abs(c) * 0.0005, 0.0001)
        ax_price.add_patch(
            Rectangle(
                (dates[i] - width / 2, body_bottom),
                width, body_height,
                facecolor=candle_color, edgecolor=candle_color, linewidth=0.7
            )
        )

    # MA
    for key, label, color in [
        ("SMA20", "MA20", "#f39c12"),
        ("SMA50", "MA50", "#3498db"),
        ("SMA200", "MA200", "#8e44ad"),
    ]:
        if key in x.columns:
            ax_price.plot(dates, x[key], label=label, linewidth=1.25, color=color)

    # Các mức từ decision_engine; không tự suy diễn mức còn thiếu.
    level_specs = [
        ("buy_zone_low", "Vùng mua thấp", "#16a085", "--"),
        ("buy_zone_high", "Vùng mua cao", "#16a085", "--"),
        ("stop_loss", "Cắt lỗ", "#e74c3c", "--"),
        ("target", "Mục tiêu module", "#2980b9", "--"),
    ]
    for key, label, color, style in level_specs:
        value = decision.get(key) if isinstance(decision, dict) else None
        if value is not None and pd.notna(value):
            ax_price.axhline(float(value), color=color, linestyle=style, linewidth=1.0, label=label)

    # Hỗ trợ/kháng cự từ module hiện hữu.
    sr = find_support_resistance(enriched)
    if sr.get("support") is not None:
        ax_price.axhline(sr["support"], color="#2ecc71", linestyle=":", linewidth=1.2,
                         label="Hỗ trợ (20 phiên)")
    if sr.get("resistance") is not None:
        ax_price.axhline(sr["resistance"], color="#c0392b", linestyle=":", linewidth=1.2,
                         label="Kháng cự (20 phiên)")

    ax_price.set_title(f"{symbol} · Biểu đồ nến và vùng giá", loc="left", fontsize=12, fontweight="bold")
    ax_price.set_ylabel("Giá")
    ax_price.grid(alpha=0.2)
    ax_price.legend(loc="upper left", ncol=3, fontsize=8)

    # Volume và trung bình khối lượng nếu module có cột.
    vol_colors = ["#16a085" if c >= o else "#e74c3c"
                  for o, c in zip(x["open"], x["close"])]
    ax_volume.bar(dates, x["volume"], width=width, color=vol_colors, alpha=0.75, label="Volume")
    if "VOL_MA20" in x.columns:
        ax_volume.plot(dates, x["VOL_MA20"], color="#f39c12", linewidth=1.1, label="Volume MA20")
    ax_volume.set_ylabel("Volume")
    ax_volume.grid(alpha=0.2)
    ax_volume.legend(loc="upper left", fontsize=8)

    # RSI
    if "RSI14" in x.columns:
        ax_rsi.plot(dates, x["RSI14"], color="#8e44ad", linewidth=1.2, label="RSI14")
        ax_rsi.axhline(70, color="#e74c3c", linestyle="--", linewidth=0.8)
        ax_rsi.axhline(50, color="gray", linestyle=":", linewidth=0.8)
        ax_rsi.axhline(30, color="#16a085", linestyle="--", linewidth=0.8)
        ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.grid(alpha=0.2)
    ax_rsi.legend(loc="upper left", fontsize=8)

    # MACD
    if "MACD" in x.columns:
        ax_macd.plot(dates, x["MACD"], label="MACD", color="#2980b9", linewidth=1.1)
    if "MACD_SIGNAL" in x.columns:
        ax_macd.plot(dates, x["MACD_SIGNAL"], label="Signal", color="#e67e22", linewidth=1.1)
    if "MACD_HIST" in x.columns:
        hist_colors = ["#16a085" if v >= 0 else "#e74c3c" for v in x["MACD_HIST"].fillna(0)]
        ax_macd.bar(dates, x["MACD_HIST"].fillna(0), width=width, color=hist_colors, alpha=0.45,
                    label="Histogram")
    ax_macd.axhline(0, color="gray", linewidth=0.7)
    ax_macd.set_ylabel("MACD")
    ax_macd.grid(alpha=0.2)
    ax_macd.legend(loc="upper left", fontsize=8)

    # Dòng tiền: CMF20 có sẵn trong indicators.py.
    if "CMF20" in x.columns:
        ax_flow.plot(dates, x["CMF20"], color="#16a085", linewidth=1.2, label="CMF20")
    ax_flow.axhline(0, color="gray", linewidth=0.8, linestyle=":")
    ax_flow.set_ylabel("CMF20")
    ax_flow.grid(alpha=0.2)
    ax_flow.legend(loc="upper left", fontsize=8)
    if "MFI14" in x.columns:
        ax_flow_mfi = ax_flow.twinx()
        ax_flow_mfi.plot(dates, x["MFI14"], color="#d35400", linewidth=1.0,
                         alpha=0.85, label="MFI14")
        ax_flow_mfi.set_ylabel("MFI14")
        ax_flow_mfi.set_ylim(0, 100)
        ax_flow_mfi.legend(loc="upper right", fontsize=8)

    ax_flow.xaxis_date()
    ax_flow.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax_flow.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax_flow.xaxis.get_major_locator()))
    for ax in axes:
        ax.margins(x=0.01)

    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def _show_level_summary(decision, enriched):
    sr = find_support_resistance(enriched)
    cols = st.columns(4)
    cols[0].metric("Hỗ trợ 20 phiên", _fmt_price(sr.get("support")))
    cols[1].metric("Kháng cự 20 phiên", _fmt_price(sr.get("resistance")))
    cols[2].metric("Cắt lỗ", _fmt_price(decision.get("stop_loss")))
    cols[3].metric("Mục tiêu hiện có", _fmt_price(decision.get("target")))

    st.caption(
        "Giá xác nhận mua và mục tiêu chốt lời 2 chưa được decision_engine.py cung cấp. "
        "Ứng dụng không tự tạo hai mức giá này."
    )


# =========================================================
# TAB 1 · DỮ LIỆU & TỔNG QUAN
# =========================================================
with tabs[0]:
    st.subheader("Nạp dữ liệu thị trường")
    up = st.file_uploader(
        "Chọn file OHLCV",
        type=["csv", "xlsx", "xls", "json", "txt", "parquet", "pdf", "docx"],
        key="market_upload"
    )
    hint = st.text_input(
        "Mã cổ phiếu nếu file chỉ có một mã (không bắt buộc)", value=""
    )
    sheet = st.text_input(
        "Tên sheet Excel (để trống = sheet đầu tiên)", value=""
    )

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
        cols = st.columns(3)
        cols[0].metric("Số dòng OHLCV", f"{len(data):,}")
        cols[1].metric("Số mã", f"{data['symbol'].nunique():,}")
        cols[2].metric("Số phiên", f"{data['date'].nunique():,}")
        st.write(
            "Khoảng ngày:",
            data.date.min().date(),
            "→",
            data.date.max().date()
        )
        st.dataframe(data, use_container_width=True, height=360)
        st.download_button(
            "Tải dữ liệu đã chuẩn hóa CSV",
            data.to_csv(index=False).encode("utf-8-sig"),
            "ohlcv_normalized.csv",
            "text/csv"
        )
    else:
        st.info("Tải file OHLCV lên để bắt đầu phân tích. Ứng dụng không tự nạp dữ liệu mẫu.")


# =========================================================
# TAB 2 · CHỈ BÁO & BIỂU ĐỒ
# =========================================================
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

        history_label = st.selectbox(
            "Số phiên hiển thị trên biểu đồ",
            ["60 phiên", "120 phiên", "200 phiên", "Toàn bộ"],
            index=1,
            key="chart_history"
        )
        history = None if history_label == "Toàn bộ" else int(history_label.split()[0])

        latest = enriched.iloc[-1]
        cols = st.columns(5)
        for col, key in zip(cols, ["SMA20", "SMA50", "SMA200", "RSI14", "close"]):
            val = latest.get(key)
            col.metric(key.upper() if key == "close" else key, _fmt_price(val))

        st.markdown("#### Biểu đồ kỹ thuật tổng hợp")
        _candlestick_chart(enriched, decision, selected, history=history)

        st.markdown("#### Hỗ trợ, kháng cự và các mức giao dịch")
        _show_level_summary(decision, enriched)

        with st.expander("Xem bảng chỉ báo chi tiết · 30 phiên gần nhất"):
            st.dataframe(enriched.tail(30), use_container_width=True, height=340)


# =========================================================
# TAB 3 · TRỢ LÝ PHÂN TÍCH
# =========================================================
with tabs[2]:
    st.subheader("Trợ lý phân tích chuyên sâu")
    data = st.session_state.market_data
    results = st.session_state.analysis
    if data is None:
        st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        if results is None:
            results = analyze_universe(data)
            st.session_state.analysis = results

        for symbol, (enriched, decision) in results.items():
            with st.expander(f"{symbol} · {decision.get('decision', '')}", expanded=False):
                c1, c2, c3 = st.columns(3)
                c1.metric("Giá đóng cửa", _fmt_price(decision.get("close")))
                c2.metric("Xu hướng", decision.get("trend", "Chưa xác định"))
                c3.metric("Động lượng", decision.get("momentum", "Chưa xác định"))

                st.markdown("**Lý do từ bộ máy quyết định**")
                for reason in decision.get("reasons", []):
                    st.write("•", reason)

                analyst = run_ai_analysis(enriched, symbol)
                st.markdown("**Nhận định trợ lý offline**")
                st.write(analyst["summary"])

                left, right = st.columns(2)
                with left:
                    st.markdown("**Yếu tố tích cực**")
                    for item in analyst["bullish"] or ["Chưa có xác nhận rõ."]:
                        st.write("•", item)
                with right:
                    st.markdown("**Rủi ro / phản biện**")
                    for item in analyst["risks"] or ["Chưa phát hiện từ bộ luật hiện tại."]:
                        st.write("•", item)

                with st.expander("Quan sát và chỉ báo chi tiết"):
                    for item in analyst.get("observations", []):
                        st.write("•", item)
                    last = enriched.iloc[-1]
                    for key in [
                        "ADX14", "MFI14", "CMF20", "OBV", "ATR14",
                        "MACD_HIST", "STOCH_K", "CCI20", "WILLIAMS_R14"
                    ]:
                        val = last.get(key)
                        st.write(f"{key}: {_fmt_number(val, 4)}")

                st.caption(
                    "Trợ lý này diễn giải offline theo quy tắc; không phải mô hình ngôn ngữ AI. "
                    "Chỉ báo thiếu lịch sử được giữ là NaN."
                )


# =========================================================
# TAB 4 · SWING, QUẢN TRỊ VỊ THẾ & BACKTEST
# =========================================================
with tabs[3]:
    st.subheader("Quyết định Swing & quản trị vốn")
    data = st.session_state.market_data
    results = st.session_state.analysis

    if data is None:
        st.info("Hãy nạp dữ liệu ở TAB 1.")
    else:
        with st.expander("Thiết lập vốn và rủi ro", expanded=True):
            c1, c2, c3 = st.columns(3)
            capital = c1.number_input(
                "Vốn (VND)", min_value=1_000_000,
                value=DEFAULT_CAPITAL_VND, step=1_000_000, key="swing_capital"
            )
            risk = c2.number_input(
                "Rủi ro mỗi lệnh (%)", min_value=0.1, max_value=5.0,
                value=1.0, step=0.1, key="swing_risk"
            )
            allocation = c3.number_input(
                "Tỷ trọng tối đa mỗi mã (%)", min_value=1.0, max_value=100.0,
                value=20.0, step=1.0, key="swing_allocation"
            )
            c4, c5 = st.columns(2)
            lot = c4.number_input("Bước lô", min_value=1, value=100, step=1, key="swing_lot")
            multiplier = c5.number_input(
                "Hệ số quy đổi giá sang VND", min_value=0.0001,
                value=1.0, format="%.4f", key="swing_multiplier"
            )

            if st.button("Tính lại quyết định và khối lượng", key="recalculate_swing"):
                results = analyze_universe(
                    data,
                    capital_vnd=capital,
                    risk_pct=risk,
                    max_alloc_pct=allocation,
                    lot_size=int(lot),
                    price_multiplier=multiplier
                )
                st.session_state.analysis = results

        if results is None:
            results = analyze_universe(data)
            st.session_state.analysis = results

        rows = []
        for symbol, (enriched, d) in results.items():
            rows.append({
                "Mã": symbol,
                "Đóng cửa": d.get("close"),
                "Tín hiệu": d.get("decision"),
                "Vùng mua thấp": d.get("buy_zone_low"),
                "Vùng mua cao": d.get("buy_zone_high"),
                "Cắt lỗ": d.get("stop_loss"),
                "Mục tiêu 1 (module)": d.get("target"),
                "R:R": d.get("reward_risk"),
                "Khối lượng gợi ý": d.get("suggested_quantity")
            })

        st.markdown("#### Bảng quyết định toàn bộ danh mục")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=300)

        st.divider()
        st.markdown("#### Chiến lược theo từng mã")
        strategy_symbol = st.selectbox(
            "Chọn mã cần xem chiến lược",
            list(results.keys()),
            key="strategy_symbol"
        )
        enriched_strategy, decision_strategy = results[strategy_symbol]
        latest_close = decision_strategy.get("close")
        st.write(
            f"**{strategy_symbol}** · Tín hiệu hiện tại: "
            f"**{decision_strategy.get('decision', 'Chưa xác định')}**"
        )

        position_mode = st.radio(
            "Trạng thái vị thế",
            ["Chưa có hàng", "Đang có hàng"],
            horizontal=True,
            key="position_mode"
        )

        if position_mode == "Chưa có hàng":
            st.markdown("##### Kế hoạch tham khảo khi chưa nắm giữ")
            pcols = st.columns(4)
            pcols[0].metric("Vùng mua thấp", _fmt_price(decision_strategy.get("buy_zone_low")))
            pcols[1].metric("Vùng mua cao", _fmt_price(decision_strategy.get("buy_zone_high")))
            pcols[2].metric("Cắt lỗ", _fmt_price(decision_strategy.get("stop_loss")))
            pcols[3].metric("Chốt lời 1", _fmt_price(decision_strategy.get("target")))

            qcols = st.columns(3)
            qcols[0].metric(
                "Số lượng đề xuất",
                f"{int(decision_strategy.get('suggested_quantity') or 0):,} cp"
            )
            qcols[1].metric("Tỷ lệ R:R", _fmt_number(decision_strategy.get("reward_risk")))
            qcols[2].metric("Giá xác nhận", "Module chưa cung cấp")

            st.info(
                "Chốt lời 2 chưa được decision_engine.py cung cấp. "
                "Ứng dụng không tự đặt mục tiêu thứ hai từ một công thức chưa được kiểm định."
            )
            st.write("**Đánh giá hiện tại:**", decision_strategy.get("decision", "Chưa xác định"))
            for reason in decision_strategy.get("reasons", []):
                st.write("•", reason)

        else:
            st.markdown("##### Quản lý vị thế đang nắm giữ")
            p1, p2 = st.columns(2)
            avg_price = p1.number_input(
                "Giá vốn bình quân", min_value=0.0, value=0.0,
                step=100.0, format="%.2f", key=f"avg_price_{strategy_symbol}"
            )
            holding_qty = p2.number_input(
                "Số lượng cổ phiếu đang nắm giữ", min_value=0,
                value=0, step=100, key=f"holding_qty_{strategy_symbol}"
            )

            if latest_close is not None and pd.notna(latest_close) and avg_price > 0 and holding_qty > 0:
                market_value = float(latest_close) * int(holding_qty) * multiplier
                cost_value = float(avg_price) * int(holding_qty) * multiplier
                pnl = market_value - cost_value
                pnl_pct = (float(latest_close) / float(avg_price) - 1) * 100

                pcols = st.columns(4)
                pcols[0].metric("Giá hiện tại", _fmt_price(latest_close))
                pcols[1].metric("Giá trị vốn", f"{cost_value:,.0f} đ")
                pcols[2].metric("Lãi / lỗ tạm tính", f"{pnl:,.0f} đ")
                pcols[3].metric("Hiệu suất", f"{pnl_pct:+.2f}%")

                stop_loss = decision_strategy.get("stop_loss")
                target = decision_strategy.get("target")
                signal = decision_strategy.get("decision", "")

                st.markdown("**Định hướng quản trị vị thế theo dữ liệu hiện có**")
                if stop_loss is not None and pd.notna(stop_loss) and float(latest_close) <= float(stop_loss):
                    st.warning(
                        "Giá đóng cửa đã chạm hoặc thấp hơn mức cắt lỗ tham chiếu của module. "
                        "Cần rà soát luận điểm đầu tư và cân nhắc giảm rủi ro vị thế."
                    )
                elif target is not None and pd.notna(target) and float(latest_close) >= float(target):
                    st.success(
                        "Giá đã đạt/vượt mục tiêu hiện có của module. "
                        "Có thể đánh giá việc chốt một phần hoặc bảo vệ thành quả."
                    )
                elif signal == "THEO DÕI ĐIỂM MUA":
                    st.info(
                        "Các điều kiện theo dõi điểm mua của module đang tích cực. "
                        "Ưu tiên giữ kỷ luật tỷ trọng; chỉ cân nhắc mua thêm khi kế hoạch vốn và rủi ro cho phép."
                    )
                elif signal == "KHÔNG MUA MỚI":
                    st.warning(
                        "Module đang đánh giá không phù hợp mua mới. "
                        "Không nên tự động bình quân giá xuống; cần xem xét lại rủi ro và luận điểm nắm giữ."
                    )
                else:
                    st.info(
                        "Tín hiệu chưa đủ xác nhận. Có thể tiếp tục theo dõi, tránh tăng tỷ trọng "
                        "khi chưa có tín hiệu rõ hơn."
                    )

                st.caption(
                    "Lãi/lỗ là ước tính theo giá đóng cửa mới nhất và giá vốn người dùng nhập; "
                    "chưa tính phí, thuế, cổ tức hoặc các giao dịch phát sinh."
                )
            else:
                st.info("Nhập giá vốn lớn hơn 0 và số lượng cổ phiếu lớn hơn 0 để tính lãi/lỗ.")

        with st.expander("Biểu đồ và các mốc giá của mã đang chọn", expanded=False):
            chart_history_strategy = st.selectbox(
                "Số phiên biểu đồ",
                ["60 phiên", "120 phiên", "200 phiên", "Toàn bộ"],
                index=1,
                key="strategy_chart_history"
            )
            history_strategy = (
                None if chart_history_strategy == "Toàn bộ"
                else int(chart_history_strategy.split()[0])
            )
            _candlestick_chart(
                enriched_strategy, decision_strategy,
                strategy_symbol, history=history_strategy
            )
            _show_level_summary(decision_strategy, enriched_strategy)

        st.divider()
        st.markdown("#### Backtest Swing")
        sym = st.selectbox(
            "Mã để backtest", list(data.symbol.unique()), key="bt_symbol"
        )
        if st.button("Chạy backtest mã đã chọn", key="run_swing_backtest"):
            frame = data[data.symbol == sym].copy()
            bt = simple_swing_backtest(frame)
            if "error" in bt:
                st.warning(bt["error"])
            else:
                b1, b2, b3 = st.columns(3)
                b1.metric("Tổng lợi nhuận mô phỏng", f"{bt.get('total_return_pct', 0):+.2f}%")
                b2.metric("Số giao dịch đã đóng", f"{bt.get('closed_trades', 0)}")
                win_rate = bt.get("win_rate_pct")
                b3.metric("Tỷ lệ thắng", "Chưa có giao dịch đóng" if win_rate is None else f"{win_rate:.2f}%")
                with st.expander("Chi tiết giao dịch và đường vốn"):
                    st.json(bt)
                st.caption(bt.get("note", ""))


# =========================================================
# TAB 5 · EXCEL/CSV ĐỘC LẬP - GIỮ NGUYÊN CHỨC NĂNG
# =========================================================
with tabs[4]:
    st.subheader("TAB 5 – Công cụ Excel/CSV độc lập")
    st.caption("TAB này không gọi, không sửa và không phụ thuộc lõi phân tích chứng khoán.")
    file5 = st.file_uploader(
        "Tải Excel/CSV để xử lý riêng",
        type=["csv", "txt", "xlsx", "xls"],
        key="tab5_upload"
    )
    if file5:
        try:
            sheet5 = st.text_input("Sheet TAB 5 (tên hoặc chỉ số)", value="0")
            arg = int(sheet5) if sheet5.isdigit() else sheet5
            table = tab5_excel.read_table(file5, arg)
            st.dataframe(table, use_container_width=True, height=360)
            c1, c2 = st.columns(2)
            c1.download_button(
                "Xuất CSV",
                tab5_excel.to_csv_bytes(table),
                "tab5_export.csv",
                "text/csv"
            )
            c2.download_button(
                "Xuất Excel",
                tab5_excel.to_excel_bytes(table),
                "tab5_export.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Lỗi TAB 5: {e}")
