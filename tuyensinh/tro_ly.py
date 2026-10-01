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
    "Nhập học qua các năm",
    "Liên hệ tháng 4 so với năm trước",
    "Nguồn nào hiệu quả nhất?",
    "Trường cũ nào có nhiều học sinh nhập học nhất?",
    "So sánh khối 6 và khối 10",
    "Học sinh nào còn thiếu giấy tờ khối 6?",
    "Danh sách nộp hồ sơ nhưng chưa giữ chỗ",
    "Tìm Nguyễn Văn An",
    "Tư vấn quá 14 ngày chưa chuyển bước",
)


@dataclass
class TraLoi:
    text: str
    table: pd.DataFrame | None = None
    # 2 cột (nhãn, số lượng) -> cột/thanh; 3 cột (nhãn, nhóm, số lượng) -> cột nhóm
    chart: pd.DataFrame | None = None
    goi_y: list[str] = field(default_factory=list)
    hieu_la: str = ""      # câu hỏi đã chuẩn hóa (dùng làm ngữ cảnh cho câu sau)
    da_ghep: bool = False  # câu hỏi được ghép với ngữ cảnh câu trước


@dataclass
class Ctx:
    ts: pd.DataFrame
    nh: pd.DataFrame
    nam_hoc: str
    quyen: set[str] | None = None  # None = không giới hạn
    hom_nay: date = field(default_factory=date.today)
    ts_all: pd.DataFrame | None = None  # mọi năm học (so sánh các năm)
    nh_all: pd.DataFrame | None = None

    def duoc(self, *trang: str) -> bool:
        return self.quyen is None or "Cài đặt & đồng bộ" in self.quyen or \
            any(t in self.quyen for t in trang)

    def cac_nam(self) -> list[str]:
        ds = set(_col(self.ts_all, "NamHoc")) if self.ts_all is not None else set()
        return sorted({y for y in ds if re.fullmatch(r"\d{4}-\d{4}", y)} | {self.nam_hoc})

    def nam(self, nam_hoc: str) -> "Ctx":
        if nam_hoc == self.nam_hoc or self.ts_all is None:
            return self
        nh_all = self.nh_all if self.nh_all is not None else self.nh.iloc[0:0]
        return Ctx(self.ts_all[_col(self.ts_all, "NamHoc") == nam_hoc],
                   nh_all[_col(nh_all, "NamHoc") == nam_hoc], nam_hoc, self.quyen,
                   self.hom_nay, self.ts_all, self.nh_all)


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
    khoi_ds: list[str] = field(default_factory=list)  # "khối 10 và khối 11" -> so sánh
    gioi_tinh: str | None = None
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
        if self.gioi_tinh:
            p.append(f"học sinh {self.gioi_tinh.lower()}")
        if self.nguon:
            p.append(f"nguồn {self.nguon}")
        if self.mo_ta_tg:
            p.append(self.mo_ta_tg)
        return ", ".join(p)


_GIOI_KD = (r"(?:hoc sinh|be|em|cac em|tre|ban|gioi tinh|phai) (?:nam|nu)\b"
            r"(?! (?:truoc|nay|hoc|ngoai|\d))|nam sinh|nu sinh|con trai|con gai")

def doc_loc(q: str, hom_nay: date, goc: str = "") -> Loc:
    loc = Loc()
    ds = [str(int(x)) for x in re.findall(r"(?:khoi|lop|k)\s*(\d{1,2})(?!\d)", q)
          if 1 <= int(x) <= 12]
    ds += [str(int(x)) for x in re.findall(r"(?:khoi|lop)\s*\d{1,2}\s*(?:,|va|voi|-)\s*(\d{1,2})(?!\d)", q)
           if 1 <= int(x) <= 12]
    ds = list(dict.fromkeys(ds))
    if len(ds) >= 2:
        loc.khoi_ds = ds
    elif ds:
        loc.khoi = ds[0]
    g = unicodedata.normalize("NFC", goc.lower())
    # "nam/nữ" chỉ là giới tính khi đi sau "học sinh / hs / bé / em / giới tính" (tránh tên "Nam")
    truoc = r"(?:học sinh|hs|học viên|bé|em|các em|trẻ|bạn|giới tính|phái)\s+"
    gk = re.search(_GIOI_KD, q)  # câu đã chuẩn hóa (vd câu ghép ngữ cảnh)
    if re.search(rf"{truoc}nữ(?!\w)|(?<!\w)(?:con gái|bé gái|nữ sinh)(?!\w)", g) or \
            (gk and re.search(r"nu|gai", gk.group(0))):
        loc.gioi_tinh = "Nữ"
    elif re.search(rf"{truoc}nam(?!\w)|(?<!\w)(?:con trai|bé trai|nam sinh)(?!\w)", g) or gk:
        loc.gioi_tinh = "Nam"
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
    if loc.gioi_tinh:
        df = df[_col(df, "GioiTinh").map(kd) == kd(loc.gioi_tinh)]
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


