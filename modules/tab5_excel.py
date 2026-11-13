"""Tab 5 độc lập: nhập, dán, chỉnh sửa, lưu, mở, đổi tên và xuất CSV/Excel.
Không chuẩn hóa, không ghép dòng, không xóa trùng và không tác động market_data.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "tab5_saved"
BACKUP_DIR = DATA_DIR / "backups"


def _safe_filename(filename: str) -> str:
    name = Path(str(filename)).name.strip()
    name = re.sub(r"[^\w\-.() ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("._")
    if not name:
        raise ValueError("Tên file không hợp lệ.")
    return name


def _path_for(filename: str) -> Path:
    name = _safe_filename(filename)
    path = (DATA_DIR / name).resolve()
    if path.parent != DATA_DIR.resolve():
        raise ValueError("Đường dẫn file không hợp lệ.")
    return path


def detect_separator(text: str) -> str:
    sample = "\n".join(line for line in text.splitlines() if line.strip())[:20000]
    if not sample:
        raise ValueError("Không có dữ liệu để phân tách.")
    # Ưu tiên tab vì dữ liệu copy từ Excel thường dùng tab.
    if "\t" in sample:
        return "\t"
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|").delimiter
    except csv.Error:
        counts = {sep: sample.count(sep) for sep in (";", "|", ",")}
        best = max(counts, key=counts.get)
        return best if counts[best] else "whitespace"


def parse_pasted_text(text: str, delimiter: str = "Tự nhận diện", header: bool = True) -> pd.DataFrame:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Ô nhập dữ liệu đang trống.")
    sep = detect_separator(text) if delimiter in ("Tự nhận diện", "") else delimiter
    if sep == "whitespace":
        df = pd.read_csv(io.StringIO(text.strip()), sep=r"\s+", header=0 if header else None,
                         engine="python", dtype=object, keep_default_na=False)
    else:
        df = pd.read_csv(io.StringIO(text.strip()), sep=sep, header=0 if header else None,
                         engine="python", dtype=object, keep_default_na=False)
    if len(df.columns) == 0:
        raise ValueError("Không nhận diện được cột dữ liệu.")
    if not header:
        df.columns = [f"Cột_{i+1}" for i in range(len(df.columns))]
    return df


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    errors = []
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin1"):
        try:
            text = raw.decode(encoding)
            sep = detect_separator(text)
            kwargs = dict(engine="python", dtype=object, keep_default_na=False)
            if sep == "whitespace":
                return pd.read_csv(io.StringIO(text), sep=r"\s+", **kwargs)
            return pd.read_csv(io.StringIO(text), sep=sep, **kwargs)
        except Exception as exc:
            errors.append(str(exc))
    raise ValueError("Không đọc được CSV/TXT. " + (errors[-1] if errors else ""))


def read_table(uploaded_file, sheet_name=0) -> pd.DataFrame:
    name = str(uploaded_file.name).lower()
    raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    if name.endswith((".csv", ".txt")):
        return _read_csv_bytes(raw)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, dtype=object, keep_default_na=False)
    raise ValueError("Tab 5 hỗ trợ CSV, TXT, XLSX và XLS.")


def normalize_columns(df: pd.DataFrame):
    """Giữ API cũ để không làm hỏng mã gọi hàm; hiện tại tuyệt đối không đổi tên cột."""
    if df is None:
        raise ValueError("Không có bảng dữ liệu.")
    return df.copy(), {}


def validate_table(df: pd.DataFrame):
    """Tương thích ngược: chỉ kiểm tra bảng có tồn tại, không áp luật OHLCV."""
    if df is None:
        return ["Chưa có bảng dữ liệu."]
    return []


def merge_old_and_new(old_df: pd.DataFrame, new_df: pd.DataFrame, keys=None):
    """Tương thích ngược; không tự ghép hoặc loại dòng trùng. Trả về bảng mới nguyên trạng."""
    if new_df is None:
        raise ValueError("Không có dữ liệu mới.")
    return new_df.copy(), 0


def _read_saved(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return _read_csv_bytes(path.read_bytes())
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, dtype=object, keep_default_na=False)
    raise ValueError("Định dạng file lưu không được hỗ trợ.")


def list_saved_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in DATA_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in {".csv", ".xlsx"}
                  and not p.name.endswith(".tmp"))


def load_saved_file(filename: str) -> pd.DataFrame:
    path = _path_for(filename)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {filename}")
    return _read_saved(path)


def _write_file(df: pd.DataFrame, path: Path):
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False, engine="openpyxl")
    else:
        raise ValueError("Chỉ lưu được CSV hoặc XLSX.")


def save_new_file(df: pd.DataFrame, filename: str, file_type: str = "xlsx") -> Path:
    if df is None:
        raise ValueError("Chưa có bảng dữ liệu để lưu.")
    ext = ".csv" if str(file_type).lower() == "csv" else ".xlsx"
    name = _safe_filename(filename)
    if not name.lower().endswith(ext):
        name = Path(name).stem + ext
    path = _path_for(name)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"File {path.name} đã tồn tại. Hãy chọn tên khác hoặc dùng Ghi đè có sao lưu.")
    _write_file(df, path)
    return path


def update_saved_file(df_new: pd.DataFrame, filename: str, keys=None):
    """Ghi đè toàn bộ bằng bảng hiện tại sau khi sao lưu file cũ; không merge/dedup."""
    if df_new is None:
        raise ValueError("Chưa có bảng dữ liệu để ghi đè.")
    path = _path_for(filename)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cũ: {filename}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = BACKUP_DIR / f"{path.stem}_backup_{stamp}{path.suffix}"
    backup.write_bytes(path.read_bytes())
    temp = path.with_name(path.stem + ".tmp" + path.suffix)
    try:
        _write_file(df_new, temp)
        temp.replace(path)
    except Exception:
        if temp.exists():
            temp.unlink()
        raise
    return df_new.copy(), 0, backup


def rename_saved_file(old_name: str, new_name: str) -> Path:
    old_path = _path_for(old_name)
    if not old_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {old_name}")
    new_safe = _safe_filename(new_name)
    if Path(new_safe).suffix.lower() not in {".csv", ".xlsx"}:
        new_safe += old_path.suffix.lower()
    if Path(new_safe).suffix.lower() != old_path.suffix.lower():
        raise ValueError("Đổi tên không được thay đổi định dạng file.")
    new_path = _path_for(new_safe)
    if new_path.exists() and new_path != old_path:
        raise FileExistsError(f"Tên file {new_path.name} đã tồn tại.")
    old_path.rename(new_path)
    return new_path


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return bio.getvalue()
