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
    if tk.get("id") and str(phong.get("GiaoVienID") or "") == str(tk["id"]):
        return True
    # phòng nhập từ Excel trước khi giáo viên có tài khoản: khớp theo họ tên
    from .danh_muc import fold
    return (not _s(phong.get("GiaoVienID")) and bool(_s(phong.get("GiaoVien")))
            and fold(phong.get("GiaoVien")) == fold(tk.get("HoTen")))


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


def bo_khoi_phong(storage: Storage, phongs: list[dict], hoc_sinh: list[str]) -> int:
    """Bỏ các học sinh khỏi mọi phòng đang chứa các em."""
    bo, n = {str(i) for i in hoc_sinh}, 0
    for p in phongs:
        con = [i for i in hs_ids(p) if i not in bo]
        if len(con) != len(hs_ids(p)):
            storage.update_item(NOI_TRU_PHONG.name, p["id"], {"HocSinhIDs": ";".join(con)})
            n += 1
    return n


def them_vao_phong(storage: Storage, phongs: list[dict], nam_hoc: str, phong: dict | None,
                   ten_moi: str, hoc_sinh: list[str]) -> dict:
    """Xếp thêm học sinh vào phòng có sẵn (giữ giáo viên, học sinh cũ) hoặc phòng mới."""
    if not hoc_sinh:
        raise ValueError("Chưa chọn học sinh nào.")
    if not phong:
        return luu_phong(storage, phongs, nam_hoc, ten_moi, "", None, hoc_sinh)
    gv = {"id": _s(phong.get("GiaoVienID")), "HoTen": _s(phong.get("GiaoVien"))}
    return luu_phong(storage, phongs, nam_hoc, _s(phong.get("TenPhong")), _s(phong.get("Khu")),
                     gv, hs_ids(phong) + [i for i in hoc_sinh if i not in hs_ids(phong)],
                     _s(phong.get("GhiChu")), phong.get("id"))


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


def nhap_danh_gia(storage: Storage, df: pd.DataFrame, phongs_all: list[dict],
                  danh_gia: list[dict], nam_hoc: str, nh: list[dict], nguoi: str,
                  progress=None) -> dict:
    """Nhập đánh giá từ file mẫu (mỗi dòng = 1 học sinh trong 1 ngày; cột theo key: Ngay,
    Phong, HoTen, Lop, <mục>, <mục>_NX, DiemSang / TraoDoi / DinhHuong, NguoiDanhGia).

    Học sinh tìm trong phòng của năm học theo họ tên (trùng tên thì xét lớp). Phòng + ngày đã
    có bản ghi: em có trong file được cập nhật, em khác giữ nguyên."""
    from .danh_muc import fold

    phongs = {_s(p.get("TenPhong")).lower(): p for p in phong_nam(phongs_all, nam_hoc)}
    hs = {str(r.get("id")): r for r in nh}
    loi, nhom = [], {}
    for i, row in df.iterrows():
        d = {k: _s(v) for k, v in row.to_dict().items()}
        dong = i + 2
        ngay = _ngay(d.get("Ngay"))
        p = phongs.get(d.get("Phong", "").lower().removeprefix("phòng ").strip())
        if ngay is None:
            loi.append({"Dòng": dong, "Lỗi": f"Ngày không hợp lệ: \"{d.get('Ngay', '')}\""})
            continue
        if p is None:
            loi.append({"Dòng": dong, "Lỗi": f"Không có phòng \"{d.get('Phong', '')}\" trong "
                                             f"năm học {nam_hoc}"})
            continue
        ung = [x for x in hs_ids(p) if fold((hs.get(x) or {}).get("HoTen")) == fold(d.get("HoTen"))]
        if len(ung) > 1 and d.get("Lop"):
            ung = [x for x in ung if _chuan_lop(hs[x].get("LopHoc")) == _chuan_lop(d["Lop"])] or ung
        if len(ung) != 1:
            loi.append({"Dòng": dong, "Lỗi": (f"Phòng {p.get('TenPhong')} có {len(ung)} em tên "
                                              f"\"{d.get('HoTen')}\" — ghi thêm lớp") if ung else
                        f"Không thấy \"{d.get('HoTen', '')}\" trong phòng {p.get('TenPhong')}"})
            continue
        sai = [d[m] for m in MUC if d.get(m) and d[m] not in MUC_DANH_GIA]
        if sai:
            loi.append({"Dòng": dong, "Lỗi": f"Mức không hợp lệ: {sai[0]} (chọn: "
                                             f"{', '.join(MUC_DANH_GIA)})"})
            continue
        dai = [k for k in [NX[m] for m in MUC] + list(LOI) if len(d.get(k, "")) > MAX_LOI]
        if dai:
            loi.append({"Dòng": dong, "Lỗi": f"Nhận xét quá dài (tối đa {MAX_LOI} ký tự)"})
            continue
        r = hs[ung[0]]
        x = {"id": ung[0], "ten": _s(r.get("HoTen")), "lop": _s(r.get("LopHoc"))}
        x.update({k: d[k] for k in list(MUC) + [NX[m] for m in MUC] + list(LOI) if d.get(k)})
        g = nhom.setdefault((str(p["id"]), ngay), {"phong": p, "dong": {}, "nguoi": "",
                                                   "so_dong": []})
        g["dong"][ung[0]] = x
        g["nguoi"] = g["nguoi"] or d.get("NguoiDanhGia", "")
        g["so_dong"].append(dong)
    danh_gia = list(danh_gia)
    ok, done = 0, 0
    for (_, ngay), g in nhom.items():
        cu = tim_ban_ghi(danh_gia, g["phong"]["id"], ngay)
        gop = {str(x.get("id")): x for x in (doc_du_lieu(cu) if cu else [])}
        for i, x in g["dong"].items():
            gop[i] = {**gop.get(i, {}), **x}
        try:
            luu_danh_gia(storage, danh_gia, nam_hoc, ngay, g["phong"], list(gop.values()),
                         g["nguoi"] or (cu or {}).get("NguoiDanhGia") or nguoi)
            ok += len(g["dong"])
        except Exception as e:
            loi += [{"Dòng": n, "Lỗi": str(e)[:300]} for n in g["so_dong"]]
        done += 1
        if progress:
            progress(done, len(nhom))
    return {"ok": ok, "ban_ghi": len(nhom), "errors": sorted(loi, key=lambda e: e["Dòng"]),
            "total": len(df)}


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