# Các trục thống kê: (từ khóa, cột, tên hiển thị, thứ tự, gộp chữ viết khác nhau)
# Thứ tự quan trọng: cụm dài trước (tình trạng trước tỉnh, phường xã trước phường).
TRUC = (
    (("truong cu", "truong truoc", "truong dang hoc", "truong hoc cu", "truong"), "TruongCu", "Trường cũ",
     None, True),
    (("tinh trang",), "TinhTrang", "Tình trạng", None, False),
    (("phuong xa", "phuong/xa", "xa phuong", "phuong"), "TruongCu_PhuongXa",
     "Phường/xã (trường cũ)", None, True),
    (("tinh thanh", "tinh", "thanh pho"), "TruongCu_Tinh", "Tỉnh/thành (trường cũ)", None, True),
    (("nguoi gioi thieu", "gioi thieu"), "NguoiGioiThieu", "Người giới thiệu", None, True),
    (("nguoi nhan",), "NguoiNhanHoSo", "Người nhận hồ sơ", None, True),
    (("nguon",), "Nguon", "Nguồn", NGUON, False),
    (("khoi",), "Khoi", "Khối", None, False),
    (("trang thai", "buoc"), "TrangThai", "Bước", TRANG_THAI, False),
    (("che do",), "CheDo", "Chế độ", CHE_DO, False),
    (("giu cho",), "GiuCho", "Giữ chỗ", None, False),
    (("gioi tinh",), "GioiTinh", "Giới tính", None, False),
    (("phan he", "he"), "PhanHe", "Hệ", None, False),
)
THOI_GIAN = {"thang": ("Tháng", "%Y-%m"), "tuan": ("Tuần", "%G-T%V"), "ngay": ("Ngày", "%Y-%m-%d")}
_SO_SANH = ("nhieu nhat", "it nhat", "dong nhat", "cao nhat", "thap nhat", "top", "xep hang",
            "pho bien", "chu yeu", "nhieu hs nhat", "nhieu hoc sinh nhat")


def _tim_truc(q: str):
    """Trục thống kê trong câu hỏi: 'theo X', 'X nào ...', 'từng X', 'X ... nhiều nhất'."""
    co_hoi = _co(q, "nao", "tung", "moi", "phan bo", "co cau", "ty le", "thong ke", "nhat",
                 *_SO_SANH)
    for tu, *thong_tin in TRUC:
        for t in tu:
            # "khối 10" / "lớp 6" là bộ lọc, không phải trục
            for m in re.finditer(rf"(?<!\w){re.escape(t)}(?!\w)(?!\s*\d)", q):
                if co_hoi or q[:m.start()].endswith("theo "):
                    return t, thong_tin
    m = re.search(r"theo (thang|tuan|ngay)", q)
    return (m.group(1), None) if m else (None, None)


def _dem_gop(series: pd.Series, ten: str) -> pd.DataFrame:
    """Đếm, gộp các cách viết khác nhau (hoa/thường, có/không dấu, khoảng trắng)."""
    s = series.fillna("").astype(str).str.strip()
    khoa = s.map(kd)
    nhan = s.groupby(khoa).agg(lambda x: x.value_counts().index[0])
    vc = khoa.value_counts()
    out = pd.DataFrame({ten: [nhan[k] or "(trống)" for k in vc.index],
                        "Số lượng": vc.values})
    return out


