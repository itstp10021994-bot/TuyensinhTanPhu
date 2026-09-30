"""Thiết lập list SharePoint và nhập dữ liệu Excel — dùng chung cho trang "Cài đặt" và scripts/."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pandas as pd

from . import config, danh_muc, services
from .export_vemis import COLUMNS, HEADER_ROW
from .schema import ALL_LISTS, NHAP_HOC, TUYEN_SINH, ListDef
from .storage.base import Storage
from .storage.convert import ColumnMap


# ------------------------------------------------------------------ thiết lập list
def check_lists(storage: Storage) -> list[dict]:
    """Tình trạng từng list: có chưa, cột nào đã khớp, cột nào còn thiếu."""
    out = []
    for ld in ALL_LISTS:
        row = {"list": ld, "ten": config.list_name(ld.name), "co_list": False,
               "khop": {}, "thieu": [], "loi": ""}
        try:
            row["co_list"] = storage.list_exists(ld.name)
            if row["co_list"]:
                cm = ColumnMap(ld.name, storage.columns(ld.name))
                row["khop"], row["thieu"] = cm.internal, cm.missing
            else:
                row["thieu"] = list(ld.keys)
        except Exception as e:  # lỗi kết nối
            row["loi"] = str(e)
        out.append(row)
    return out


def setup_lists(storage: Storage, log: Callable[[str], None] = print) -> None:
    """Tạo list chưa có và thêm các cột còn thiếu (không xóa / đổi cột có sẵn)."""
    for ld in ALL_LISTS:
        name = config.list_name(ld.name)
        if not storage.list_exists(ld.name):
            log(f"Tạo list {name}")
            storage.create_list(ld.name, ld.title)
        cm = ColumnMap(ld.name, storage.columns(ld.name))
        for key in cm.missing:
            f = ld.get(key)
            log(f"{name}: thêm cột “{f.sp_title}” ({key})")
            storage.add_column(ld.name, f, key)
    log("Xong.")


# ------------------------------------------------------------------ đọc Excel
def _blank(v) -> bool:
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() in ("", "nan", "NaN", "NaT", "None")


def read_vemis(src) -> pd.DataFrame:
    raw = pd.read_excel(src, header=None, skiprows=HEADER_ROW + 1, dtype=str)
    raw = raw.iloc[:, :len(COLUMNS)]
    raw.columns = [key or "STT" for _, _, key in COLUMNS][:raw.shape[1]]
    raw = raw.dropna(subset=["HoTen"])
    for k in ("CanNgheo", "DoanVien", "DoiVien"):
        raw[k] = raw[k].fillna("").str.strip().str.lower().eq("x")
    for k in ("NgaySinh", "NgayVaoTruong", "NgayCapCanCuoc"):
        raw[k] = pd.to_datetime(raw[k], dayfirst=True, errors="coerce").dt.date
    return raw.drop(columns=["STT"])


def guess_list(sheet_names: list[str]) -> ListDef:
    return NHAP_HOC if NHAP_HOC.name in sheet_names and TUYEN_SINH.name not in sheet_names \
        else TUYEN_SINH


def read_frame(src, ld: ListDef, sheet: str | None = None, vemis: bool = False,
               mapping: dict[str, str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Đọc file → DataFrame với cột = key trong app. Trả về (dữ liệu, cột bỏ qua)."""
    if vemis:
        df = read_vemis(src)
    elif str(getattr(src, "name", src)).lower().endswith(".csv"):
        df = pd.read_csv(src, dtype=str)
    else:
        sheets = pd.ExcelFile(src).sheet_names
        sheet = sheet or (ld.name if ld.name in sheets else sheets[0])
        df = pd.read_excel(src, sheet_name=sheet, dtype=str)
    # nhận key, nhãn trong app và tên hiển thị trên SharePoint (file "Export to Excel")
    rename = {f.label: f.key for f in ld.fields}
    rename.update({f.sp_title: f.key for f in ld.fields})
    rename.update(mapping or {})
    df = df.rename(columns=rename)
    keep = [c for c in df.columns if c in ld.keys or c == "Title"]
    skipped = [str(c) for c in df.columns if c not in keep]
    df = df[keep].dropna(how="all")
    return df, skipped


# ------------------------------------------------------------------ nhập
def signature(ld: ListDef, rec: dict) -> tuple:
    """Dấu hiệu nhận biết một dòng đã có (để chạy lại không bị trùng)."""
    def d(v):
        return str(v)[:10] if not _blank(v) else ""

    if ld is NHAP_HOC:
        return (rec.get("NamHoc") or "", danh_muc.fold(rec.get("HoTen")), d(rec.get("NgaySinh")))
    return (rec.get("NamHoc") or "", danh_muc.fold(rec.get("HoTenHS")),
            services.normalize_phone(rec.get("SDT")), d(rec.get("NgayLienHe")))


def import_rows(storage: Storage, ld: ListDef, df: pd.DataFrame, nam_hoc: str,
                keep_all: bool = True, skip_existing: bool = True, workers: int = 6,
                progress: Callable[[int, int], None] | None = None) -> dict:
    """Ghi các dòng vào list.

    keep_all: chuyển dữ liệu cũ — ghi cả dòng thiếu trường bắt buộc (không kiểm tra).
    skip_existing: bỏ qua dòng đã có trên list (chạy lại an toàn khi bị ngắt giữa chừng).
    """
    rows = []
    for i, row in df.iterrows():
        data = {k: v for k, v in row.to_dict().items() if not _blank(v)}
        data.setdefault("NamHoc", nam_hoc)
        rows.append((i, data))

    if hasattr(storage, "colmap"):  # đọc cấu trúc cột 1 lần trước khi ghi song song
        storage.colmap(ld.name)
    # Đếm số bản đã có trên list theo dấu hiệu; chỉ bỏ qua đúng số đó (dòng trùng nhau
    # ngay trong file dữ liệu cũ vẫn được giữ đủ)
    existing = Counter()
    if skip_existing:
        existing = Counter(signature(ld, it) for it in storage.list_items(ld.name))

    todo, skipped = [], 0
    for i, data in rows:
        clean = services._clean(ld, data)
        if keep_all and data.get("Title"):
            clean["Title"] = data["Title"]
        sig = signature(ld, clean)
        if existing[sig] > 0:
            existing[sig] -= 1
            skipped += 1
            continue
        todo.append((i, data, clean))

    def write(item):
        i, data, clean = item
        if keep_all:
            return storage.create_item(ld.name, clean)
        if ld is TUYEN_SINH:
            return services.save_tuyen_sinh(storage, data)
        return services.save_nhap_hoc(storage, data)

    ok, errors, done = 0, [], 0
    total = len(todo)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(write, item): item for item in todo}
        for fut in as_completed(futures):
            i = futures[fut][0]
            try:
                fut.result()
                ok += 1
            except Exception as e:  # ghi tiếp các dòng khác, báo lỗi cuối cùng
                errors.append({"Dòng": i + 2, "Lỗi": str(e)[:300]})
            done += 1
            if progress:
                progress(done, total)
    return {"ok": ok, "skipped": skipped, "errors": sorted(errors, key=lambda e: e["Dòng"]),
            "total": len(rows)}
