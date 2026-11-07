"""Tin tuyển sinh (nguồn chính thống) và dự báo tuyển sinh mùa tới."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import du_bao as DB  # noqa: E402
from tuyensinh import tin_tuc as TT  # noqa: E402

RSS = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>GD</title>
<item><title>TP.HCM công bố chỉ tiêu tuyển sinh lớp 10 năm học 2027-2028</title>
<link>https://bao.gov.vn/tuyen-sinh-lop-10.html</link><pubDate>Mon, 02 Nov 2026 08:00:00 +0700</pubDate>
<description>&lt;p&gt;Sở GD&amp;ĐT công bố&lt;/p&gt;</description></item>
<item><title>Đại học X công bố phương án tuyển sinh 2027</title>
<link>https://bao.gov.vn/dai-hoc.html</link></item>
<item><title>Giá xăng hôm nay</title><link>https://bao.gov.vn/xang.html</link></item>
<item><title>Tuyển sinh đầu cấp: link lạ</title><link>https://lua-dao.com/x</link></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Lịch thi vào lớp 6 trường chuyên</title>
<link rel="alternate" href="/bai/lop-6"/><updated>2026-10-30T10:00:00Z</updated></entry></feed>"""

TRANG_CO_RSS = """<html><head><link rel="alternate" type="application/rss+xml" href="/rss/giao-duc.rss">
</head><body>trang chủ</body></html>"""

TRANG_KHONG_RSS = """<html><body>
<a href="/tin/1">Hướng dẫn tuyển sinh vào lớp 1, lớp 6 năm học 2027-2028 trên địa bàn thành phố</a>
<a href="/tin/2">Hội nghị tổng kết công tác thi đua khen thưởng năm 2026 của ngành</a>
<a href="https://khac.vn/x">Tuyển sinh lớp 10 — trang không chính thống của bên thứ ba</a>
<a href="javascript:alert(1)">Tuyển sinh lớp 10 năm học mới nhất bấm vào đây ngay</a>
</body></html>"""


class _Resp:
    def __init__(self, body, ct):
        self.body, self.headers = body.encode() if isinstance(body, str) else body, \
            {"Content-Type": ct}

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Session:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kw):
        if url not in self.pages:
            raise ConnectionError(url)
        return _Resp(*self.pages[url])


def test_doc_rss_loc_tin_tuyen_sinh_pho_thong_va_cung_mien():
    s = _Session({"https://bao.gov.vn/rss": (RSS, "application/rss+xml")})
    tins, tt = TT.lay_tin((("Báo", "https://bao.gov.vn/rss"),), session=s)
    assert tt == {"Báo": ""}
    assert [t.tieu_de for t in tins] == [
        "TP.HCM công bố chỉ tiêu tuyển sinh lớp 10 năm học 2027-2028"]
    assert tins[0].ngay.year == 2026 and tins[0].tom_tat == "Sở GD&ĐT công bố"


def test_trang_co_khai_bao_rss_va_atom():
    s = _Session({"https://so.edu.vn/": (TRANG_CO_RSS, "text/html; charset=utf-8"),
                  "https://so.edu.vn/rss/giao-duc.rss": (ATOM, "application/atom+xml")})
    tins, _ = TT.lay_tin((("Sở", "https://so.edu.vn/"),), session=s)
    assert [(t.tieu_de, t.lien_ket) for t in tins] == [
        ("Lịch thi vào lớp 6 trường chuyên", "https://so.edu.vn/bai/lop-6")]


def test_trang_khong_rss_lay_lien_ket_bai_viet_va_nguon_loi():
    s = _Session({"https://www.bo.gov.vn/": (TRANG_KHONG_RSS, "text/html")})
    tins, tt = TT.lay_tin((("Bộ", "https://www.bo.gov.vn/"), ("Hỏng", "https://hong.vn/")),
                          session=s)
    assert [t.lien_ket for t in tins] == ["https://www.bo.gov.vn/tin/1"]
    assert tt["Bộ"] == "" and tt["Hỏng"] == "ConnectionError"


def test_nguon_tu_cau_hinh():
    assert TT.nguon_tu_cau_hinh(["Sở|https://a.vn/", {"ten": "B", "url": "https://b.vn"},
                                 "x|ftp://c"]) == (("Sở", "https://a.vn/"), ("B", "https://b.vn"))
    assert TT.nguon_tu_cau_hinh(None) == TT.NGUON_MAC_DINH


def _ts(rows):
    return pd.DataFrame(rows, columns=["NamHoc", "NgayLienHe", "TrangThai", "Khoi"])


def test_du_bao_theo_cung_ky_nam_truoc():
    rows = []
    # mùa 2026-2027: 100 liên hệ, 40 trước 01/11/2025, 25 nhập học
    for i in range(100):
        d = date(2025, 10, 1) if i < 40 else date(2026, 4, 1)
        rows.append(("2026-2027", d, "Nhập học" if i < 25 else "Tư vấn", "10" if i % 2 else "6"))
    # mùa 2027-2028: 50 liên hệ đến 01/11/2026
    rows += [("2027-2028", date(2026, 10, 15), "Tư vấn", "10")] * 50
    kq = DB.du_bao(_ts(rows), date(2026, 11, 1))
    assert kq.nam_hoc == "2027-2028" and kq.lh_den_nay == 50
    assert kq.lh_cung_ky == 40 and kq.lh_nam_truoc == 100
    assert kq.du_bao_lh == 125  # 50 × 100 / 40
    assert kq.ty_le_nh == 0.25 and kq.du_bao_nh == 31
    assert kq.bon_tuan_toi == 0  # năm trước không có liên hệ nào trong 4 tuần tới
    assert set(kq.duong["Chuỗi"]) == {"Mùa 2027-2028 (thực tế)", "Mùa 2026-2027",
                                      "Mùa 2027-2028 (dự báo)"}
    assert kq.duong[kq.duong["Chuỗi"].str.contains("dự báo")]["Liên hệ cộng dồn"].max() == 125
    assert kq.theo_khoi["Dự báo liên hệ"].sum() >= 120


def test_du_bao_dau_mua_va_chi_co_nam_nay():
    rows = [("2026-2027", date(2026, 3, 1), "Nhập học", "10")] * 30
    kq = DB.du_bao(_ts(rows), date(2026, 11, 1))  # mùa 2027-2028 chưa có liên hệ
    assert kq.lh_den_nay == 0 and kq.du_bao_lh == 30 and kq.du_bao_nh == 30
    kq = DB.du_bao(_ts(rows), date(2026, 3, 29))  # chỉ có năm nay: theo tốc độ 8 tuần
    assert kq.nam_hoc == "2026-2027" and kq.lh_cung_ky is None and kq.du_bao_lh > 30
    assert DB.nam_hoc_dang_tuyen(date(2026, 8, 31)) == "2026-2027"
    assert DB.nam_hoc_dang_tuyen(date(2026, 9, 1)) == "2027-2028"
    assert DB.du_bao(_ts([]), date(2026, 11, 1)).du_bao_lh == 0