def thong_ke(c: Ctx, q: str, loc: Loc, ts: pd.DataFrame, ten_tap: str) -> TraLoi | None:
    t, tt = _tim_truc(q)
    if not t:
        return None
    if tt is None:  # theo thời gian
        ten, fmt = THOI_GIAN[t]
        n = pd.to_datetime(_col(ts, "NgayLienHe"), errors="coerce")
        vc = n.dt.strftime(fmt).fillna("~").value_counts().sort_index()
        vc.index = [("(không có ngày)" if k == "~" else
                     f"{k[5:]}/{k[:4]}" if t == "thang" else k) for k in vc.index]
        bang = vc.rename_axis(ten).reset_index(name="Số lượng")
        thu_tu_co_dinh = True
    else:
        cot, ten, thu_tu, gop = tt
        bang = _dem_gop(_col(ts, cot), ten) if gop else _dem(_col(ts, cot), ten, thu_tu)
        thu_tu_co_dinh = bool(thu_tu) or cot == "Khoi"
        if cot == "Khoi":
            bang = bang.sort_values(ten, key=lambda s: s.map(_khoi_key)).reset_index(drop=True)
    pham_vi = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    tong = int(bang["Số lượng"].sum())
    co_gia_tri = bang[~bang.iloc[:, 0].isin(["(trống)", "(không có ngày)"])]
    trong = tong - int(co_gia_tri["Số lượng"].sum())
    it = _co(q, "it nhat", "thap nhat")
    ngan = ten.split(" (")[0].lower()  # "tỉnh/thành (trường cũ)" -> "tỉnh/thành"
    so_sanh = _co(q, *_SO_SANH) or _co(q, "nhat")
    xep = co_gia_tri.sort_values("Số lượng", ascending=it, kind="stable").reset_index(drop=True)
    Tap = ten_tap[0].upper() + ten_tap[1:]
    if co_gia_tri.empty:
        return TraLoi(f"{Tap}{pham_vi}: **{tong}**, nhưng chưa có dữ liệu **{ngan}**.")
    if so_sanh or (_co(q, "nao") and not thu_tu_co_dinh):
        dau = xep.iloc[0]
        cung = xep[xep["Số lượng"] == dau["Số lượng"]]
        ten_dau = ", ".join(f"**{x}**" for x in cung.iloc[:, 0].head(5)) + (
            f" và {len(cung) - 5} nơi khác" if len(cung) > 5 else "")
        text = (f"{ten} có {'ít' if it else 'nhiều'} {ten_tap} nhất{pham_vi}: {ten_dau} "
                f"với **{int(dau['Số lượng'])}** {ten_tap}")
        if len(xep) > 1 and len(cung) == 1:
            nhi = xep.iloc[1]
            text += f", tiếp theo là {nhi.iloc[0]} ({int(nhi['Số lượng'])})"
        text += f". Có {len(xep)} {ngan} khác nhau trên tổng {tong} {ten_tap}"
        text += f" ({trong} chưa ghi {ngan})." if trong else "."
        bang_ra = xep.copy()
        bang_ra.insert(0, "Hạng", range(1, len(bang_ra) + 1))
        return TraLoi(text, table=bang_ra, chart=xep.head(15),
                      goi_y=[f"Thống kê {ten_tap} theo khối", f"Thống kê {ten_tap} theo nguồn"])
    text = f"{Tap}{pham_vi}: **{tong}**, chia theo {ngan} ({len(co_gia_tri)} nhóm)."
    if len(xep) > 1:
        text += f" Nhiều nhất: **{xep.iloc[0, 0]}** ({int(xep.iloc[0]['Số lượng'])})."
    if trong:
        text += f" {trong} chưa ghi {ngan}."
    return TraLoi(text, table=bang if thu_tu_co_dinh else xep,
                  chart=bang if thu_tu_co_dinh else xep.head(15))


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
    def khop(df, cot):
        if not len(df):
            return df
        ho_ten = _col(df, cot).map(kd)
        m = df[ho_ten.str.contains(ten, regex=False)]
        if m.empty:  # gõ không đúng thứ tự: "long tran" -> mọi chữ đều có trong họ tên
            tu = ten.split()
            m = df[ho_ten.map(lambda h: all(t in h.split() for t in tu))]
        return m
    return khop(ts, "HoTenHS"), khop(nh, "HoTen"), ten


def tra_cuu(c: Ctx, q_goc: str, bat_buoc: bool = True) -> TraLoi | None:
    if not c.duoc("Data tuyển sinh", "Hồ sơ nhập học"):
        return TraLoi("Tài khoản của bạn không được xem thông tin từng học sinh.") \
            if bat_buoc else None
    a, b, khoa = _tim(c.ts if c.duoc("Data tuyển sinh") else c.ts.iloc[0:0],
                      c.nh if c.duoc("Hồ sơ nhập học") else c.nh.iloc[0:0], q_goc)
    if a.empty and b.empty and c.ts_all is not None:  # thử các năm học khác
        for y in reversed(c.cac_nam()):
            if y != c.nam_hoc:
                cy = c.nam(y)
                a2, b2, _ = _tim(cy.ts if c.duoc("Data tuyển sinh") else cy.ts.iloc[0:0],
                                 cy.nh if c.duoc("Hồ sơ nhập học") else cy.nh.iloc[0:0], q_goc)
                if len(a2) or len(b2):
                    r = tra_cuu(cy, q_goc, bat_buoc)
                    if r:
                        r.text = f"*(Tìm thấy ở năm học {y})*\n\n" + r.text
                    return r
    if a.empty and b.empty:
        return TraLoi(f"Không tìm thấy học sinh nào khớp **{khoa}** trong các năm học.") \
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
        "(không gửi ra ngoài). Hỏi tự nhiên, có dấu hay không dấu, viết tắt (*bn, hs, ds*) đều "
        "được. Mình có thể:\n"
        "- **Đếm / liệt kê**: liên hệ, tư vấn, nộp hồ sơ, nhập học, rút hồ sơ — kèm *khối 10*, "
        "*IEP/ESL*, *nội trú*, *học sinh nữ*, *nguồn mạng xã hội*, *hôm nay / tuần này / tháng 7 / "
        "30 ngày qua*\n"
        "- **Thống kê, xếp hạng**: *theo khối / nguồn / tháng / trường cũ / tỉnh*, "
        "*trường cũ nào nhiều HS nhất*, *nguồn nào hiệu quả nhất* (tỷ lệ nhập học)\n"
        "- **So sánh**: *so với năm trước*, *qua các năm*, *3 năm gần đây*, *năm học 2024-2025*, "
        "*so sánh khối 6 và khối 10*, cùng kỳ (*tháng 4 so với năm trước*)\n"
        "- **Hỏi tiếp theo ngữ cảnh**: *còn khối 11 thì sao?*, *năm trước?*, *thế còn nam?*\n"
        "- **Tra cứu học sinh** theo tên hoặc số điện thoại; **giấy tờ còn thiếu**; "
        "**tư vấn quá hạn**\n"
        "- **Tài chính**: giữ chỗ, chờ hoàn phí, học phí còn nợ (tài khoản có quyền Kế toán)",
        goi_y=list(VI_DU[:6]))