# ------------------------------------------------------------------ nhập phân phòng từ Excel
TT_KHOP, TT_KHONG_THAY, TT_TRUNG = "Khớp", "Không tìm thấy", "Trùng tên, chưa rõ em nào"


def _chuan_lop(v) -> str:
    """9.3 / "9,3" / "10A1ESL" / "10A1E" -> dạng so khớp: "9.3", "10A1" (bỏ đuôi E/ESL)."""
    import re
    if v is None or (isinstance(v, float) and v != v):
        return ""
    t = (f"{v:g}" if isinstance(v, float) else str(v)).strip().upper().replace(",", ".")
    t = re.sub(r"\s+", "", t)
    return re.sub(r"(ESL|E|IEP)$", "", t)


def _khoi_lop(lop: str) -> str:
    import re
    m = re.match(r"^(\d{1,2})", lop or "")
    return m.group(1) if m else ""


def _tim_cot(nhan: list[str]) -> dict | None:
    def tim(*dk):
        for f in dk:
            j = next((j for j, v in enumerate(nhan) if v and f(v)), None)
            if j is not None:
                return j
        return None
    c = {"ten": tim(lambda v: v in ("ho va ten", "ho ten", "ho ten hs")),
         "phong": tim(lambda v: v.startswith("phong") and ("nt" in v.split() or "noi tru" in v),
                      lambda v: v.startswith("phong") and "hoc" not in v),
         "lop": tim(lambda v: v == "lop", lambda v: v == "lop moi"),
         "gt": tim(lambda v: v.startswith("gioi tinh")),
         "gv": tim(lambda v: v.startswith("qn") or "quan ly" in v or "quan nhiem" in v,
                   lambda v: v.startswith("giao vien"))}
    return c if c["ten"] is not None and c["phong"] is not None else None


