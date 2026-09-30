"""Nghiệp vụ tuyển sinh — tách khỏi giao diện để dễ kiểm thử."""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from .schema import (BOOL, DATE, NHAP_HOC, NUMBER, THU_PHI, TUYEN_SINH, ListDef)
from .storage.base import Storage


def today() -> str:
    return date.today().isoformat()


def normalize_phone(v: str | None) -> str:
    digits = re.sub(r"\D", "", str(v or ""))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits


def validate(ld: ListDef, data: dict) -> list[str]:
    errors = []
    for f in ld.fields:
        v = data.get(f.key)
        if f.required and (v is None or str(v).strip() == ""):
            errors.append(f"Chưa nhập **{f.label}**")
        elif f.type == NUMBER and v not in (None, ""):
            try:
                float(v)
            except (TypeError, ValueError):
                errors.append(f"**{f.label}** phải là số")
    if ld is TUYEN_SINH and data.get("SDT"):
        if not re.fullmatch(r"0\d{9,10}", normalize_phone(data["SDT"])):
            errors.append("**SĐT** không hợp lệ (10–11 số, bắt đầu bằng 0)")
    return errors


def to_df(ld: ListDef, items: list[dict]) -> pd.DataFrame:
    cols = ["id"] + ld.keys + ["Created", "Modified"]
    df = pd.DataFrame(items)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    for f in ld.fields:
        if f.type == NUMBER:
            df[f.key] = pd.to_numeric(df[f.key], errors="coerce").fillna(0)
        elif f.type == BOOL:
            df[f.key] = df[f.key].fillna(False).astype(bool)
        elif f.type == DATE:
            df[f.key] = pd.to_datetime(df[f.key], errors="coerce").dt.date
        else:
            df[f.key] = df[f.key].fillna("").astype(str)
    return df


def load_df(storage: Storage, ld: ListDef, nam_hoc: str | None = None) -> pd.DataFrame:
    df = to_df(ld, storage.list_items(ld.name))
    if nam_hoc:
        df = df[df["NamHoc"] == nam_hoc]
    return df.reset_index(drop=True)


def _clean(ld: ListDef, data: dict) -> dict:
    out = {}
    for f in ld.fields:
        if f.key not in data:
            continue
        v = data[f.key]
        if f.type == DATE:
            if v is None or v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
                v = ""
            else:
                v = v.isoformat()[:10] if isinstance(v, date) else str(v or "")[:10]
        elif f.type == NUMBER:
            v = float(v) if v not in (None, "") else 0
        elif f.type == BOOL:
            v = bool(v)
        else:
            v = "" if v is None else str(v).strip()
        out[f.key] = v
    return out


# ------------------------------------------------------------------ Tuyển sinh
def find_duplicates(storage: Storage, data: dict, exclude_id: str | None = None) -> list[dict]:
    """HS trùng SĐT + họ tên trong cùng năm học."""
    phone = normalize_phone(data.get("SDT"))
    name = str(data.get("HoTenHS", "")).strip().lower()
    return [
        it for it in storage.list_items(TUYEN_SINH.name)
        if it.get("NamHoc") == data.get("NamHoc") and it["id"] != exclude_id
        and normalize_phone(it.get("SDT")) == phone
        and str(it.get("HoTenHS", "")).strip().lower() == name
    ]


def save_tuyen_sinh(storage: Storage, data: dict, item_id: str | None = None) -> dict:
    data = dict(data)
    data.setdefault("TrangThai", "Tư vấn")
    if data.get("SDT"):
        data["SDT"] = normalize_phone(data["SDT"])
    errors = validate(TUYEN_SINH, data)
    if errors:
        raise ValueError("\n".join(errors))
    clean = _clean(TUYEN_SINH, data)
    if item_id:
        old = storage.get_item(TUYEN_SINH.name, item_id) or {}
        rec = storage.update_item(TUYEN_SINH.name, item_id, clean)
        if old.get("TrangThai") != rec.get("TrangThai"):
            rec = set_trang_thai(storage, item_id, rec["TrangThai"])
        elif rec.get("TrangThai") == "Nhập học":
            sync_nhap_hoc(storage, rec)
        return rec
    rec = storage.create_item(TUYEN_SINH.name, clean)
    if rec.get("TrangThai") != "Tư vấn":
        rec = set_trang_thai(storage, rec["id"], rec["TrangThai"])
    return rec


def set_trang_thai(storage: Storage, item_id: str, trang_thai: str,
                   ly_do: str | None = None) -> dict:
    """Chuyển trạng thái HS: Tư vấn → Nộp hồ sơ → Nhập học, hoặc Rút hồ sơ.

    Khi chuyển sang "Nhập học" sẽ tạo hồ sơ trong Data_NhapHoc (nếu chưa có).
    """
    rec = storage.get_item(TUYEN_SINH.name, item_id)
    if rec is None:
        raise KeyError(item_id)
    upd = {"TrangThai": trang_thai}
    date_field = {"Nộp hồ sơ": "NgayNopHoSo", "Nhập học": "NgayNhapHoc",
                  "Rút hồ sơ": "NgayRutHoSo"}.get(trang_thai)
    if date_field and not rec.get(date_field):
        upd[date_field] = today()
    if trang_thai in ("Nhập học", "Nộp hồ sơ") and not rec.get("NgayNopHoSo"):
        upd["NgayNopHoSo"] = today()
    if ly_do is not None:
        upd["LyDoRut"] = ly_do
    rec = storage.update_item(TUYEN_SINH.name, item_id, upd)
    if trang_thai == "Nhập học":
        sync_nhap_hoc(storage, rec)
    return rec