TAP = (  # (từ khóa, trạng thái hoặc None = tất cả liên hệ, tên)
    (("rut ho so",), "Rút hồ sơ", "học sinh rút hồ sơ"),
    (("nhap hoc",), "Nhập học", "học sinh nhập học"),
    (("nop ho so",), "Nộp hồ sơ", "học sinh nộp hồ sơ"),
    (("tu van",), "Tư vấn", "liên hệ đang tư vấn"),
    (("lien he", "hoc sinh", "phu huynh", "data"), None, "liên hệ"),
)

# ------------------------------------------------------------------ hiểu câu hỏi
# Từ đồng nghĩa / viết tắt -> cụm chuẩn (áp dụng trên chuỗi không dấu)
DONG_NGHIA = (
    (r"\b(?:bn|bao nhiu|bao nhieu)\b", "bao nhieu"),
    (r"\bds\b", "danh sach"), (r"\bhs\b", "hoc sinh"), (r"\b(?:ph|phhs)\b", "phu huynh"),
    (r"\bsdt\b", "so dien thoai"), (r"\bti le\b", "ty le"), (r"\bnam ngoai\b", "nam truoc"),
    (r"\b(?:trung tuyen|da vao hoc|vao hoc|nhap truong|chinh thuc|da nhap hoc)\b", "nhap hoc"),
    (r"\b(?:dang ky hoc|dang ky nhap hoc|nop don|nop hs|da nop ho so|da nop)\b", "nop ho so"),
    (r"\b(?:bo hoc|nghi hoc|huy ho so|rut lui|khong hoc nua|rut hs|rut)\b(?! ho so)", "rut ho so"),
    (r"\b(?:tiem nang|dang quan tam|chua chot|dang tu van)\b", "tu van"),
    (r"\b(?:dong nhat|nhieu hs nhat|nhieu hoc sinh nhat)\b", "nhieu nhat"),
    (r"\bkhoi lop\b", "khoi"), (r"\blop (\d{1,2})\b", r"khoi \1"),
    (r"\b(?:so voi cung ky|cung ky nam truoc)\b", "so voi nam truoc"),
)
# Từ vựng để sửa lỗi gõ (chỉ dùng cho nhận dạng ý định, không đổi tên học sinh)
_TU_VUNG = set("""bao nhieu danh sach hoc sinh lien he nhap hoc nop ho so rut tu van thong ke theo
khoi nguon thang tuan ngay nam truoc nay qua cac tung truong cu tinh thanh pho phuong xa
nguoi nhan gioi thieu giay to thieu han chua chuyen buoc tien phi giu cho hoan dong tong quan
tinh hinh nhieu nhat it ty le chuyen doi hieu qua so sanh voi noi tru ban tru ngoai che do
tim tra cuu thong tin cua trang thai gioi tinh phan he top xep hang moi
trung tuyen vao chinh thuc dang ky don nghi huy lui khong tiem nang quan tam chot cung gan
nhat lien tiep hien sinh trai gai""".split())


def _sua_loi_go(goc: str) -> str:
    """Bỏ dấu từng từ; sửa từ gõ sai gần giống từ khóa (bỏ qua từ viết hoa: tên riêng)."""
    from difflib import get_close_matches
    out = []
    for tu in unicodedata.normalize("NFC", str(goc or "")).split():
        w = kd(tu)
        if len(w) >= 4 and w.isalpha() and w not in _TU_VUNG and not tu[:1].isupper():
            m = get_close_matches(w, _TU_VUNG, n=1, cutoff=0.8)
            w = m[0] if m else w
        out.append(w)
    return " ".join(out)


def chuan_hoa(q: str) -> str:
    q = kd(_sua_loi_go(q))
    for a, b in DONG_NGHIA:
        q = re.sub(a, b, q)
    return re.sub(r"\s+", " ", q).strip()


_NAM_RE = r"(20\d{2})\s*[-/]\s*(20\d{2})"
_NHIEU_NAM = ("cac nam", "qua cac nam", "tung nam", "moi nam", "nhieu nam", "cac nam hoc",
              "nhung nam", "hang nam")