def sheet_phong(src) -> list[str]:
    """Các sheet có cột Họ và tên + Phòng (nội trú), sheet đầy đủ cột nhất đứng trước."""
    import openpyxl
    from .danh_muc import fold

    wb = openpyxl.load_workbook(src, data_only=True, read_only=True)
    ds = []
    for ws in wb.worksheets:
        for r in ws.iter_rows(min_row=1, max_row=12, values_only=True):
            c = _tim_cot([fold(v).replace("\n", " ") if v is not None else "" for v in r])
            if c:
                ds.append((-sum(v is not None for v in c.values()), len(ds), ws.title))
                break
    wb.close()
    return [t for *_, t in sorted(ds)]


def doc_ds_phong(src, sheet: str | None = None) -> tuple[pd.DataFrame, str]:
    """Đọc danh sách nội trú: cột Họ và tên, Lớp, Giới tính, Phòng (NT), Giáo viên quản lý.

    Trả về (bảng: Họ tên, Lớp, Giới tính, Phòng, Giáo viên; tên sheet đã đọc)."""
    import openpyxl
    from .danh_muc import fold

    ds = sheet_phong(src)
    if not ds:
        raise ValueError("Không tìm thấy sheet có cột \"Họ và tên\" và cột \"Phòng\".")
    sheet = sheet if sheet in ds else ds[0]
    if hasattr(src, "seek"):
        src.seek(0)
    wb = openpyxl.load_workbook(src, data_only=True, read_only=True)
    ws = wb[sheet]
    c, tieu_de = None, 0
    for i, r in enumerate(ws.iter_rows(min_row=1, max_row=12, values_only=True), 1):
        c = _tim_cot([fold(v).replace("\n", " ") if v is not None else "" for v in r])
        if c:
            tieu_de = i
            break
    out = []
    for r in ws.iter_rows(min_row=tieu_de + 1, values_only=True):
        def lay(k):
            j = c[k]
            return r[j] if j is not None and j < len(r) else None
        ten = _s(lay("ten"))
        phong = lay("phong")
        phong = f"{phong:g}" if isinstance(phong, float) else _s(phong)
        if not ten or not phong:  # chỉ lấy học sinh có phòng nội trú
            continue
        out.append({"Họ tên": " ".join(ten.split()), "Lớp": _chuan_lop(lay("lop")),
                    "Giới tính": _s(lay("gt")), "Phòng": phong,
                    "Giáo viên": " ".join(_s(lay("gv")).split())})
    wb.close()
    return pd.DataFrame(out, columns=["Họ tên", "Lớp", "Giới tính", "Phòng", "Giáo viên"]), sheet


def ghep_hs(ds: pd.DataFrame, nh: list[dict], nam_hoc: str) -> pd.DataFrame:
    """Ghép từng dòng danh sách với hồ sơ nhập học của năm: theo họ tên, rồi khối / lớp /
    giới tính khi trùng tên. Thêm cột Kết quả, HocSinhID, Lớp (app), Chế độ (app)."""
    from .danh_muc import fold

    ung = [r for r in nh if _s(r.get("NamHoc")) == nam_hoc
           and _s(r.get("TinhTrangHS")) not in ("Rút hồ sơ", "Không học tiếp")]
    theo_ten: dict[str, list[dict]] = {}
    for r in ung:
        theo_ten.setdefault(fold(r.get("HoTen")), []).append(r)
    kq = []
    for _, d in ds.iterrows():
        cands = theo_ten.get(fold(d["Họ tên"]), [])
        lop, khoi = d["Lớp"], _khoi_lop(d["Lớp"])
        for loc in (
                lambda c: _chuan_lop(c.get("LopHoc")) == lop and lop,
                lambda c: (_s(c.get("Khoi")) == khoi or _khoi_lop(_chuan_lop(c.get("LopHoc")))
                           == khoi) and khoi,
                lambda c: fold(c.get("GioiTinh")) == fold(d["Giới tính"]) and d["Giới tính"]):
            if len(cands) > 1:
                hep = [c for c in cands if loc(c)]
                cands = hep or cands
        if len(cands) == 1:
            c = cands[0]
            kq.append((TT_KHOP, str(c["id"]), _s(c.get("LopHoc")) or _s(c.get("Khoi")),
                       _s(c.get("NoiTruBanTru"))))
        else:
            kq.append((TT_TRUNG if cands else TT_KHONG_THAY, "", "", ""))
    out = ds.copy()
    out["Kết quả"] = [k[0] for k in kq]
    out["HocSinhID"] = [k[1] for k in kq]
    out["Lớp (app)"] = [k[2] for k in kq]
    out["Chế độ (app)"] = [k[3] for k in kq]
    # một hồ sơ bị ghép cho 2 dòng -> không chắc, bỏ ghép
    trung_id = out["HocSinhID"][out["HocSinhID"] != ""].duplicated(keep=False)
    for i in trung_id[trung_id].index:
        out.loc[i, ["Kết quả", "HocSinhID"]] = [TT_TRUNG, ""]
    return out