def nhap_hoc_of(storage: Storage, tuyen_sinh_id: str) -> dict | None:
    for it in storage.list_items(NHAP_HOC.name):
        if str(it.get("TuyenSinhID")) == str(tuyen_sinh_id):
            return it
    return None


def _che_do_to_vemis(che_do: str) -> str:
    return che_do if che_do in ("Nội trú", "Bán trú") else ""


def sync_nhap_hoc(storage: Storage, ts: dict) -> dict:
    """Tạo (hoặc bổ sung thông tin còn trống) hồ sơ nhập học từ bản ghi tuyển sinh."""
    prefill = {
        "TuyenSinhID": ts["id"],
        "NamHoc": ts.get("NamHoc", ""),
        "LopHoc": ts.get("Khoi", ""),
        "HoTen": ts.get("HoTenHS", ""),
        "NgaySinh": ts.get("NgaySinh", ""),
        "GioiTinh": ts.get("GioiTinh", ""),
        "NgayVaoTruong": ts.get("NgayNhapHoc") or today(),
        "NoiTruBanTru": _che_do_to_vemis(ts.get("CheDo", "")),
        "DienThoaiSLL": ts.get("SDT", ""),
        "EmailSLL": ts.get("Email", ""),
        "QuocTich": "Việt Nam",
        "DanToc": "Kinh",
        "TonGiao": "Không",
        "DienChinhSach": "Không",
    }
    cur = nhap_hoc_of(storage, ts["id"])
    if cur is None:
        return storage.create_item(NHAP_HOC.name, _clean(NHAP_HOC, prefill))
    missing = {k: v for k, v in prefill.items() if v and not cur.get(k)}
    return storage.update_item(NHAP_HOC.name, cur["id"], _clean(NHAP_HOC, missing)) if missing else cur


def save_nhap_hoc(storage: Storage, data: dict, item_id: str | None = None) -> dict:
    errors = validate(NHAP_HOC, data)
    if errors:
        raise ValueError("\n".join(errors))
    clean = _clean(NHAP_HOC, data)
    if item_id:
        return storage.update_item(NHAP_HOC.name, item_id, clean)
    return storage.create_item(NHAP_HOC.name, clean)


def nhap_hoc_df(storage: Storage, nam_hoc: str) -> pd.DataFrame:
    """Hồ sơ nhập học của năm, bỏ các HS đã rút hồ sơ sau khi nhập học."""
    df = load_df(storage, NHAP_HOC, nam_hoc)
    ts = load_df(storage, TUYEN_SINH)
    rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
    return df[~df["TuyenSinhID"].isin(rut)].reset_index(drop=True)


# ------------------------------------------------------------------ Kế toán
def add_payment(storage: Storage, data: dict) -> dict:
    data = dict(data)
    data.setdefault("TrangThaiXN", "Chờ xác nhận")
    data.setdefault("NgayThu", today())
    errors = validate(THU_PHI, data)
    if not errors and float(data.get("SoTien") or 0) <= 0:
        errors.append("**Số tiền** phải lớn hơn 0")
    if errors:
        raise ValueError("\n".join(errors))
    return storage.create_item(THU_PHI.name, _clean(THU_PHI, data))


def confirm_payments(storage: Storage, ids: list[str], nguoi: str,
                     trang_thai: str = "Đã xác nhận") -> int:
    for i in ids:
        storage.update_item(THU_PHI.name, i, {"TrangThaiXN": trang_thai, "NguoiXacNhan": nguoi,
                                              "NgayXacNhan": today()})
    return len(ids)


def payment_summary(ts: pd.DataFrame, tp: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp số tiền đã xác nhận theo từng HS và loại phí."""
    base = ts[ts["TrangThai"].isin(["Nộp hồ sơ", "Nhập học"])][
        ["id", "HoTenHS", "Khoi", "CheDo", "SDT", "TrangThai"]].rename(columns={"id": "TuyenSinhID"})
    ok = tp[tp["TrangThaiXN"] == "Đã xác nhận"]
    if ok.empty:
        pv = pd.DataFrame(columns=["TuyenSinhID"])
    else:
        pv = ok.pivot_table(index="TuyenSinhID", columns="LoaiPhi", values="SoTien",
                            aggfunc="sum", fill_value=0).reset_index()
        pv.columns.name = None
    out = base.merge(pv, on="TuyenSinhID", how="left")
    fee_cols = [c for c in out.columns if c not in base.columns]
    out[fee_cols] = out[fee_cols].fillna(0)
    out["Tổng đã thu"] = out[fee_cols].sum(axis=1) if fee_cols else 0
    return out
