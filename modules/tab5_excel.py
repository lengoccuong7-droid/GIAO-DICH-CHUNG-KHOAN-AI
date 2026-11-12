"""TAB 5 độc lập: tiện ích đọc/xem/xuất Excel/CSV.
Không import lõi phân tích, chỉ xử lý bảng tính.
"""
import io
import pandas as pd

def read_table(uploaded_file, sheet_name=0):
    name=uploaded_file.name.lower()
    raw=uploaded_file.getvalue()
    bio=io.BytesIO(raw)
    if name.endswith(".csv") or name.endswith(".txt"):
        return pd.read_csv(bio)
    if name.endswith((".xlsx",".xls")):
        return pd.read_excel(bio,sheet_name=sheet_name)
    raise ValueError("TAB 5 hỗ trợ CSV, TXT, XLSX, XLS.")

def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")

def to_excel_bytes(df):
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Data")
    return bio.getvalue()
