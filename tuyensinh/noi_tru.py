"""Phân hệ Nội trú: phòng, giáo viên quản nhiệm, đánh giá hằng ngày từng học sinh theo 6 mục.

Mục chọn mức (Tốt / Khá / Trung bình / Chưa tốt) kèm lời nhận xét: Nề nếp, Học tập,
Sức khỏe - Tâm lý. Mục viết lời: Điểm sáng trong tháng, Quá trình trao đổi và hỗ trợ,
Định hướng giáo dục.

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
# Mục chọn mức (kèm lời nhận xét) — key trong JSON -> tên cột hiển thị
MUC = ("NeNep", "HocTap", "SucKhoe")
TEN_MUC = {"NeNep": "Nề nếp", "HocTap": "Học tập", "SucKhoe": "Sức khỏe - Tâm lý"}
NX = {m: f"{m}_NX" for m in MUC}
TEN_NX = {m: f"Nhận xét {TEN_MUC[m].lower()}" for m in MUC}
# Mục chỉ viết lời
LOI = ("DiemSang", "TraoDoi", "DinhHuong")
TEN_LOI = {"DiemSang": "Điểm sáng trong tháng", "TraoDoi": "Quá trình trao đổi và hỗ trợ",
           "DinhHuong": "Định hướng giáo dục"}
COT_MUC = [TEN_MUC[m] for m in MUC]
COT_BANG = (["Ngày", "PhongID", "Phòng", "HocSinhID", "Học sinh", "Lớp"]
            + [c for m in MUC for c in (TEN_MUC[m], TEN_NX[m])]
            + [TEN_LOI[k] for k in LOI] + ["Người đánh giá"])
COT_LOI = [TEN_NX[m] for m in MUC] + [TEN_LOI[k] for k in LOI]
MAX_LOI = 300  # ký tự mỗi ô lời nhận xét (cả phòng lưu trong 1 ô SharePoint ~63.000 ký tự)
CU = {"HocTap": "HocBaiToi"}  # dữ liệu cũ (2 mục Nề nếp + Học bài tối)
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

    `dong`: [{"id", "ten", "lop", <mục>: mức, <mục>_NX: lời, DiemSang / TraoDoi / DinhHuong}]"""
    if not dong:
        raise ValueError("Phòng chưa có học sinh nào để đánh giá.")
    sach = []
    for d in dong:
        x = {"id": _s(d.get("id")), "ten": _s(d.get("ten")), "lop": _s(d.get("lop"))}
        for m in MUC:
            v = _s(d.get(m)) or _s(d.get(CU.get(m, ""))) or "Tốt"
            if v not in MUC_DANH_GIA:
                raise ValueError(f"Mức đánh giá không hợp lệ: {v}")
            x[m] = v
        for k in [NX[m] for m in MUC] + list(LOI):
            v = _s(d.get(k))
            if len(v) > MAX_LOI:
                raise ValueError(f"Nhận xét của {x['ten'] or 'một học sinh'} quá dài "
                                 f"({len(v)} ký tự, tối đa {MAX_LOI}).")
            if v:
                x[k] = v
        sach.append(x)
    du_lieu = json.dumps(sach, ensure_ascii=False, separators=(",", ":"))
    if len(du_lieu) > 60000:
        raise ValueError("Nhận xét của cả phòng quá dài để lưu một lần — rút gọn bớt lời nhận xét.")
    data = {"NamHoc": nam_hoc, "Ngay": ngay.isoformat(), "PhongID": _s(phong.get("id")),
            "Phong": _s(phong.get("TenPhong")), "NguoiDanhGia": _s(nguoi),
            "DuLieu": du_lieu,
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
            row = {"Ngày": ngay, "PhongID": _s(r.get("PhongID")), "Phòng": _s(r.get("Phong")),
                   "HocSinhID": _s(d.get("id")), "Học sinh": _s(d.get("ten")),
                   "Lớp": _s(d.get("lop"))}
            for m in MUC:
                row[TEN_MUC[m]] = _s(d.get(m)) or _s(d.get(CU.get(m, "")))
                row[TEN_NX[m]] = _s(d.get(NX[m]))
            if not row[TEN_NX["NeNep"]]:  # dữ liệu cũ: một ô "Ghi chú" chung
                row[TEN_NX["NeNep"]] = _s(d.get("GhiChu"))
            for k in LOI:
                row[TEN_LOI[k]] = _s(d.get(k))
            row["Người đánh giá"] = _s(r.get("NguoiDanhGia"))
            rows.append(row)
    return pd.DataFrame(rows, columns=COT_BANG)


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
    """Theo phòng: số ngày đã/chưa nhập, tỷ lệ Tốt và số lượt cần chú ý của từng mục."""
    out = []
    for p in phongs:
        x = long[long["PhongID"] == str(p.get("id"))]
        x = x[x["Ngày"].isin(ngays)] if ngays else x.iloc[0:0]
        da = x["Ngày"].nunique()
        r = {"Phòng": _s(p.get("TenPhong")), "Khu": _s(p.get("Khu")),
             "Giáo viên": _s(p.get("GiaoVien")), "Số HS": len(hs_ids(p)),
             "Ngày đã nhập": da, "Ngày chưa nhập": max(len(ngays) - da, 0)}
        for c in COT_MUC:
            r[f"{c} Tốt (%)"] = _ty_le_tot(x[c])
        for c in COT_MUC:
            r[f"Lượt {c.lower()} TB/CT"] = int(x[c].isin(CAN_CHU_Y).sum())
        out.append(r)
    return pd.DataFrame(out)


def _gan_nhat(s: pd.Series) -> str:
    return next((v for v in reversed(s.tolist()) if v), "")


def hoc_sinh_can_chu_y(long: pd.DataFrame, toi_thieu: int = 2) -> pd.DataFrame:
    """Học sinh có từ `toi_thieu` lượt Trung bình / Chưa tốt (cộng các mục) trong khoảng lọc."""
    cot_ct = [f"{c} TB/CT" for c in COT_MUC]
    cols = (["Học sinh", "Lớp", "Phòng", "Số ngày"] + cot_ct
            + ["Tổng lượt", "Điểm TB", "Nhận xét gần nhất"])
    if long.empty:
        return pd.DataFrame(columns=cols)
    x = long.assign(**{f"_ct{i}": long[c].isin(CAN_CHU_Y) for i, c in enumerate(COT_MUC)},
                    _d=sum(long[c].map(DIEM) for c in COT_MUC) / len(COT_MUC),
                    _nx=long[[TEN_NX[m] for m in MUC]].apply(
                        lambda r: " · ".join(v for v in r if v), axis=1))
    g = x.sort_values("Ngày").groupby("HocSinhID").agg(**{
        "Học sinh": ("Học sinh", "last"), "Lớp": ("Lớp", "last"), "Phòng": ("Phòng", "last"),
        "Số ngày": ("Ngày", "nunique"),
        **{cot_ct[i]: (f"_ct{i}", "sum") for i in range(len(COT_MUC))},
        "Điểm TB": ("_d", "mean"), "Nhận xét gần nhất": ("_nx", _gan_nhat)})
    g["Tổng lượt"] = g[cot_ct].sum(axis=1)
    g["Điểm TB"] = g["Điểm TB"].round(2)
    g = g[g["Tổng lượt"] >= toi_thieu].sort_values(["Tổng lượt", "Điểm TB"],
                                                   ascending=[False, True])
    return g[cols].reset_index(drop=True)


def nhan_xet(long: pd.DataFrame) -> pd.DataFrame:
    """Các dòng có lời nhận xét (để đọc nhanh): mỗi học sinh-ngày một dòng."""
    if long.empty:
        return long[["Ngày", "Phòng", "Học sinh", "Lớp"] + COT_LOI]
    co = long[COT_LOI].ne("").any(axis=1)
    return long.loc[co, ["Ngày", "Phòng", "Học sinh", "Lớp"] + COT_LOI]


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
    """Tỷ lệ Tốt của từng mục theo ngày (toàn khu nội trú)."""
    if long.empty:
        return pd.DataFrame(columns=["Ngày", "Mục", "Tỷ lệ Tốt (%)"])
    g = long.groupby("Ngày").agg(**{c: (c, _ty_le_tot) for c in COT_MUC}).reset_index()
    return g.melt("Ngày", COT_MUC, var_name="Mục", value_name="Tỷ lệ Tốt (%)")


def phan_bo_muc(long: pd.DataFrame) -> pd.DataFrame:
    """Số lượt từng mức của từng mục."""
    rows = []
    for col in COT_MUC:
        vc = long[col].value_counts()
        for m in MUC_DANH_GIA:
            rows.append({"Mục": col, "Mức": m, "Số lượt": int(vc.get(m, 0))})
    return pd.DataFrame(rows)