def ke_hoach_phong(ghep: pd.DataFrame, tks: list[dict]) -> list[dict]:
    """Mỗi phòng: tên, giáo viên (nhiều tên thì lấy tên xuất hiện nhiều nhất), tài khoản khớp
    theo họ tên, danh sách HocSinhID đã ghép."""
    from .danh_muc import fold

    theo_ten = {fold(t.get("HoTen")): t for t in tks if _s(t.get("HoTen"))}
    out = []
    for phong, g in ghep.groupby("Phòng", sort=False):
        if not _s(phong):
            continue
        gv_ds = g["Giáo viên"][g["Giáo viên"] != ""]
        gv = gv_ds.value_counts().index[0] if len(gv_ds) else ""
        out.append({"TenPhong": _s(phong), "GiaoVien": gv, "TaiKhoan": theo_ten.get(fold(gv)),
                    "NhieuGV": sorted(set(gv_ds)) if gv_ds.nunique() > 1 else [],
                    "HocSinhIDs": [i for i in g["HocSinhID"] if i]})
    return sorted(out, key=lambda x: _so_tu_nhien(x["TenPhong"]))


def ap_dung_phan_phong(storage: Storage, phongs_all: list[dict], nam_hoc: str,
                       ghep: pd.DataFrame, ke_hoach: list[dict], nh_name: str,
                       progress=None) -> dict:
    """Ghi lên SharePoint: hồ sơ ghép được -> "Nội trú"; tạo / cập nhật phòng theo file (học
    sinh của phòng = theo file); em có trong file bị bỏ khỏi phòng khác của năm."""
    from concurrent.futures import ThreadPoolExecutor

    doi_che_do = ghep[(ghep["HocSinhID"] != "")
                      & ~ghep["Chế độ (app)"].str.startswith("Nội trú")]["HocSinhID"].tolist()
    cung_nam = [p for p in phongs_all if _s(p.get("NamHoc")) == nam_hoc]
    theo_ten = {_s(p.get("TenPhong")).lower(): p for p in cung_nam}
    trong_file = {i for k in ke_hoach for i in k["HocSinhIDs"]}
    viec = [("nh", i) for i in doi_che_do]
    phong_file = set()
    for k in ke_hoach:
        cu = theo_ten.get(k["TenPhong"].lower())
        phong_file.add(k["TenPhong"].lower())
        tk = k["TaiKhoan"] or {}
        data = {"NamHoc": nam_hoc, "TenPhong": k["TenPhong"],
                "GiaoVienID": _s(tk.get("id")), "GiaoVien": _s(tk.get("HoTen")) or k["GiaoVien"],
                "HocSinhIDs": ";".join(dict.fromkeys(k["HocSinhIDs"]))}
        if cu:
            data["Khu"] = _s(cu.get("Khu"))
        viec.append(("phong", (cu.get("id") if cu else None, data)))
    for p in cung_nam:  # bỏ học sinh có trong file khỏi các phòng khác
        if _s(p.get("TenPhong")).lower() in phong_file:
            continue
        con = [i for i in hs_ids(p) if i not in trong_file]
        if len(con) != len(hs_ids(p)):
            viec.append(("phong", (p["id"], {"HocSinhIDs": ";".join(con)})))

    def lam(v):
        loai, x = v
        if loai == "nh":
            return storage.update_item(nh_name, x, {"NoiTruBanTru": "Nội trú"})
        item_id, data = x
        if item_id:
            return storage.update_item(NOI_TRU_PHONG.name, item_id, data)
        return storage.create_item(NOI_TRU_PHONG.name, data)

    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for _ in pool.map(lam, viec):
            done += 1
            if progress:
                progress(done, len(viec))
    return {"doi_che_do": len(doi_che_do), "phong": len(ke_hoach),
            "xep": len(trong_file), "viec": len(viec)}
