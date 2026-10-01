"""Thực hiện "ý định" có cấu trúc (do Gemini đọc từ câu hỏi) trên dữ liệu trong app.

Ý định là một dict, mọi khóa đều tùy chọn trừ "loai":
  loai        dem | danh_sach | thong_ke | xep_hang | ty_le | tong_quan | tra_cuu |
              giay_to | tai_chinh | qua_han
  doi_tuong   lien_he | tu_van | nop_ho_so | nhap_hoc | rut_ho_so | chua_nhap_hoc
  khoi, he, che_do, nguon, tinh, phuong_xa, truong_cu, nguoi_nhan, giu_cho, tinh_trang,
  phu_huynh   danh sách giá trị (nhiều giá trị = HOẶC; các khóa khác nhau = VÀ)
  gioi_tinh   "Nam" | "Nữ";   ten / ho / ten_chua: lọc theo họ tên học sinh
  tu_ngay, den_ngay (YYYY-MM-DD, theo ngày liên hệ); nam_hoc: danh sách; so_sanh_nam: bool;
  so_nam: số năm gần nhất khi so sánh (mặc định 2)
  theo        trục thống kê (khoi, nguon, thang, tuan, buoc, che_do, gioi_tinh, truong_cu, tinh,
              phuong_xa, nguoi_nhan, giu_cho, he, tinh_trang)
  thu_tu      nhieu | it;  top: số dòng;  ty_le_cua: nhap_hoc | nop_ho_so | rut_ho_so
  tim         họ tên / SĐT (tra cứu);  so_ngay: quá hạn;  tai_chinh: tong | chua_giu_cho |
              hoan_phi | con_no
Dữ liệu học sinh không rời khỏi app: Gemini chỉ đọc câu hỏi để tạo ý định.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from . import tro_ly as T
from .schema import TRANG_THAI

TRUC = {  # khóa -> (cột, tên hiển thị, gộp cách viết)
    "khoi": ("Khoi", "Khối", False), "nguon": ("Nguon", "Nguồn", False),
    "buoc": ("TrangThai", "Bước", False), "che_do": ("CheDo", "Chế độ", False),
    "gioi_tinh": ("GioiTinh", "Giới tính", False), "truong_cu": ("TruongCu", "Trường cũ", True),
    "tinh": ("TruongCu_Tinh", "Tỉnh/thành", True),
    "phuong_xa": ("TruongCu_PhuongXa", "Phường/xã", True),
    "nguoi_nhan": ("NguoiNhanHoSo", "Người nhận hồ sơ", True),
    "giu_cho": ("GiuCho", "Giữ chỗ", False), "he": ("PhanHe", "Hệ", False),
    "tinh_trang": ("TinhTrang", "Tình trạng", False),
}
THOI_GIAN = {"thang": ("Tháng", "%Y-%m"), "tuan": ("Tuần", "%G-T%V"), "ngay": ("Ngày", "%Y-%m-%d")}
DOI_TUONG = {"lien_he": (None, "liên hệ"), "tu_van": ("Tư vấn", "liên hệ đang tư vấn"),
             "nop_ho_so": ("Nộp hồ sơ", "học sinh đã nộp hồ sơ (gồm nhập học)"),
             "nhap_hoc": ("Nhập học", "học sinh nhập học"),
             "rut_ho_so": ("Rút hồ sơ", "học sinh rút hồ sơ"),
             "chua_nhap_hoc": ("CHUA_NH", "liên hệ chưa nhập học")}
# khóa lọc danh sách -> (cột, kiểu so khớp, nhãn hiển thị)
LOC_DS = {
    "nguon": ("Nguon", "chua", "nguồn"), "tinh": ("TruongCu_Tinh", "chua", "tỉnh"),
    "phuong_xa": ("TruongCu_PhuongXa", "chua", "phường/xã"), "truong_cu": ("TruongCu", "chua", "trường"),
    "nguoi_nhan": ("NguoiNhanHoSo", "chua", "người nhận"), "giu_cho": ("GiuCho", "chua", ""),
    "tinh_trang": ("TinhTrang", "chua", "tình trạng"), "che_do": ("CheDo", "chua", ""),
    "phu_huynh": ("TenLienHe", "chua", "phụ huynh"),
}
_TIEN_TO = re.compile(r"^(?:thanh pho|tinh|tp|phuong|xa|thi tran|truong|trung hoc co so|"
                      r"trung hoc pho thong|tieu hoc|thcs|thpt|th)\s+")


def _ds(v) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]


def _loi(s: str) -> str:
    """Phần lõi để so khớp tên địa danh / trường ("Trường THCS Phước Thái" -> "phuoc thai")."""
    k = T.kd(s)
    while (m := _TIEN_TO.sub("", k)) != k:
        k = m
    return k


def _ngay(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def loc(df: pd.DataFrame, yd: dict) -> pd.DataFrame:
    """Áp mọi bộ lọc của ý định (các khóa = VÀ; nhiều giá trị trong một khóa = HOẶC)."""
    if df.empty:
        return df
    m = pd.Series(True, index=df.index)
    if khoi := _ds(yd.get("khoi")):
        k = T._col(df, "Khoi").str.split(".").str[0].str.strip()
        he_k = {x.split("-")[0].strip(): x.split("-")[1].strip().upper()
                for x in khoi if "-" in x}
        so = [re.sub(r"\D", "", x.split("-")[0]) for x in khoi]
        m &= k.isin([x for x in so if x])
        if he_k:  # "10-IEP"
            ph = T._col(df, "PhanHe").str.upper()
            m &= pd.Series([he_k.get(a) in (None, b) for a, b in zip(k, ph)], index=df.index)
    if he := [x.upper() for x in _ds(yd.get("he"))]:
        m &= T._col(df, "PhanHe").str.upper().isin(he)
    if gt := str(yd.get("gioi_tinh") or "").strip():
        m &= T._col(df, "GioiTinh").map(T.kd) == T.kd(gt)
    for khoa, (cot, _, _) in LOC_DS.items():
        gia_tri = [_loi(x) for x in _ds(yd.get(khoa))]
        gia_tri = [g for g in gia_tri if g]
        if gia_tri and cot in df:
            cot_kd = T._col(df, cot).map(_loi)
            m &= cot_kd.map(lambda v: any(g in v or (v and v in g) for g in gia_tri))
    cot_ten = "HoTenHS" if "HoTenHS" in df else "HoTen"
    chu = T._col(df, cot_ten).map(T.kd).str.split()
    if ten := T.kd(yd.get("ten") or ""):
        n = len(ten.split())
        m &= chu.map(lambda w: " ".join(w[-n:]) == ten if w else False)
    if ho := T.kd(yd.get("ho") or ""):
        n = len(ho.split())
        m &= chu.map(lambda w: " ".join(w[:n]) == ho if w else False)
    if tc := T.kd(yd.get("ten_chua") or ""):
        m &= chu.map(lambda w: f" {tc} " in f" {' '.join(w)} ")
    tu, den = _ngay(yd.get("tu_ngay")), _ngay(yd.get("den_ngay"))
    if (tu or den) and "NgayLienHe" in df:
        d = T._ngay(df["NgayLienHe"])
        if tu:
            m &= d.map(lambda x: pd.notna(x) and x >= tu)
        if den:
            m &= d.map(lambda x: pd.notna(x) and x <= den)
    out = df[m]
    buoc = DOI_TUONG.get(yd.get("doi_tuong") or "lien_he", (None, ""))[0]
    return T.loc_buoc(out, buoc) if buoc else out


def mo_ta(yd: dict) -> str:
    p = []
    if k := _ds(yd.get("khoi")):
        p.append("khối " + ", ".join(k))
    if h := _ds(yd.get("he")):
        p.append("hệ " + "/".join(x.upper() for x in h))
    if g := yd.get("gioi_tinh"):
        p.append(f"học sinh {str(g).lower()}")
    for khoa, (_, _, nhan) in LOC_DS.items():
        if v := _ds(yd.get(khoa)):
            p.append((f"{nhan} " if nhan else "") + " hoặc ".join(v))
    if yd.get("ten"):
        p.append(f"tên {yd['ten']}")
    if yd.get("ho"):
        p.append(f"họ {yd['ho']}")
    if yd.get("ten_chua"):
        p.append(f"tên có chữ {yd['ten_chua']}")
    tu, den = _ngay(yd.get("tu_ngay")), _ngay(yd.get("den_ngay"))
    if tu and den:
        p.append(f"từ {tu:%d/%m/%Y} đến {den:%d/%m/%Y}" if tu != den else f"ngày {tu:%d/%m/%Y}")
    elif tu:
        p.append(f"từ {tu:%d/%m/%Y}")
    elif den:
        p.append(f"đến {den:%d/%m/%Y}")
    return ", ".join(p)


def _bang_truc(df: pd.DataFrame, truc: str) -> tuple[pd.DataFrame, str, bool]:
    """(bảng nhãn | Số lượng, tên trục, có thứ tự cố định)."""
    if truc in THOI_GIAN:
        ten, fmt = THOI_GIAN[truc]
        vc = pd.to_datetime(T._col(df, "NgayLienHe"), errors="coerce").dt.strftime(fmt) \
            .fillna("~").value_counts().sort_index()
        vc.index = [("(không có ngày)" if k == "~" else f"{k[5:]}/{k[:4]}" if truc == "thang"
                     else k) for k in vc.index]
        return vc.rename_axis(ten).reset_index(name="Số lượng"), ten, True
    cot, ten, gop = TRUC[truc]
    b = T._dem_gop(T._col(df, cot), ten) if gop else \
        T._dem(T._col(df, cot), ten, TRANG_THAI if truc == "buoc" else None)
    if truc == "khoi":
        b = b.sort_values(ten, key=lambda s: s.map(T._khoi_key)).reset_index(drop=True)
    return b, ten, truc in ("khoi", "buoc")


def _doi_ky(yd: dict, nam: str, goc: str) -> dict:
    lech = int(nam[:4]) - int(goc[:4])
    out = dict(yd)
    for k in ("tu_ngay", "den_ngay"):
        if d := _ngay(yd.get(k)):
            try:
                out[k] = d.replace(year=d.year + lech).isoformat()
            except ValueError:
                out[k] = d.replace(year=d.year + lech, day=28).isoformat()
    return out


def _nam(yd: dict, c: T.Ctx) -> tuple[list[str], bool]:
    ds = c.cac_nam()
    nams = [n for n in _ds(yd.get("nam_hoc")) if n in ds]
    i = ds.index(c.nam_hoc) if c.nam_hoc in ds else len(ds) - 1
    if yd.get("so_sanh_nam") and len(nams) < 2:
        goc = nams[-1] if nams else c.nam_hoc
        j = ds.index(goc) if goc in ds else i
        so_nam = max(2, min(int(yd.get("so_nam") or 2), 5))
        nams = ds[max(0, j - so_nam + 1):j + 1]
    return (nams or [c.nam_hoc]), len(nams) >= 2


def thuc_hien(yd: dict, c: T.Ctx) -> T.TraLoi:
    loai = str(yd.get("loai") or "dem")
    dt = DOI_TUONG.get(yd.get("doi_tuong") or "lien_he", DOI_TUONG["lien_he"])
    ten_tap = dt[1]
    Tap = ten_tap[0].upper() + ten_tap[1:]
    nams, nhieu = _nam(yd, c)
    pv_txt = mo_ta(yd)
    pv = f" ({pv_txt})" if pv_txt else ""

    # các loại chuyên biệt: dùng lại bộ máy hiện có với bộ lọc đơn giản
    if loai in ("tong_quan", "giay_to", "tai_chinh", "qua_han", "tra_cuu"):
        cy = c.nam(nams[-1])
        lc = T.Loc(khoi=(_ds(yd.get("khoi")) or [None])[0], gioi_tinh=yd.get("gioi_tinh"))
        if loai == "tra_cuu":
            return T.tra_cuu(cy, str(yd.get("tim") or ""))
        if loai == "giay_to":
            return T.giay_to(cy, lc)
        if loai == "qua_han":
            return T.tu_van_cu(cy, f"{int(yd.get('so_ngay') or 14)} ngay", lc)
        if loai == "tai_chinh":
            q = {"chua_giu_cho": "chua giu cho", "hoan_phi": "hoan phi",
                 "con_no": "con no"}.get(str(yd.get("tai_chinh") or ""), "tong")
            return T.tai_chinh(cy, q, lc)
        sub = T.Ctx(loc(cy.ts, {**yd, "doi_tuong": "lien_he"}), cy.nh, cy.nam_hoc, cy.quyen,
                    cy.hom_nay, cy.ts_all, cy.nh_all)
        r = T.tong_quan(sub, T.Loc())
        if pv_txt:
            r.text = r.text.replace("**:", f"** ({pv_txt}):", 1)
        return r

    if not c.duoc("Data tuyển sinh", "Báo cáo", "Tổng quan", "Hồ sơ nhập học", "Kế toán"):
        return T.TraLoi("Tài khoản của bạn không được xem số liệu tuyển sinh.")
    truc = str(yd.get("theo") or "")
    truc = truc if truc in TRUC or truc in THOI_GIAN else ""
    if loai in ("thong_ke", "xep_hang") and not truc:
        truc = "khoi"

    # ---- nhiều năm học
    if nhieu:
        if loai == "ty_le":
            rows = []
            for y in nams:
                d = loc(c.nam(y).ts, {**_doi_ky(yd, y, c.nam_hoc), "doi_tuong": "lien_he"})
                n = len(_tu_so(d, yd))
                rows.append({"Năm học": y, "Liên hệ": len(d), "Đạt": n,
                             "Tỷ lệ (%)": round(100 * n / len(d), 1) if len(d) else 0.0})
            b = pd.DataFrame(rows)
            return T.TraLoi(f"Tỷ lệ {_ten_ty_le(yd)}{pv}: " + " → ".join(
                f"{r['Năm học']}: **{T._pt(r['Tỷ lệ (%)'])}**" for r in rows) + ".", table=b,
                chart=b[["Năm học", "Tỷ lệ (%)"]].rename(columns={"Tỷ lệ (%)": "Số lượng"}))
        dfs = {y: loc(c.nam(y).ts, _doi_ky(yd, y, c.nam_hoc)) for y in nams}
        if truc:
            cols = {}
            for y in nams:
                b, ten, _ = _bang_truc(dfs[y], truc)
                cols[y] = b.set_index(ten)["Số lượng"]
            bang = pd.DataFrame(cols).fillna(0).astype(int)
            bang = bang.drop(index=[x for x in ("(trống)", "(không có ngày)") if x in bang.index])
            bang["Tổng"] = bang.sum(axis=1)
            bang = bang.sort_index(key=lambda s: s.map(T._khoi_key)) if truc == "khoi" else \
                bang.sort_values("Tổng", ascending=False)
            bang[f"Tăng/giảm {nams[-1]}"] = [T._tang(a, b) for a, b in
                                            zip(bang[nams[-2]], bang[nams[-1]])]
            bang = bang.rename_axis(ten).reset_index()
            if top := int(yd.get("top") or 0):
                bang = bang.head(top)
            return T.TraLoi(f"{Tap}{pv} theo {ten.lower()} qua {len(nams)} năm học.",
                            table=bang, chart=bang.head(12).melt(ten, nams, var_name="Năm học",
                                                                 value_name="Số lượng"))
        rows = [{"Năm học": y, Tap: len(dfs[y])} for y in nams]
        b = pd.DataFrame(rows)
        b["Tăng/giảm"] = ["—"] + [T._tang(a, x) for a, x in zip(b[Tap][:-1], b[Tap][1:])]
        chuoi = " → ".join(f"{r['Năm học']}: **{r[Tap]}**" + (
            f" ({r['Tăng/giảm']})" if r["Tăng/giảm"] != "—" else "") for _, r in b.iterrows())
        return T.TraLoi(f"{Tap}{pv} qua các năm học: {chuoi}.", table=b,
                        chart=b[["Năm học", Tap]].rename(columns={Tap: "Số lượng"}))

    cy = c.nam(nams[0])
    df = loc(cy.ts, yd)

    if loai == "ty_le":
        goc = loc(cy.ts, {**yd, "doi_tuong": "lien_he"})
        dat = _tu_so(goc, yd)
        text = (f"Tỷ lệ {_ten_ty_le(yd)}{pv} năm học {cy.nam_hoc}: "
                f"**{T._pt(100 * len(dat) / len(goc))}** ({len(dat)}/{len(goc)} liên hệ)."
                if len(goc) else f"Không có liên hệ nào{pv}.")
        if not truc or not len(goc):
            return T.TraLoi(text)
        b_goc, ten, _ = _bang_truc(goc, truc)
        b_dat, _, _ = _bang_truc(dat, truc)
        b = b_goc.rename(columns={"Số lượng": "Liên hệ"}).merge(
            b_dat.rename(columns={"Số lượng": "Đạt"}), on=ten, how="left").fillna(0)
        b["Đạt"] = b["Đạt"].astype(int)
        b["Tỷ lệ (%)"] = (100 * b["Đạt"] / b["Liên hệ"]).round(1)
        du = b[(b["Liên hệ"] >= 5) & (b[ten] != "(trống)")]
        if len(du):
            it = yd.get("thu_tu") == "it"
            t = du.sort_values(["Tỷ lệ (%)", "Liên hệ"], ascending=[it, False]).iloc[0]
            text = (f"{ten} có tỷ lệ {_ten_ty_le(yd)} {'thấp' if it else 'cao'} nhất (từ 5 liên "
                    f"hệ): **{t[ten]}** — {T._pt(t['Tỷ lệ (%)'])} ({t['Đạt']}/{t['Liên hệ']}). "
                    + text)
        b = b.sort_values(["Tỷ lệ (%)", "Liên hệ"], ascending=False).reset_index(drop=True)
        return T.TraLoi(text, table=b, chart=b[[ten, "Tỷ lệ (%)"]].head(15).rename(
            columns={"Tỷ lệ (%)": "Số lượng"}))

    if truc and loai in ("thong_ke", "xep_hang", "dem", "danh_sach"):
        b, ten, co_dinh = _bang_truc(df, truc)
        co = b[~b.iloc[:, 0].isin(["(trống)", "(không có ngày)"])]
        if co.empty:
            return T.TraLoi(f"{Tap}{pv}: **{len(df)}**, chưa có dữ liệu {ten.lower()}.")
        it = yd.get("thu_tu") == "it"
        xep = co.sort_values("Số lượng", ascending=it, kind="stable").reset_index(drop=True)
        if loai == "xep_hang" or yd.get("thu_tu") or yd.get("top"):
            top = int(yd.get("top") or 0)
            dau = xep.iloc[0]
            cung = xep[xep["Số lượng"] == dau["Số lượng"]]
            ds = ", ".join(f"**{x}**" for x in cung.iloc[:, 0].head(5))
            text = (f"{ten} có {'ít' if it else 'nhiều'} {ten_tap} nhất{pv}: {ds} với "
                    f"**{int(dau['Số lượng'])}**. Có {len(xep)} {ten.lower()} khác nhau trên tổng "
                    f"{len(df)} {ten_tap}.")
            bang = xep.copy()
            bang.insert(0, "Hạng", range(1, len(bang) + 1))
            if top:
                bang, xep = bang.head(top), xep.head(top)
            return T.TraLoi(text, table=bang, chart=xep.head(15))
        text = f"{Tap}{pv}: **{len(df)}**, chia theo {ten.lower()} ({len(co)} nhóm)."
        if len(xep) > 1:
            text += f" Nhiều nhất: **{xep.iloc[0, 0]}** ({int(xep.iloc[0]['Số lượng'])})."
        return T.TraLoi(text, table=b if co_dinh else xep, chart=(b if co_dinh else xep).head(15))

    # đếm / danh sách
    text = f"Năm học {cy.nam_hoc}: **{len(df)}** {ten_tap}{pv}."
    if len(df) and not DOI_TUONG.get(yd.get("doi_tuong") or "lien_he")[0]:
        tt = T._col(df, "TrangThai").value_counts()
        text += " Gồm " + ", ".join(f"{b.lower()} {int(tt.get(b, 0))}" for b in TRANG_THAI) + "."
    bang = None
    if (loai == "danh_sach" or 0 < len(df) <= 30) and c.duoc("Data tuyển sinh"):
        bang = T._bang_ts(df, tien=c.duoc("Kế toán"))
        if top := int(yd.get("top") or 0):
            bang = bang.head(top)
    chart = None
    if len(df) and not _ds(yd.get("khoi")):
        chart = T._dem(T._col(df, "Khoi"), "Khối").sort_values(
            "Khối", key=lambda s: s.map(T._khoi_key)).reset_index(drop=True)
    return T.TraLoi(text, table=bang, chart=chart,
                    goi_y=[f"{Tap} theo nguồn", f"{Tap} so với năm trước"])


def _tu_so(df: pd.DataFrame, yd: dict) -> pd.DataFrame:
    return T.loc_buoc(df, {"nop_ho_so": "Nộp hồ sơ", "rut_ho_so": "Rút hồ sơ"}.get(
        str(yd.get("ty_le_cua") or ""), "Nhập học"))


def _ten_ty_le(yd: dict) -> str:
    return {"nop_ho_so": "nộp hồ sơ", "rut_ho_so": "rút hồ sơ"}.get(
        str(yd.get("ty_le_cua") or ""), "nhập học")
