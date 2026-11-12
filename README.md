# BOT TRADER SWING – MULTI STOCK (OFFLINE)

## Chạy ứng dụng
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Nguyên tắc dữ liệu
- Không chứa dữ liệu cổ phiếu mẫu trong mã nguồn.
- Dữ liệu phân tích được đọc từ file do người dùng tải lên.
- Không tải dữ liệu từ Internet.
- Không tự điền chỉ báo bị thiếu bằng số giả.
- Chỉ báo được tính từ OHLCV khi đủ dữ liệu và có công thức rõ ràng.
- DXG chỉ là một file kiểm thử do người dùng cung cấp, không bị mã hóa cố định.

## Định dạng
CSV, XLSX, XLS, JSON, TXT, Parquet, PDF (bảng văn bản trích xuất được), DOCX (bảng).
PDF/DOCX không phải file dữ liệu giá chuyên dụng; cần bảng có tiêu đề cột nhận diện được.
XLS yêu cầu xlrd; Parquet yêu cầu pyarrow.

## Cấu trúc dữ liệu tối thiểu
Date, Open, High, Low, Close, Volume.
Có thể thêm Symbol/Ticker để phân tích nhiều mã trong cùng file.
Đơn vị giá được giữ nguyên theo file. Không tự nhân/chia 1.000.

## Ghi chú
Đây là công cụ hỗ trợ phân tích, không bảo đảm lợi nhuận và không tự đặt lệnh.
Backtest là mô phỏng đơn giản, cần tính thêm phí, thuế, trượt giá theo cấu hình phù hợp trước khi dùng vốn thật.

## Trợ lý phân tích TAB 3
TAB 3 dùng bộ luật diễn giải offline (rule-based), không gọi mô hình AI cloud. Các nhận định được truy ra từ chỉ báo thực tế; không có kết nối mạng. Muốn dùng mô hình ngôn ngữ AI thực thụ cần một mô hình local riêng và kiểm định độc lập.