def doc_nam(q: str, c: Ctx) -> tuple[list[str], bool, str]:
    """(các năm học được hỏi, có so sánh nhiều năm không, câu hỏi đã bỏ phần năm học)."""
    ds = c.cac_nam()
    i = ds.index(c.nam_hoc) if c.nam_hoc in ds else len(ds) - 1
    nams = [f"{a}-{b}" for a, b in re.findall(_NAM_RE, q)]
    q2 = re.sub(_NAM_RE, " ", q)
    for y in re.findall(r"nam(?: hoc)? (20\d{2})\b", q2):
        nams += [n for n in ds if n.startswith(y)][:1]
    q2 = re.sub(r"nam(?: hoc)? 20\d{2}\b", " ", q2)
    so_sanh = len(nams) >= 2 or _co(q2, "so voi nam truoc", "so sanh nam truoc", *_NHIEU_NAM)
    if m := re.search(r"(?<!khoi )(?<!lop )\b(\d) nam (?:gan (?:day|nhat)|qua|lien tiep|vua qua)", q2):
        nams, so_sanh = ds[max(0, i - int(m.group(1)) + 1):i + 1], True
    elif _co(q2, *_NHIEU_NAM) and len(nams) < 2:
        nams = ds[max(0, i - 2):i + 1]
    elif _co(q2, "so voi nam truoc", "so sanh nam truoc", "so sanh voi nam truoc"):
        nams = ds[max(0, i - 1):i + 1]
    elif m := re.search(r"(?<!khoi )(?<!lop )\b(\d) nam truoc", q2):
        nams = [ds[max(0, i - int(m.group(1)))]]
    elif _co(q2, "nam truoc", "nam hoc truoc"):
        nams = [ds[max(0, i - 1)]]
    q2 = re.sub(r"\b(?:(?<!khoi )(?<!lop )\d nam (?:gan (?:day|nhat)|qua|lien tiep|vua qua)|"
                r"so sanh voi nam truoc|so voi nam truoc|so sanh nam truoc|"
                r"(?<!khoi )(?<!lop )\d nam truoc|nam hoc truoc|nam truoc|"
                r"nam hoc nay|nam nay|" + "|".join(_NHIEU_NAM) + r")\b", " ", q2)
    nams = [n for n in dict.fromkeys(nams) if n in ds]
    return nams, so_sanh and len(nams) >= 2, re.sub(r"\s+", " ", q2).strip()


# Ngữ cảnh: "còn khối 11 thì sao?", "năm trước thì sao?", "thế còn nhập học?"
_TIEP = r"^(?:the con|vay con|con voi|con|vay|the|va)\b|\b(?:thi sao|the nao|thi the nao|nua|nhi)\s*$"
_LOP_LOC = {
    "khoi": r"(?:khoi|lop|k)\s*\d{1,2}(?:\s*(?:,|va|voi)\s*\d{1,2})*",
    "he": r"\b(?:iep|esl)\b",
    "tg": r"hom nay|hom qua|tuan nay|tuan truoc|thang nay|thang truoc|"
          r"\d{1,3} ngay (?:qua|gan day|vua qua)|thang \d{1,2}(?:[/ -]\d{4})?",
    "nam": _NAM_RE + r"|nam(?: hoc)? 20\d{2}|\d nam (?:gan (?:day|nhat)|qua|lien tiep)|"
           r"so voi nam truoc|nam truoc|nam nay|" + "|".join(_NHIEU_NAM),
    "che_do": r"noi tru|ban tru|ngoai tru",
    "gioi": _GIOI_KD,
    "nguon": "|".join(re.escape(kd(n)) for n in NGUON),
    "tap": r"rut ho so|nhap hoc|nop ho so|tu van|lien he",
    "truc": r"theo [a-z/]+(?: [a-z]+)?",
}
_Y_DINH = ("bao nhieu", "danh sach", "thong ke", "theo", "nao", "nhat", "ty le", "tim", "tra cuu",
           "giay to", "tien", "hoc phi", "giu cho", "tong quan", "qua han", "so sanh", "liet ke")


_TU_DEM = r"\b(?:cua|o|trong|va|voi|cac|nhung|hoc sinh|em|thi|co|la|nhe|a|so|bao nhieu)\b"


def ghep_ngu_canh(q: str, truoc: str | None) -> tuple[str, bool]:
    """Ghép câu hỏi nối tiếp với câu trước ("còn khối 11 thì sao?", "năm trước?"):
    thay các bộ lọc mới vào câu trước. Chỉ ghép khi có từ nối hoặc câu chỉ toàn bộ lọc."""
    if not truoc or len(q.split()) > 8:
        return q, False
    tiep = bool(re.search(_TIEP, q))
    loi = re.sub(_TIEP, " ", q).strip()
    if tiep and loi in ("nam", "nu"):  # "thế còn nam?" -> học sinh nam
        q = q.replace(loi, f"hoc sinh {loi}")
    co_loc = [k for k, r in _LOP_LOC.items() if re.search(rf"(?<!\w)(?:{r})(?!\w)", q)]
    con_lai = q
    for k, r in _LOP_LOC.items():
        if k not in ("tap", "truc"):
            con_lai = re.sub(rf"(?<!\w)(?:{r})(?!\w)", " ", con_lai)
    con_lai = re.sub(_TU_DEM, " ", re.sub(_TIEP, " ", con_lai)).strip()
    if not (tiep or (co_loc and not con_lai)):
        return q, False
    cu = truoc
    for k in co_loc:
        cu = re.sub(rf"(?<!\w)(?:{_LOP_LOC[k]})(?!\w)", " ", cu)
    moi = re.sub(_TIEP, " ", q)
    return re.sub(r"\s+", " ", f"{cu} {moi}").strip(), True


