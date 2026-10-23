"""Phân hệ Nội trú: phòng, giáo viên quản nhiệm, đánh giá nề nếp và học bài tối theo ngày.

- Phòng (list NoiTru_Phong): mỗi năm học, mỗi phòng có 1 giáo viên quản nhiệm và danh sách
  học sinh (ID hồ sơ nhập học).
- Đánh giá (list NoiTru_DanhGia): mỗi bản ghi là MỘT PHÒNG trong MỘT NGÀY, đánh giá từng học
  sinh lưu dạng JSON — lưu cả phòng chỉ cần 1 lần ghi lên SharePoint.

Quyền: nhập/sửa đánh giá: giáo viên quản nhiệm của phòng (phòng mình), Tổ trưởng quản nhiệm và
Quản trị (mọi phòng); xem đánh giá: mọi người vào được
trang; quản lý phòng và báo cáo tổng hợp: Tổ trưởng quản nhiệm, Quản trị.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from .schema import MUC_DANH_GIA, NOI_TRU_DANH_GIA, NOI_TRU_PHONG
from .storage.base import Storage

DIEM = {"Tốt": 4, "Khá": 3, "Trung bình": 2, "Chưa tốt": 1}
CAN_CHU_Y = ("Trung bình", "Chưa tốt")
MUC = ("NeNep", "HocBaiToi")
TEN_MUC = {"NeNep": "Nề nếp", "HocBaiToi": "Học bài tối"}
VAI_QUAN_LY = ("Quản trị", "Tổ trưởng quản nhiệm")


# ------------------------------------------------------------------ quyền
def la_quan_ly(tk: dict | None) -> bool:
    """Tổ trưởng quản nhiệm / Quản trị (app chưa dùng tài khoản: ai cũng là quản lý)."""
    return not tk or tk.get("VaiTro") in VAI_QUAN_LY


def duoc_nhap(phong: dict, tk: dict | None) -> bool:
    """Giáo viên quản nhiệm nhập phòng mình; Tổ trưởng quản nhiệm / Quản trị nhập mọi phòng."""
    if la_quan_ly(tk):
        return True
    return bool(tk.get("id")) and str(phong.get("GiaoVienID") or "") == str(tk["id"])


# ------------------------------------------------------------------ phòng
def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def hs_ids(phong: dict) -> list[str]:
    return [x.strip() for x in _s(phong.get("HocSinhIDs")).split(";") if x.strip()]


def phong_nam(phongs: list[dict], nam_hoc: str) -> list[dict]:
    ds = [p for p in phongs if _s(p.get("NamHoc")) == nam_hoc]
    return sorted(ds, key=lambda p: (_s(p.get("Khu")), _so_tu_nhien(_s(p.get("TenPhong")))))


def _so_tu_nhien(s: str) -> tuple:
    import re
    return tuple(int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", s))


def phong_cua_hs(phongs: list[dict]) -> dict[str, dict]:
    return {i: p for p in phongs for i in hs_ids(p)}


def luu_phong(storage: Storage, phongs: list[dict], nam_hoc: str, ten: str, khu: str,
              gv: dict | None, hoc_sinh: list[str], ghi_chu: str = "",
              item_id: str | None = None) -> dict:
    """Thêm / sửa phòng. Tên phòng không trùng trong năm; mỗi học sinh chỉ ở một phòng."""
    ten = _s(ten)
    if not ten:
        raise ValueError("Cần nhập **Tên phòng**.")
    cung_nam = [p for p in phongs if _s(p.get("NamHoc")) == nam_hoc
                and str(p.get("id")) != str(item_id)]
    if any(_s(p.get("TenPhong")).lower() == ten.lower() for p in cung_nam):
        raise ValueError(f"Phòng **{ten}** đã có trong năm học {nam_hoc}.")
    o_phong_khac = phong_cua_hs(cung_nam)
    trung = [i for i in hoc_sinh if i in o_phong_khac]
    if trung:
        ten_p = sorted({_s(o_phong_khac[i].get("TenPhong")) for i in trung})
        raise ValueError(f"{len(trung)} học sinh đang ở phòng khác ({', '.join(ten_p)}). "
                         "Bỏ các em khỏi phòng cũ trước.")
    data = {"NamHoc": nam_hoc, "TenPhong": ten, "Khu": _s(khu),
            "GiaoVienID": _s((gv or {}).get("id")), "GiaoVien": _s((gv or {}).get("HoTen")),
            "HocSinhIDs": ";".join(dict.fromkeys(hoc_sinh)), "GhiChu": _s(ghi_chu)}
    if item_id:
        return storage.update_item(NOI_TRU_PHONG.name, item_id, data)
    return storage.create_item(NOI_TRU_PHONG.name, data)


# ------------------------------------------------------------------ đánh giá
def _ngay(v) -> date | None:
    d = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(d) else d.date()


def tim_ban_ghi(danh_gia: list[dict], phong_id: str, ngay: date) -> dict | None:
    for r in danh_gia:
        if str(r.get("PhongID")) == str(phong_id) and _ngay(r.get("Ngay")) == ngay:
            return r
    return None


def doc_du_lieu(r: dict) -> list[dict]:
    try:
        v = json.loads(_s(r.get("DuLieu")) or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def luu_danh_gia(storage: Storage, danh_gia: list[dict], nam_hoc: str, ngay: date,
                 phong: dict, dong: list[dict], nguoi: str) -> dict:
    """Ghi đánh giá cả phòng trong ngày (tạo mới hoặc ghi đè bản ghi đã có).

    `dong`: [{"id", "ten", "lop", "NeNep", "HocBaiToi", "GhiChu"}]"""
    if not dong:
        raise ValueError("Phòng chưa có học sinh nào để đánh giá.")
    sach = []
    for d in dong:
        x = {"id": _s(d.get("id")), "ten": _s(d.get("ten")), "lop": _s(d.get("lop")),
             "GhiChu": _s(d.get("GhiChu"))}
        for m in MUC:
            v = _s(d.get(m)) or "Tốt"
            if v not in MUC_DANH_GIA:
                raise ValueError(f"Mức đánh giá không hợp lệ: {v}")
            x[m] = v
        sach.append(x)
    data = {"NamHoc": nam_hoc, "Ngay": ngay.isoformat(), "PhongID": _s(phong.get("id")),
            "Phong": _s(phong.get("TenPhong")), "NguoiDanhGia": _s(nguoi),
            "DuLieu": json.dumps(sach, ensure_ascii=False, separators=(",", ":")),
            "SoHS": len(sach),
            "SoChuaTot": sum(x[m] in CAN_CHU_Y for x in sach for m in MUC)}
    cu = tim_ban_ghi(danh_gia, phong.get("id"), ngay)
    if cu:
        return storage.update_item(NOI_TRU_DANH_GIA.name, cu["id"], data)
    return storage.create_item(NOI_TRU_DANH_GIA.name, data)


def bang_dai(danh_gia: list[dict], nam_hoc: str | None = None) -> pd.DataFrame:
    """Mỗi dòng = một học sinh trong một ngày."""
    rows = []
    for r in danh_gia:
        if nam_hoc and _s(r.get("NamHoc")) != nam_hoc:
            continue
        ngay = _ngay(r.get("Ngay"))
        if ngay is None:
            continue
        for d in doc_du_lieu(r):
            rows.append({"Ngày": ngay, "PhongID": _s(r.get("PhongID")), "Phòng": _s(r.get("Phong")),
                         "HocSinhID": _s(d.get("id")), "Học sinh": _s(d.get("ten")),
                         "Lớp": _s(d.get("lop")), "Nề nếp": _s(d.get("NeNep")),
                         "Học bài tối": _s(d.get("HocBaiToi")), "Ghi chú": _s(d.get("GhiChu")),
                         "Người đánh giá": _s(r.get("NguoiDanhGia"))})
    cols = ["Ngày", "PhongID", "Phòng", "HocSinhID", "Học sinh", "Lớp", "Nề nếp", "Học bài tối",
            "Ghi chú", "Người đánh giá"]
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ báo cáo
def ngay_trong_khoang(tu: date, den: date, thu: list[int]) -> list[date]:
    """Các ngày trong khoảng thuộc những thứ được chọn (0 = Thứ Hai … 6 = Chủ nhật)."""
    if den < tu:
        return []
    return [d.date() for d in pd.date_range(tu, den) if d.weekday() in thu]


def _ty_le_tot(s: pd.Series) -> float | None:
    """% lượt "Tốt"; chưa có lượt đánh giá nào thì None (hiện "—", không phải 0%)."""
    return round(100 * (s == "Tốt").mean(), 1) if len(s) else None


def tong_hop_phong(long: pd.DataFrame, phongs: list[dict], ngays: list[date]) -> pd.DataFrame:
    """Theo phòng: số ngày đã/chưa nhập, tỷ lệ Tốt và số lượt cần chú ý của 2 mục."""
    out = []
    for p in phongs:
        x = long[long["PhongID"] == str(p.get("id"))]
        x = x[x["Ngày"].isin(ngays)] if ngays else x.iloc[0:0]
        da = x["Ngày"].nunique()
        out.append({"Phòng": _s(p.get("TenPhong")), "Khu": _s(p.get("Khu")),
                    "Giáo viên": _s(p.get("GiaoVien")), "Số HS": len(hs_ids(p)),
                    "Ngày đã nhập": da, "Ngày chưa nhập": max(len(ngays) - da, 0),
                    "Nề nếp Tốt (%)": _ty_le_tot(x["Nề nếp"]),
                    "Học bài Tốt (%)": _ty_le_tot(x["Học bài tối"]),
                    "Lượt nề nếp TB/Chưa tốt": int(x["Nề nếp"].isin(CAN_CHU_Y).sum()),
                    "Lượt học bài TB/Chưa tốt": int(x["Học bài tối"].isin(CAN_CHU_Y).sum())})
    return pd.DataFrame(out)


def hoc_sinh_can_chu_y(long: pd.DataFrame, toi_thieu: int = 2) -> pd.DataFrame:
    """Học sinh có từ `toi_thieu` lượt Trung bình / Chưa tốt (cả 2 mục) trong khoảng đã lọc."""
    if long.empty:
        return pd.DataFrame(columns=["Học sinh", "Lớp", "Phòng", "Số ngày", "Nề nếp TB/CT",
                                     "Học bài TB/CT", "Tổng lượt", "Điểm TB", "Ghi chú gần nhất"])
    x = long.assign(_nn=long["Nề nếp"].isin(CAN_CHU_Y), _hb=long["Học bài tối"].isin(CAN_CHU_Y),
                    _d=(long["Nề nếp"].map(DIEM) + long["Học bài tối"].map(DIEM)) / 2)
    g = x.sort_values("Ngày").groupby("HocSinhID").agg(**{
        "Học sinh": ("Học sinh", "last"), "Lớp": ("Lớp", "last"), "Phòng": ("Phòng", "last"),
        "Số ngày": ("Ngày", "nunique"), "Nề nếp TB/CT": ("_nn", "sum"),
        "Học bài TB/CT": ("_hb", "sum"), "Điểm TB": ("_d", "mean"),
        "Ghi chú gần nhất": ("Ghi chú", lambda s: next((v for v in reversed(s.tolist()) if v), ""))})
    g["Tổng lượt"] = g["Nề nếp TB/CT"] + g["Học bài TB/CT"]
    g["Điểm TB"] = g["Điểm TB"].round(2)
    g = g[g["Tổng lượt"] >= toi_thieu].sort_values(["Tổng lượt", "Điểm TB"],
                                                   ascending=[False, True])
    return g[["Học sinh", "Lớp", "Phòng", "Số ngày", "Nề nếp TB/CT", "Học bài TB/CT",
              "Tổng lượt", "Điểm TB", "Ghi chú gần nhất"]].reset_index(drop=True)


def tinh_hinh_nhap(long: pd.DataFrame, phongs: list[dict], ngays: list[date]) -> pd.DataFrame:
    """Phòng × ngày: ✓ đã nhập, ✗ chưa nhập (để Tổ trưởng nhắc giáo viên)."""
    da = set(zip(long["PhongID"], long["Ngày"]))
    rows = []
    for p in phongs:
        r = {"Phòng": _s(p.get("TenPhong")), "Giáo viên": _s(p.get("GiaoVien"))}
        for d in ngays:
            r[f"{d:%d/%m}"] = "✓" if (str(p.get("id")), d) in da else "✗"
        rows.append(r)
    return pd.DataFrame(rows)


def theo_ngay(long: pd.DataFrame) -> pd.DataFrame:
    """Tỷ lệ Tốt của 2 mục theo từng ngày (toàn khu nội trú)."""
    if long.empty:
        return pd.DataFrame(columns=["Ngày", "Mục", "Tỷ lệ Tốt (%)"])
    g = long.groupby("Ngày").agg(**{"Nề nếp": ("Nề nếp", _ty_le_tot),
                                    "Học bài tối": ("Học bài tối", _ty_le_tot)}).reset_index()
    return g.melt("Ngày", ["Nề nếp", "Học bài tối"], var_name="Mục", value_name="Tỷ lệ Tốt (%)")


def phan_bo_muc(long: pd.DataFrame) -> pd.DataFrame:
    """Số lượt từng mức của 2 mục."""
    rows = []
    for col in ("Nề nếp", "Học bài tối"):
        vc = long[col].value_counts()
        for m in MUC_DANH_GIA:
            rows.append({"Mục": col, "Mức": m, "Số lượt": int(vc.get(m, 0))})
    return pd.DataFrame(rows)
