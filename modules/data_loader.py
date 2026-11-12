from __future__ import annotations
from pathlib import Path
import io, re
import pandas as pd

ALIASES = {
    "date": ["date", "datetime", "time", "ngay", "ngày", "tradingdate"],
    "open": ["open", "mo cua", "mở cửa", "gia mo cua"],
    "high": ["high", "cao nhat", "cao nhất", "gia cao nhat"],
    "low": ["low", "thap nhat", "thấp nhất", "gia thap nhat"],
    "close": ["close", "dong cua", "đóng cửa", "gia dong cua"],
    "volume": ["volume", "vol", "khoi luong", "khối lượng"],
    "symbol": ["symbol", "ticker", "ma", "mã", "stock", "code"],
}

def _norm(x):
    return re.sub(r"[\s_\-]+", " ", str(x).strip().lower())

def _read_file(name: str, raw: bytes, sheet_name=0) -> pd.DataFrame:
    ext = Path(name).suffix.lower()
    bio = io.BytesIO(raw)
    if ext == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin1"):
            try:
                bio.seek(0); return pd.read_csv(bio, encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("Không đọc được mã hóa CSV.")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(bio, sheet_name=sheet_name)
    if ext == ".json":
        return pd.read_json(bio)
    if ext == ".txt":
        try:
            return pd.read_csv(bio, sep=None, engine="python")
        except Exception:
            bio.seek(0); return pd.read_csv(bio, sep=r"\s+", engine="python")
    if ext == ".parquet":
        return pd.read_parquet(bio)
    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError as e:
            raise ValueError("Cần cài pdfplumber để đọc PDF.") from e
        rows = []
        with pdfplumber.open(bio) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    rows.extend(table)
        if not rows:
            raise ValueError("Không tìm thấy bảng văn bản trong PDF.")
        return pd.DataFrame(rows[1:], columns=rows[0])
    if ext == ".docx":
        try:
            from docx import Document
        except ImportError as e:
            raise ValueError("Cần cài python-docx để đọc DOCX.") from e
        doc = Document(bio)
        rows = []
        for table in doc.tables:
            for row in table.rows:
                rows.append([c.text.strip() for c in row.cells])
        if len(rows) < 2:
            raise ValueError("Không tìm thấy bảng dữ liệu trong DOCX.")
        return pd.DataFrame(rows[1:], columns=rows[0])
    raise ValueError(f"Định dạng chưa hỗ trợ: {ext}")

def normalize_ohlcv(df: pd.DataFrame, symbol_hint=None) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("File không có dữ liệu.")
    rename = {}
    norm_map = {_norm(c): c for c in df.columns}
    for target, aliases in ALIASES.items():
        found = None
        for alias in aliases:
            if _norm(alias) in norm_map:
                found = norm_map[_norm(alias)]; break
        if found is not None:
            rename[found] = target
    out = df.rename(columns=rename).copy()
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError("Thiếu cột bắt buộc: " + ", ".join(missing))
    out["date"] = pd.to_datetime(out["date"], dayfirst=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    if "symbol" not in out.columns:
        out["symbol"] = str(symbol_hint or "UNKNOWN").upper()
    else:
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
        if symbol_hint:
            out["symbol"] = out["symbol"].replace("", str(symbol_hint).upper())
    out = out[["date", "symbol", "open", "high", "low", "close", "volume"]]
    if out[required].isna().any().any():
        bad = int(out[required].isna().any(axis=1).sum())
        raise ValueError(f"Có {bad} dòng ngày/giá/khối lượng không hợp lệ; không tự điền.")
    if (out[["open","high","low","close"]] <= 0).any().any():
        raise ValueError("Giá OHLC phải lớn hơn 0.")
    if (out["volume"] < 0).any():
        raise ValueError("Khối lượng không được âm.")
    invalid = (out["high"] < out[["open","low","close"]].max(axis=1)) | (out["low"] > out[["open","high","close"]].min(axis=1))
    if invalid.any():
        raise ValueError(f"Có {int(invalid.sum())} dòng sai quan hệ OHLC.")
    if out.duplicated(["symbol","date"]).any():
        dup = out.loc[out.duplicated(["symbol","date"], keep=False), ["symbol","date"]]
        raise ValueError("Trùng mã/ngày: " + str(dup.head(5).to_dict("records")))
    out = out.sort_values(["symbol","date"]).reset_index(drop=True)
    return out

def load_market_file(uploaded_file, sheet_name=0, symbol_hint=None):
    raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    frame = _read_file(uploaded_file.name, raw, sheet_name)
    return normalize_ohlcv(frame, symbol_hint=symbol_hint)