# ------------------------------------------------------------------ tỷ lệ chuyển đổi
def ty_le(c: Ctx, q: str, loc: Loc, ts: pd.DataFrame) -> TraLoi:
    if _co(q, "rut ho so"):
        dk, ten = _col(ts, "TrangThai") == "Rút hồ sơ", "rút hồ sơ"
    elif _co(q, "nop ho so"):
        dk, ten = _col(ts, "TrangThai").isin(["Nộp hồ sơ", "Nhập học"]), "nộp hồ sơ"
    else:
        dk, ten = _col(ts, "TrangThai") == "Nhập học", "nhập học"
    pv = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
    tong, so = len(ts), int(dk.sum())
    text = (f"Tỷ lệ {ten}{pv} năm học {c.nam_hoc}: **{_pt(100 * so / tong)}** "
            f"({so}/{tong} liên hệ).") if tong else f"Chưa có liên hệ nào{pv}."
    t, tt = _tim_truc(q)
    if not t or tt is None or not tong:
        return TraLoi(text, goi_y=[f"Tỷ lệ {ten} theo khối", f"Tỷ lệ {ten} theo nguồn",
                                   f"Tỷ lệ {ten} qua các năm"])
    cot, ten_truc, thu_tu, gop = tt
    nhom = _col(ts, cot).str.strip()
    if gop:
        khoa = nhom.map(kd)
        nhan = nhom.groupby(khoa).agg(lambda x: x.value_counts().index[0])
        nhom = khoa.map(nhan)
    g = pd.DataFrame({ten_truc: nhom.replace("", "(trống)"), "_ok": dk}).groupby(ten_truc)["_ok"]
    bang = pd.DataFrame({"Liên hệ": g.size(), ten.capitalize(): g.sum().astype(int)})
    bang["Tỷ lệ (%)"] = (100 * bang.iloc[:, 1] / bang["Liên hệ"]).round(1)
    bang = bang.reset_index()
    du = bang[(bang["Liên hệ"] >= 5) & (bang[ten_truc] != "(trống)")]
    if cot == "Khoi":
        bang = bang.sort_values(ten_truc, key=lambda s: s.map(_khoi_key))
    else:
        bang = bang.sort_values(["Tỷ lệ (%)", "Liên hệ"], ascending=False)
    if len(du):
        it = _co(q, "it nhat", "thap nhat", "kem nhat")
        top = du.sort_values(["Tỷ lệ (%)", "Liên hệ"], ascending=[it, False]).iloc[0]
        dau = (f"{ten_truc} có tỷ lệ {ten} {'thấp' if it else 'cao'} nhất (từ 5 liên hệ): "
               f"**{top[ten_truc]}** — {_pt(top['Tỷ lệ (%)'])} ({top.iloc[2]}/{top['Liên hệ']}).")
        text = f"{dau} Toàn trường: {text[0].lower()}{text[1:]}" if _co(q, "nao", "nhat") \
            else f"{text} {dau}"
    return TraLoi(text, table=bang.reset_index(drop=True),
                  chart=bang[[ten_truc, "Tỷ lệ (%)"]].head(15).rename(
                      columns={"Tỷ lệ (%)": "Số lượng"}))


# ------------------------------------------------------------------ so sánh
def _pt(v: float) -> str:
    return f"{v:.1f}%".replace(".", ",")


def _tang(a, b) -> str:
    if not a:
        return "—"
    v = 100 * (b - a) / a
    return f"{v:+.1f}%".replace(".", ",")


def _doi_ky(loc: Loc, nam: str, goc: str) -> Loc:
    """Dời khoảng thời gian sang cùng kỳ của năm học khác."""
    if not (loc.tu or loc.den):
        return loc
    lech = int(nam[:4]) - int(goc[:4])

    def doi(d):
        try:
            return d.replace(year=d.year + lech) if d else d
        except ValueError:  # 29/02
            return d.replace(year=d.year + lech, day=28)
    return Loc(**{**loc.__dict__, "tu": doi(loc.tu), "den": doi(loc.den)})


def _tap_cua(q: str, loc: Loc):
    q_tap = q.replace(kd(loc.nguon), " ") if loc.nguon else q
    return next((t for t in TAP if _co(q_tap, *t[0])), None)


