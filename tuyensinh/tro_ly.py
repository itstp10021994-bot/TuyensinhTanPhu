"""Trợ lý dữ liệu: trả lời câu hỏi tiếng Việt về dữ liệu tuyển sinh / nhập học.

Chạy hoàn toàn trong app (không gọi dịch vụ AI bên ngoài -> miễn phí, dữ liệu học sinh không
rời khỏi app). Nhận dạng ý định bằng từ khóa (có dấu hoặc không dấu) + bộ lọc khối, chế độ,
nguồn, thời gian; câu trả lời tôn trọng quyền xem trang của tài khoản.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from . import services
from .schema import CHE_DO, NGUON, TRANG_THAI

VI_DU = (
    "Tổng quan năm học này",
    "Có bao nhiêu học sinh nhập học khối 10?",
    "Liên hệ mới trong tuần này",
    "Thống kê theo nguồn",
    "Học sinh nào còn thiếu giấy tờ khối 6?",
    "Danh sách nộp hồ sơ nhưng chưa giữ chỗ",
    "Tìm Nguyễn Văn An",
    "Tra cứu 0909123456",
    "Tư vấn quá 14 ngày chưa chuyển bước",
    "Tổng tiền giữ chỗ đã thu",
)


@dataclass
class TraLoi:
    text: str
    table: pd.DataFrame | None = None
    chart: pd.DataFrame | None = None  # 2 cột: nhãn, số lượng
    goi_y: list[str] = field(default_factory=list)


@dataclass
class Ctx:
    ts: pd.DataFrame
    nh: pd.DataFrame
    nam_hoc: str
    quyen: set[str] | None = None  # None = không giới hạn
    hom_nay: date = field(default_factory=date.today)

    def duoc(self, *trang: str) -> bool:
        return self.quyen is None or "Cài đặt & đồng bộ" in self.quyen or \
            any(t in self.quyen for t in trang)


# ------------------------------------------------------------------ xử lý chữ
def kd(s) -> str:
    """Bỏ dấu, chữ thường, gộp khoảng trắng."""
    s = unicodedata.normalize("NFD", str(s or "")).replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/.-]", " ", s)).strip()


def _co(q: str, *tu: str) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", q) for t in tu)


def _tien(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "0 đ"
    if v != v:  # NaN
        v = 0
    return f"{v:,.0f} đ".replace(",", ".")


def _so(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _ngay(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date


def _col(df: pd.DataFrame, c: str) -> pd.Series:
    return df[c].fillna("").astype(str) if c in df else pd.Series("", index=df.index)


# ------------------------------------------------------------------ bộ lọc
@dataclass
class Loc:
    khoi: str | None = None
    phan_he: str | None = None
    che_do: str | None = None
    nguon: str | None = None
    tu: date | None = None
    den: date | None = None
    mo_ta_tg: str = ""

    def mo_ta(self) -> str:
        p = []
        if self.khoi:
            p.append(f"khối {self.khoi}" + (f"-{self.phan_he}" if self.phan_he else ""))
        elif self.phan_he:
            p.append(f"hệ {self.phan_he}")
        if self.che_do:
            p.append(self.che_do.lower())
        if self.nguon:
            p.append(f"nguồn {self.nguon}")
        if self.mo_ta_tg:
            p.append(self.mo_ta_tg)
        return ", ".join(p)


def doc_loc(q: str, hom_nay: date) -> Loc:
    loc = Loc()
    m = re.search(r"(?:khoi|lop|k)\s*(\d{1,2})(?!\d)", q)
    if m and 1 <= int(m.group(1)) <= 12:
        loc.khoi = str(int(m.group(1)))
    if _co(q, "iep"):
        loc.phan_he = "IEP"
    elif _co(q, "esl"):
        loc.phan_he = "ESL"
    for c in CHE_DO:
        if kd(c) in q:
            loc.che_do = c
    for n in NGUON:
        dau = kd(n.split(" - ")[0])
        if kd(n) in q or (len(dau) > 5 and dau in q):
            loc.nguon = n
            break
    d = hom_nay
    if _co(q, "hom nay"):
        loc.tu, loc.den, loc.mo_ta_tg = d, d, "hôm nay"
    elif _co(q, "hom qua"):
        loc.tu = loc.den = d - timedelta(days=1)
        loc.mo_ta_tg = "hôm qua"
    elif _co(q, "tuan nay"):
        loc.tu, loc.den, loc.mo_ta_tg = d - timedelta(days=d.weekday()), d, "tuần này"
    elif _co(q, "tuan truoc"):
        dau = d - timedelta(days=d.weekday() + 7)
        loc.tu, loc.den, loc.mo_ta_tg = dau, dau + timedelta(days=6), "tuần trước"
    elif _co(q, "thang nay"):
        loc.tu, loc.den, loc.mo_ta_tg = d.replace(day=1), d, "tháng này"
    elif _co(q, "thang truoc"):
        cuoi = d.replace(day=1) - timedelta(days=1)
        loc.tu, loc.den, loc.mo_ta_tg = cuoi.replace(day=1), cuoi, "tháng trước"
    elif m := re.search(r"(\d{1,3}) ngay (?:qua|gan day|vua qua)", q):
        loc.tu, loc.den = d - timedelta(days=int(m.group(1)) - 1), d
        loc.mo_ta_tg = f"{m.group(1)} ngày qua"
    elif m := re.search(r"thang (\d{1,2})(?:[/ -](\d{4}))?", q):
        th = int(m.group(1))
        if 1 <= th <= 12:
            nam = int(m.group(2)) if m.group(2) else (d.year if th <= d.month else d.year - 1)
            dau = date(nam, th, 1)
            sau = date(nam + (th == 12), th % 12 + 1, 1)
            loc.tu, loc.den, loc.mo_ta_tg = dau, sau - timedelta(days=1), f"tháng {th}/{nam}"
    return loc


def loc_ts(ts: pd.DataFrame, loc: Loc, cot_ngay: str = "NgayLienHe") -> pd.DataFrame:
    df = ts
    if loc.khoi:
        df = df[_col(df, "Khoi").str.split(".").str[0] == loc.khoi]
    if loc.phan_he:
        df = df[_col(df, "PhanHe").str.upper() == loc.phan_he]
    if loc.che_do:
        cot = "CheDo" if "CheDo" in df else "NoiTruBanTru"
        df = df[_col(df, cot).map(kd).str.contains(kd(loc.che_do), regex=False)]
    if loc.nguon and "Nguon" in df:
        df = df[_col(df, "Nguon") == loc.nguon]
    if (loc.tu or loc.den) and cot_ngay in df:
        n = _ngay(df[cot_ngay])
        df = df[(n >= loc.tu) & (n <= loc.den)]
    return df


# ------------------------------------------------------------------ bảng hiển thị
def _bang_ts(df: pd.DataFrame, tien: bool = False) -> pd.DataFrame:
    cols = {"HoTenHS": "Học sinh", "Khoi": "Khối", "PhanHe": "Hệ", "TrangThai": "Bước",
            "GiuCho": "Giữ chỗ", "SDT": "SĐT", "TenLienHe": "Phụ huynh",
            "NgayLienHe": "Ngày liên hệ", "Nguon": "Nguồn"}
    if tien:
        cols["SoTienXacNhan"] = "Số tiền"
    out = df[[c for c in cols if c in df]].rename(columns=cols).copy()
    if "Số tiền" in out:
        out["Số tiền"] = out["Số tiền"].map(lambda v: _tien(v) if str(v) not in ("", "nan") else "")
    if "Ngày liên hệ" in out:
        out["Ngày liên hệ"] = _ngay(out["Ngày liên hệ"]).map(
            lambda x: f"{x:%d/%m/%Y}" if pd.notna(x) else "")
    return out.reset_index(drop=True)


def _dem(series: pd.Series, ten: str, thu_tu=None) -> pd.DataFrame:
    s = series.fillna("").astype(str).replace("", "(trống)")
    vc = s.value_counts()
    if thu_tu:
        vc = vc.reindex([x for x in thu_tu if x in vc.index] +
                        [x for x in vc.index if x not in thu_tu])
    return vc.rename_axis(ten).reset_index(name="Số lượng")


def _khoi_key(k: str):
    a = str(k).split("-")[0].split(".")[0]
    return (int(a) if a.isdigit() else 99, str(k))


# ------------------------------------------------------------------ trả lời
def _nh_con_hieu_luc(c: Ctx) -> pd.DataFrame:
    if c.nh.empty:
        return c.nh
    rut = set(c.ts.loc[_col(c.ts, "TrangThai") == "Rút hồ sơ", "id"]) if "id" in c.ts else set()
    return c.nh[~_col(c.nh, "TuyenSinhID").isin(rut)]


def tong_quan(c: Ctx, loc: Loc) -> TraLoi:
    ts = loc_ts(c.ts, loc)
    tt = _col(ts, "TrangThai")
    pham_vi = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    dong = [f"**Năm học {c.nam_hoc}**{pham_vi}: **{len(ts)}** liên hệ."]
    for b in TRANG_THAI:
        dong.append(f"- {b}: **{int((tt == b).sum())}**")
    if len(ts):
        nh = int(tt.isin(["Nhập học"]).sum())
        dong.append(f"- Tỷ lệ nhập học / liên hệ: **{nh / len(ts):.0%}**")
    if c.duoc("Kế toán"):
        giu = _col(ts, "GiuCho") == "Đã giữ chỗ"
        dong.append(f"- Đã giữ chỗ: **{int(giu.sum())}** · tiền giữ chỗ "
                    f"**{_tien(_so(ts.loc[giu, 'SoTienXacNhan']).sum() if 'SoTienXacNhan' in ts else 0)}**")
    return TraLoi("\n".join(dong), chart=_dem(tt, "Bước", TRANG_THAI),
                  goi_y=["Thống kê theo khối", "Thống kê theo nguồn", "Liên hệ mới trong tuần này"])


TRUC = {  # "theo ..." -> (cột, tên, thứ tự)
    "khoi": ("Khoi", "Khối", None), "nguon": ("Nguon", "Nguồn", NGUON),
    "trang thai": ("TrangThai", "Bước", TRANG_THAI), "buoc": ("TrangThai", "Bước", TRANG_THAI),
    "che do": ("CheDo", "Chế độ", CHE_DO), "giu cho": ("GiuCho", "Giữ chỗ", None),
    "gioi tinh": ("GioiTinh", "Giới tính", None), "tinh trang": ("TinhTrang", "Tình trạng", None),
    "he": ("PhanHe", "Hệ", None), "phan he": ("PhanHe", "Hệ", None),
    "nguoi nhan": ("NguoiNhanHoSo", "Người nhận hồ sơ", None),
}


def thong_ke(c: Ctx, q: str, loc: Loc, ts: pd.DataFrame, ten_tap: str) -> TraLoi | None:
    m = re.search(r"theo (thang|tuan|ngay|" + "|".join(TRUC) + r")", q)
    if not m:
        return None
    truc = m.group(1)
    if truc in ("thang", "tuan", "ngay"):
        n = pd.to_datetime(_col(ts, "NgayLienHe"), errors="coerce")
        fmt = {"thang": "%Y-%m", "tuan": "%G-T%V", "ngay": "%Y-%m-%d"}[truc]
        nhan = n.dt.strftime(fmt).fillna("(không có ngày)")
        bang = nhan.value_counts().sort_index().rename_axis(
            {"thang": "Tháng", "tuan": "Tuần", "ngay": "Ngày"}[truc]).reset_index(name="Số lượng")
    else:
        cot, ten, thu_tu = TRUC[truc]
        bang = _dem(_col(ts, cot), ten, thu_tu)
        if truc == "khoi":
            bang = bang.sort_values(ten, key=lambda s: s.map(_khoi_key)).reset_index(drop=True)
    pham_vi = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    tong = int(bang["Số lượng"].sum())
    dau = bang.sort_values("Số lượng", ascending=False).iloc[0] if len(bang) else None
    nhan_truc = {"thang": "tháng", "tuan": "tuần", "ngay": "ngày"}.get(truc) or \
        TRUC[truc][1].lower()
    text = f"{ten_tap[0].upper() + ten_tap[1:]}{pham_vi}: **{tong}**, chia theo {nhan_truc}."
    if dau is not None and len(bang) > 1:
        text += f" Nhiều nhất: **{dau.iloc[0]}** ({int(dau['Số lượng'])})."
    return TraLoi(text, table=bang, chart=bang)


def giay_to(c: Ctx, loc: Loc) -> TraLoi:
    if not c.duoc("Hồ sơ nhập học"):
        return TraLoi("Tài khoản của bạn không được xem **Hồ sơ nhập học**.")
    nh = loc_ts(_nh_con_hieu_luc(c), Loc(khoi=loc.khoi, phan_he=loc.phan_he, che_do=loc.che_do))
    rows = []
    for _, r in nh.iterrows():
        can, da, thieu = services.tien_do_giay_to(r.to_dict())
        if thieu:
            rows.append({"Học sinh": r.get("HoTen"), "Khối": r.get("Khoi"),
                         "Lớp": r.get("LopHoc"), "Đã nộp": f"{len(can) - len(thieu)}/{len(can)}",
                         "Còn thiếu": "; ".join(thieu)})
    pv = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    if not rows:
        return TraLoi(f"Tất cả **{len(nh)}** hồ sơ nhập học{pv} đã nộp đủ giấy tờ. 🎉")
    bang = pd.DataFrame(rows)
    pho_bien = pd.Series([g for x in rows for g in x["Còn thiếu"].split("; ")]).value_counts()
    text = (f"**{len(rows)}/{len(nh)}** hồ sơ nhập học{pv} còn thiếu giấy tờ. "
            f"Thiếu nhiều nhất: **{pho_bien.index[0]}** ({pho_bien.iloc[0]} HS).")
    return TraLoi(text, table=bang, chart=pho_bien.head(8).rename_axis("Giấy tờ")
                  .reset_index(name="Số lượng"))


def tai_chinh(c: Ctx, q: str, loc: Loc) -> TraLoi:
    if not c.duoc("Kế toán"):
        return TraLoi("Tài khoản của bạn không được xem thông tin **Kế toán** (tiền giữ chỗ, học phí).")
    ts = loc_ts(c.ts, loc)
    gc = _col(ts, "GiuCho").replace("", "Chưa giữ chỗ")
    pv = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    if _co(q, "chua giu cho", "chua dat cho", "chua coc"):
        d = ts[_col(ts, "TrangThai").isin(["Nộp hồ sơ", "Nhập học"]) & (gc == "Chưa giữ chỗ")]
        return TraLoi(f"**{len(d)}** học sinh đã nộp hồ sơ / nhập học nhưng **chưa giữ chỗ**{pv}.",
                      table=_bang_ts(d))
    if _co(q, "hoan phi", "hoan tien", "huy giu cho"):
        d = ts[gc == "Hủy giữ chỗ"]
        return TraLoi(f"**{len(d)}** học sinh hủy giữ chỗ đang **chờ hoàn phí**{pv} — tổng "
                      f"{_tien(_so(_col(d, 'SoTienXacNhan')).sum())}.", table=_bang_ts(d, tien=True))
    nh = loc_ts(_nh_con_hieu_luc(c), Loc(khoi=loc.khoi, phan_he=loc.phan_he))
    con = _so(_col(nh, "SoTienConLai"))
    if _co(q, "con no", "con lai", "chua dong", "chua thanh toan", "no hoc phi", "con thieu"):
        d = nh[con > 0]
        bang = pd.DataFrame({"Học sinh": _col(d, "HoTen"), "Khối": _col(d, "Khoi"),
                             "Lớp": _col(d, "LopHoc"),
                             "Đã thu": _so(_col(d, "TongDaThu")).map(_tien),
                             "Còn lại": con[con > 0].map(_tien)}).reset_index(drop=True)
        return TraLoi(f"**{len(d)}** học sinh còn nợ học phí{pv}, tổng còn lại "
                      f"**{_tien(con.sum())}**.", table=bang)
    giu = ts[gc == "Đã giữ chỗ"]
    text = "\n".join([
        f"**Tài chính năm học {c.nam_hoc}**{pv}:",
        f"- Đã giữ chỗ: **{len(giu)}** HS · **{_tien(_so(_col(giu, 'SoTienXacNhan')).sum())}**",
        f"- Chưa giữ chỗ (đã nộp hồ sơ / nhập học): **"
        f"{int((_col(ts, 'TrangThai').isin(['Nộp hồ sơ', 'Nhập học']) & (gc == 'Chưa giữ chỗ')).sum())}**",
        f"- Chờ hoàn phí: **{int((gc == 'Hủy giữ chỗ').sum())}**",
        f"- Học phí đã thu (hồ sơ nhập học): **{_tien(_so(_col(nh, 'TongDaThu')).sum())}**",
        f"- Học phí còn lại: **{_tien(con.sum())}** ({int((con > 0).sum())} HS)",
    ])
    return TraLoi(text, chart=_dem(gc, "Giữ chỗ"),
                  goi_y=["Danh sách chưa giữ chỗ", "Học sinh còn nợ học phí", "Chờ hoàn phí"])


def tu_van_cu(c: Ctx, q: str, loc: Loc) -> TraLoi:
    m = re.search(r"(\d{1,3}) ngay", q)
    so = int(m.group(1)) if m else 14
    ts = loc_ts(c.ts, Loc(khoi=loc.khoi, phan_he=loc.phan_he, nguon=loc.nguon))
    n = _ngay(_col(ts, "NgayLienHe"))
    d = ts[(_col(ts, "TrangThai") == "Tư vấn") & (n < c.hom_nay - timedelta(days=so))]
    d = d.sort_values("NgayLienHe") if "NgayLienHe" in d else d
    return TraLoi(f"**{len(d)}** liên hệ đang ở bước Tư vấn quá **{so} ngày** chưa chuyển bước.",
                  table=_bang_ts(d))


def _tim(ts: pd.DataFrame, nh: pd.DataFrame, q_goc: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    so = re.sub(r"\D", "", q_goc)
    if len(so) >= 6:
        cot_ts = [x for x in ("SDT",) if x in ts]
        cot_nh = [x for x in ("DienThoaiSLL", "DienThoaiBo", "DienThoaiMe", "DienThoaiNGH",
                              "DienThoaiHS") if x in nh]
        f = lambda df, cs: df[pd.concat([_col(df, x).str.replace(r"\D", "", regex=True)
                                         .str.contains(so[-9:], regex=False) for x in cs],
                                        axis=1).any(axis=1)] if cs and len(df) else df.iloc[0:0]
        return f(ts, cot_ts), f(nh, cot_nh), so
    ten = kd(q_goc)
    ten = re.sub(r"^(?:hay |cho (?:toi|minh) )?(?:tim kiem|tim|tra cuu|thong tin(?: cua| ve)?|"
                 r"ho so(?: cua)?|hoc sinh|hs|em|ban|xem)\s+", "", ten)
    ten = re.sub(r"^(?:hoc sinh|hs|em|ten|be)\s+", "", ten).strip(" ?.")
    if len(ten) < 2:
        return ts.iloc[0:0], nh.iloc[0:0], ten
    a = ts[_col(ts, "HoTenHS").map(kd).str.contains(ten, regex=False)] if len(ts) else ts
    b = nh[_col(nh, "HoTen").map(kd).str.contains(ten, regex=False)] if len(nh) else nh
    return a, b, ten


def tra_cuu(c: Ctx, q_goc: str, bat_buoc: bool = True) -> TraLoi | None:
    if not c.duoc("Data tuyển sinh", "Hồ sơ nhập học"):
        return TraLoi("Tài khoản của bạn không được xem thông tin từng học sinh.") \
            if bat_buoc else None
    a, b, khoa = _tim(c.ts if c.duoc("Data tuyển sinh") else c.ts.iloc[0:0],
                      c.nh if c.duoc("Hồ sơ nhập học") else c.nh.iloc[0:0], q_goc)
    if a.empty and b.empty:
        return TraLoi(f"Không tìm thấy học sinh nào khớp **{khoa}** trong năm học {c.nam_hoc}.") \
            if bat_buoc else None
    if len(a) + len(b) > 1 and not (len(a) == 1 and len(b) <= 1):
        bang = _bang_ts(a) if len(a) else pd.DataFrame({
            "Học sinh": _col(b, "HoTen"), "Khối": _col(b, "Khoi"), "Lớp": _col(b, "LopHoc"),
            "SĐT": _col(b, "DienThoaiSLL")}).reset_index(drop=True)
        return TraLoi(f"Tìm thấy **{max(len(a), len(b))}** học sinh khớp **{khoa}**. "
                      "Gõ thêm họ tên đầy đủ để xem chi tiết.", table=bang.head(50))
    r = a.iloc[0].to_dict() if len(a) else {}
    h = b.iloc[0].to_dict() if len(b) else {}
    if r and not h and "id" in r and "TuyenSinhID" in c.nh:
        m = c.nh[_col(c.nh, "TuyenSinhID") == str(r["id"])]
        h = m.iloc[0].to_dict() if len(m) and c.duoc("Hồ sơ nhập học") else {}
    ten = r.get("HoTenHS") or h.get("HoTen")
    khoi = "-".join(x for x in (str(r.get("Khoi") or h.get("Khoi") or ""),
                                str(r.get("PhanHe") or h.get("PhanHe") or "")) if x and x != "nan")
    dong = [f"**{ten}** — khối {khoi or '?'}"]
    if r:
        nl = _ngay(pd.Series([r.get("NgayLienHe")])).iloc[0]
        dong += [f"- Bước: **{r.get('TrangThai') or '—'}** · tình trạng: {r.get('TinhTrang') or '—'}",
                 f"- Phụ huynh: {r.get('TenLienHe') or '—'} · SĐT **{r.get('SDT') or '—'}**",
                 f"- Liên hệ ngày {nl:%d/%m/%Y} · nguồn: {r.get('Nguon') or '—'}"
                 if pd.notna(nl) else f"- Nguồn: {r.get('Nguon') or '—'}",
                 f"- Chế độ: {r.get('CheDo') or '—'}"]
        if c.duoc("Kế toán"):
            dong.append(f"- Giữ chỗ: **{r.get('GiuCho') or 'Chưa giữ chỗ'}**"
                        + (f" · {_tien(r.get('SoTienXacNhan'))}"
                           if float(_so(pd.Series([r.get("SoTienXacNhan")])).iloc[0]) else ""))
    if h:
        can, da, thieu = services.tien_do_giay_to(h)
        dong += [f"- Hồ sơ nhập học: lớp **{h.get('LopHoc') or 'chưa xếp'}** · "
                 f"tình trạng {h.get('TinhTrangHS') or '—'}",
                 f"- Giấy tờ: **{len(can) - len(thieu)}/{len(can)}**"
                 + (f" — còn thiếu: {', '.join(thieu)}" if thieu else " — đủ")]
        if c.duoc("Kế toán"):
            dong.append(f"- Học phí: đã thu {_tien(h.get('TongDaThu'))} · "
                        f"còn lại **{_tien(h.get('SoTienConLai'))}**")
    elif r:
        dong.append("- Chưa có hồ sơ nhập học.")
    return TraLoi("\n".join(dong))


def huong_dan() -> TraLoi:
    return TraLoi(
        "Mình là trợ lý dữ liệu tuyển sinh, trả lời trực tiếp từ dữ liệu của app "
        "(không gửi ra ngoài). Bạn có thể hỏi:\n"
        "- **Đếm / liệt kê**: liên hệ, tư vấn, nộp hồ sơ, nhập học, rút hồ sơ — kèm *khối 10*, "
        "*IEP/ESL*, *nội trú*, *nguồn mạng xã hội*, *hôm nay / tuần này / tháng 7 / 30 ngày qua*\n"
        "- **Thống kê theo** khối, nguồn, tháng, tuần, bước, chế độ, giữ chỗ\n"
        "- **Tra cứu học sinh** theo tên hoặc số điện thoại\n"
        "- **Giấy tờ còn thiếu**, **tư vấn quá hạn**\n"
        "- **Tài chính**: giữ chỗ, chờ hoàn phí, học phí còn nợ (tài khoản có quyền Kế toán)",
        goi_y=list(VI_DU[:6]))


TAP = (  # (từ khóa, trạng thái hoặc None = tất cả liên hệ, tên)
    (("rut ho so", "rut hs", "rut"), "Rút hồ sơ", "học sinh rút hồ sơ"),
    (("nhap hoc",), "Nhập học", "học sinh nhập học"),
    (("nop ho so", "da nop", "nop hs"), "Nộp hồ sơ", "học sinh nộp hồ sơ"),
    (("tu van", "dang tu van"), "Tư vấn", "liên hệ đang tư vấn"),
    (("lien he", "hoc sinh", "hs", "phu huynh", "data"), None, "liên hệ"),
)


def tra_loi(cau_hoi: str, c: Ctx) -> TraLoi:
    q = kd(cau_hoi)
    if not q or _co(q, "giup", "huong dan", "lam duoc gi", "hoi gi", "help", "xin chao", "chao"):
        return huong_dan()
    loc = doc_loc(q, c.hom_nay)
    so = re.sub(r"\D", "", cau_hoi)

    if len(so) >= 8 and not re.search(r"\d{1,2}/\d{4}", cau_hoi):
        return tra_cuu(c, cau_hoi)
    if _co(q, "tim", "tim kiem", "tra cuu", "thong tin cua", "thong tin ve", "ho so cua"):
        return tra_cuu(c, cau_hoi)
    if _co(q, "giay to", "thieu ho so", "ho so con thieu", "bo sung", "chua nop du", "nop du",
           "con thieu giay"):
        return giay_to(c, loc)
    if _co(q, "qua han", "chua chuyen buoc", "lau chua", "can cham soc", "bo quen", "ton dong"):
        return tu_van_cu(c, q, loc)
    if _co(q, "tien", "hoc phi", "giu cho", "hoan phi", "dong phi", "thu phi", "doanh thu",
           "con no", "ke toan", "tai chinh", "chua coc", "dat cho") and "theo giu cho" not in q:
        return tai_chinh(c, q, loc)
    if _co(q, "tong quan", "tinh hinh", "bao cao nhanh", "tom tat", "the nao", "ra sao"):
        return tong_quan(c, loc)

    tap = next((t for t in TAP if _co(q, *t[0])), None)
    ts = loc_ts(c.ts, loc)
    if tap and tap[1]:
        ts = ts[_col(ts, "TrangThai") == tap[1]]
    ten_tap = tap[2] if tap else "liên hệ"
    if r := thong_ke(c, q, loc, ts, ten_tap):
        return r
    if tap or loc.mo_ta() or _co(q, "bao nhieu", "so luong", "dem", "danh sach", "liet ke"):
        pv = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
        text = f"Năm học {c.nam_hoc}: **{len(ts)}** {ten_tap}{pv}."
        if len(ts) and not (tap and tap[1]):
            tt = _col(ts, "TrangThai").value_counts()
            text += " Gồm " + ", ".join(f"{b.lower()} {int(tt.get(b, 0))}" for b in TRANG_THAI) + "."
        muon_ds = _co(q, "danh sach", "liet ke", "nhung ai", "ai ", "nhung em", "la ai", "gom ai",
                      "hoc sinh nao", "hs nao", "nhung hs", "nhung hoc sinh") or not _co(
            q, "bao nhieu", "so luong", "dem", "tong so")
        bang = _bang_ts(ts, tien=c.duoc("Kế toán")) if muon_ds and c.duoc("Data tuyển sinh") else None
        chart = None
        if not loc.khoi and len(ts):
            chart = _dem(_col(ts, "Khoi"), "Khối").sort_values(
                "Khối", key=lambda s: s.map(_khoi_key)).reset_index(drop=True)
        return TraLoi(text, table=bang, chart=chart,
                      goi_y=[f"Thống kê {ten_tap} theo nguồn", f"Thống kê {ten_tap} theo tháng"])
    # thử coi cả câu là tên học sinh
    if r := tra_cuu(c, cau_hoi, bat_buoc=False):
        return r
    t = huong_dan()
    t.text = "Mình chưa hiểu câu hỏi này. " + t.text
    return t