def so_sanh_nam(c: Ctx, q: str, loc: Loc, nams: list[str]) -> TraLoi:
    tap = _tap_cua(q, loc)
    ten_tap = tap[2] if tap else "liên hệ"
    pv = f" ({loc.mo_ta()}{', cùng kỳ' if loc.tu else ''})" if loc.mo_ta() else ""
    cy = {y: c.nam(y) for y in nams}
    ts_y = {y: loc_ts(cy[y].ts, _doi_ky(loc, y, c.nam_hoc)) for y in nams}
    if tap and tap[1]:
        ts_y = {y: d[_col(d, "TrangThai") == tap[1]] for y, d in ts_y.items()}
    t, tt = _tim_truc(q)
    if _co(q, "ty le", "hieu qua", "chuyen doi") and not (t and tt):
        rows = []
        for y in nams:
            d = loc_ts(cy[y].ts, _doi_ky(loc, y, c.nam_hoc))
            n = int((_col(d, "TrangThai") == "Nhập học").sum())
            rows.append({"Năm học": y, "Liên hệ": len(d), "Nhập học": n,
                         "Tỷ lệ nhập học (%)": round(100 * n / len(d), 1) if len(d) else 0.0})
        bang = pd.DataFrame(rows)
        text = f"Tỷ lệ nhập học{pv}: " + " → ".join(
            f"{r['Năm học']}: **{_pt(r['Tỷ lệ nhập học (%)'])}**" for r in rows) + "."
        return TraLoi(text, table=bang, chart=bang[["Năm học", "Tỷ lệ nhập học (%)"]].rename(
            columns={"Tỷ lệ nhập học (%)": "Số lượng"}))
    if t and tt:  # theo một trục: bảng trục × năm
        cot, ten_truc, thu_tu, gop = tt
        cols = {}
        for y in nams:
            b = _dem_gop(_col(ts_y[y], cot), ten_truc) if gop else _dem(_col(ts_y[y], cot), ten_truc)
            cols[y] = b.set_index(ten_truc)["Số lượng"]
        bang = pd.DataFrame(cols).fillna(0).astype(int)
        bang = bang.drop(index=[x for x in ("(trống)",) if x in bang.index])
        bang["Tổng"] = bang.sum(axis=1)
        if cot == "Khoi":
            bang = bang.sort_index(key=lambda s: s.map(_khoi_key))
        elif thu_tu:
            bang = bang.reindex([x for x in thu_tu if x in bang.index] +
                                [x for x in bang.index if x not in thu_tu])
        else:
            bang = bang.sort_values("Tổng", ascending=False)
        if len(nams) >= 2:
            bang[f"Tăng/giảm {nams[-1]}"] = [_tang(a, b) for a, b in
                                            zip(bang[nams[-2]], bang[nams[-1]])]
        bang = bang.rename_axis(ten_truc).reset_index()
        tien_to = "khối " if cot == "Khoi" else ""
        dau = [f"{y}: **{tien_to}{bang.sort_values(y, ascending=False).iloc[0][ten_truc]}** "
               f"({int(bang[y].max())})" for y in nams if len(bang) and bang[y].max() > 0]
        text = (f"{ten_tap[0].upper() + ten_tap[1:]}{pv} theo {ten_truc.split(' (')[0].lower()} "
                f"qua {len(nams)} năm học. Nhiều nhất — " + "; ".join(dau) + ".")
        top = bang.head(10 if gop else 15)
        chart = top.melt(ten_truc, nams, var_name="Năm học", value_name="Số lượng")
        return TraLoi(text, table=bang, chart=chart)
    # đếm theo năm (kèm các bước nếu hỏi tất cả liên hệ)
    rows = []
    for y in nams:
        d = ts_y[y]
        r = {"Năm học": y, ten_tap[0].upper() + ten_tap[1:]: len(d)}
        if not (tap and tap[1]):
            tt_ = _col(d, "TrangThai").value_counts()
            r.update({b: int(tt_.get(b, 0)) for b in TRANG_THAI})
        rows.append(r)
    bang = pd.DataFrame(rows)
    cot0 = bang.columns[1]
    bang["Tăng/giảm"] = ["—"] + [_tang(a, b) for a, b in zip(bang[cot0][:-1], bang[cot0][1:])]
    chuoi = " → ".join(f"{r['Năm học']}: **{r[cot0]}**" + (f" ({r['Tăng/giảm']})"
                                                         if r["Tăng/giảm"] != "—" else "")
                       for _, r in bang.iterrows())
    return TraLoi(f"{cot0}{pv} qua các năm học: {chuoi}.", table=bang,
                  chart=bang[["Năm học", cot0]].rename(columns={cot0: "Số lượng"}),
                  goi_y=[f"{cot0} theo khối qua các năm", "Tỷ lệ nhập học qua các năm"])


def so_sanh_khoi(c: Ctx, q: str, loc: Loc) -> TraLoi:
    tap = _tap_cua(q, loc)
    ten_tap = tap[2] if tap else "liên hệ"
    rows = []
    for k in loc.khoi_ds:
        d = loc_ts(c.ts, Loc(**{**loc.__dict__, "khoi": k, "khoi_ds": []}))
        tt_ = _col(d, "TrangThai").value_counts()
        rows.append({"Khối": k, "Liên hệ": len(d), **{b: int(tt_.get(b, 0)) for b in TRANG_THAI},
                     "Tỷ lệ nhập học (%)": round(100 * tt_.get("Nhập học", 0) / len(d), 1)
                     if len(d) else 0.0})
    bang = pd.DataFrame(rows)
    cot = {None: "Liên hệ"}.get(tap[1] if tap else None, tap[1] if tap else "Liên hệ")
    text = f"So sánh {ten_tap} năm học {c.nam_hoc}: " + ", ".join(
        f"khối {r['Khối']}: **{r[cot]}**" for _, r in bang.iterrows()) + "."
    return TraLoi(text, table=bang, chart=bang[["Khối", cot]].rename(columns={cot: "Số lượng"}))


# ------------------------------------------------------------------ điều phối
def tra_loi(cau_hoi: str, c: Ctx, truoc: str | None = None) -> TraLoi:
    q0 = chuan_hoa(cau_hoi)
    if not q0 or _co(q0, "giup", "huong dan", "lam duoc gi", "hoi gi", "help", "xin chao", "chao"):
        return huong_dan()
    q, da_ghep = ghep_ngu_canh(q0, truoc)
    try:
        r = _tra_loi(cau_hoi, q, c)
    except Exception as e:  # không để một câu hỏi lạ làm hỏng trợ lý
        r = TraLoi(f"Xin lỗi, mình chưa trả lời được câu này ({type(e).__name__}). "
                   "Bạn thử hỏi cách khác nhé.")
    r.hieu_la, r.da_ghep = q, da_ghep
    return r


def _tra_loi(cau_hoi: str, q_day_du: str, c: Ctx) -> TraLoi:
    nams, nhieu_nam, q = doc_nam(q_day_du, c)
    goc_khong_nam = re.sub(r"20\d{2}\s*[-/]\s*20\d{2}", " ", cau_hoi)
    loc = doc_loc(q, c.hom_nay, goc_khong_nam)
    if nhieu_nam:
        if _co(q, "tim", "tra cuu", "giay to", "hoc phi", "giu cho", "qua han"):
            c = c.nam(nams[-1])  # các câu này chỉ trả lời cho một năm
        else:
            return so_sanh_nam(c, q, loc, nams)
    elif nams:
        c = c.nam(nams[0])
    so = re.sub(r"\D", "", goc_khong_nam)
    if len(so) >= 8 and not re.search(r"\d{1,2}/\d{4}", goc_khong_nam):
        return tra_cuu(c, goc_khong_nam)
    if _co(q, "tim", "tim kiem", "tra cuu", "thong tin cua", "thong tin ve", "ho so cua"):
        return tra_cuu(c, goc_khong_nam)
    if _co(q, "giay to", "thieu ho so", "ho so con thieu", "bo sung", "chua nop du", "nop du",
           "con thieu giay"):
        return giay_to(c, loc)
    if _co(q, "qua han", "chua chuyen buoc", "lau chua", "can cham soc", "bo quen", "ton dong"):
        return tu_van_cu(c, q, loc)
    if _co(q, "tien", "hoc phi", "giu cho", "hoan phi", "dong phi", "thu phi", "doanh thu",
           "con no", "ke toan", "tai chinh", "chua coc", "dat cho") and \
            not (_tim_truc(q)[0] == "giu cho"):
        return tai_chinh(c, q, loc)
    if _co(q, "tong quan", "tinh hinh", "bao cao nhanh", "tom tat", "the nao", "ra sao") and \
            not loc.khoi_ds:
        return tong_quan(c, loc)
    if loc.khoi_ds:
        return so_sanh_khoi(c, q, loc)
    # câu chỉ gồm 2–5 chữ, không có ý định nào: nhiều khả năng là tên học sinh
    tu = goc_khong_nam.split()
    if 2 <= len(tu) <= 5 and not _co(q, *_Y_DINH) and not loc.mo_ta() and \
            all(re.fullmatch(r"[^\W\d_]+", w) for w in tu):
        viet_hoa = all(w[:1].isupper() for w in tu)  # trông như họ tên
        if r := tra_cuu(c, goc_khong_nam, bat_buoc=viet_hoa):
            return r
    if _co(q, "ty le", "hieu qua", "chuyen doi"):
        return ty_le(c, q, loc, loc_ts(c.ts, loc))

    tap = _tap_cua(q, loc)
    ts = loc_ts(c.ts, loc)
    if tap and tap[1]:
        ts = ts[_col(ts, "TrangThai") == tap[1]]
    ten_tap = tap[2] if tap else "liên hệ"
    if r := thong_ke(c, q, loc, ts, ten_tap):
        return r
    if tap or loc.mo_ta() or _co(q, "bao nhieu", "so luong", "dem", "danh sach", "liet ke") or nams:
        pv = f" ({loc.mo_ta()})" if loc.mo_ta() else ""
        text = f"Năm học {c.nam_hoc}: **{len(ts)}** {ten_tap}{pv}."
        if len(ts) and not (tap and tap[1]):
            tt = _col(ts, "TrangThai").value_counts()
            text += " Gồm " + ", ".join(f"{b.lower()} {int(tt.get(b, 0))}" for b in TRANG_THAI) + "."
        muon_ds = _co(q, "danh sach", "liet ke", "nhung ai", "ai", "nhung em", "la ai", "gom ai",
                      "hoc sinh nao", "nhung hoc sinh") or not _co(
            q, "bao nhieu", "so luong", "dem", "tong so")
        bang = _bang_ts(ts, tien=c.duoc("Kế toán")) if muon_ds and c.duoc("Data tuyển sinh") else None
        chart = None
        if not loc.khoi and len(ts):
            chart = _dem(_col(ts, "Khoi"), "Khối").sort_values(
                "Khối", key=lambda s: s.map(_khoi_key)).reset_index(drop=True)
        return TraLoi(text, table=bang, chart=chart,
                      goi_y=[f"Thống kê {ten_tap} theo nguồn", f"{ten_tap[0].upper() + ten_tap[1:]} "
                             "so với năm trước", "Còn khối 11 thì sao?"])
    # thử coi cả câu là tên học sinh
    if r := tra_cuu(c, goc_khong_nam, bat_buoc=False):
        return r
    t = huong_dan()
    t.text = "Mình chưa hiểu câu hỏi này. " + t.text
    return t
