"""Tin tuyển sinh từ nguồn chính thống (Bộ GD&ĐT, Sở GD&ĐT TP.HCM, báo của Bộ, Báo Chính phủ).

Mỗi nguồn là một địa chỉ (đổi được trong Secrets: TIN_TUC_NGUON). App đọc theo thứ tự:
1. địa chỉ là RSS / Atom -> đọc trực tiếp;
2. trang web có khai báo RSS (<link rel="alternate" ...>) -> đọc RSS đó;
3. không có RSS -> lấy các liên kết bài viết trên trang có từ khóa tuyển sinh.
Chỉ giữ tin về tuyển sinh phổ thông (lớp 1, 6, 10, đầu cấp…), chỉ liên kết cùng tên miền với nguồn.
App chỉ hiện tiêu đề + liên kết về bài gốc; không lưu, không chép nội dung bài.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .danh_muc import fold

NGUON_MAC_DINH = (
    ("Bộ Giáo dục và Đào tạo", "https://moet.gov.vn/"),
    ("Sở GD&ĐT TP. Hồ Chí Minh", "https://hcm.edu.vn/"),
    ("Báo Giáo dục & Thời đại (Bộ GD&ĐT)", "https://giaoducthoidai.vn/"),
    ("Báo Điện tử Chính phủ", "https://baochinhphu.vn/"),
)
TOI_DA_BYTE = 3_000_000
TIMEOUT = (5, 10)
UA = "TuyenSinhTanPhu/2.0 (app quan ly tuyen sinh truong hoc)"

# tin tuyển sinh (đã bỏ dấu); tin chỉ nói về đại học / cao đẳng bị bỏ trừ khi có từ phổ thông
TU_TUYEN_SINH = ("tuyen sinh", "thi vao lop", "vao lop 10", "lop 10", "vao lop 6", "lop 6",
                 "vao lop 1", "dau cap", "nhap hoc", "chi tieu", "xet tuyen", "phan tuyen",
                 "thi tuyen")
TU_PHO_THONG = ("lop 1", "lop 6", "lop 10", "dau cap", "pho thong", "thpt", "thcs", "tieu hoc",
                "mam non", "hoc sinh", "truong chuyen", "chuyen")
TU_DAI_HOC = ("dai hoc", "cao dang", "thac si", "tien si", "sau dai hoc")


@dataclass
class Tin:
    tieu_de: str
    lien_ket: str
    nguon: str
    ngay: datetime | None = None
    tom_tat: str = ""


def la_tin_tuyen_sinh(tieu_de: str, tom_tat: str = "") -> bool:
    f = fold(f"{tieu_de} {tom_tat}")
    if not any(k in f for k in TU_TUYEN_SINH):
        return False
    t = fold(tieu_de)
    return not (any(k in t for k in TU_DAI_HOC) and not any(k in t for k in TU_PHO_THONG))


def _goc(host: str) -> str:
    """Tên miền gốc: www.moet.gov.vn -> moet.gov.vn."""
    return host.lower().removeprefix("www.")


def _cung_mien(url: str, nguon: str) -> bool:
    u, n = urlparse(url), urlparse(nguon)
    if u.scheme not in ("http", "https"):
        return False
    h, g = _goc(u.hostname or ""), _goc(n.hostname or "")
    return h == g or h.endswith("." + g)


def _sach(s: str | None, toi_da: int = 300) -> str:
    s = re.sub(r"<[^>]+>", " ", unescape(str(s or "")))
    return " ".join(s.split())[:toi_da]


def _ngay(v: str | None) -> datetime | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        d = parsedate_to_datetime(v)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _ten(e) -> str:
    return e.tag.rsplit("}", 1)[-1].lower()


def doc_feed(xml: bytes | str, nguon: str, ten_nguon: str) -> list[Tin] | None:
    """RSS 2.0 / Atom -> danh sách tin (None nếu không phải feed)."""
    try:
        goc = ET.fromstring(xml)
    except ET.ParseError:
        return None
    if _ten(goc) not in ("rss", "feed", "rdf"):
        return None
    out = []
    for it in goc.iter():
        if _ten(it) not in ("item", "entry"):
            continue
        con = {_ten(c): c for c in it}
        tieu_de = _sach(con["title"].text if "title" in con else "")
        link = ""
        if "link" in con:
            link = (con["link"].text or "").strip() or con["link"].get("href", "")
        for c in it:  # Atom: nhiều <link>, ưu tiên rel="alternate"
            if _ten(c) == "link" and c.get("href") and c.get("rel", "alternate") == "alternate":
                link = c.get("href")
                break
        mo_ta = next((con[k] for k in ("description", "summary") if k in con), None)
        tom = _sach(mo_ta.text if mo_ta is not None else "")
        ngay = None
        for k in ("pubdate", "published", "updated", "date"):
            if k in con:
                ngay = _ngay(con[k].text)
                if ngay:
                    break
        link = urljoin(nguon, link)
        if tieu_de and link and _cung_mien(link, nguon):
            out.append(Tin(tieu_de, link, ten_nguon, ngay, tom))
    return out


class _TrangHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.feed_urls: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._a: str | None = None
        self._chu: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "alternate" in (a.get("rel") or "") and \
                re.search(r"(rss|atom)\+xml", a.get("type") or "") and a.get("href"):
            self.feed_urls.append(a["href"])
        elif tag == "a" and a.get("href"):
            self._a, self._chu = a["href"], []
            if a.get("title"):
                self._chu.append(a["title"])

    def handle_data(self, data):
        if self._a is not None:
            self._chu.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append((self._a, " ".join(" ".join(self._chu).split())))
            self._a = None


def doc_trang(html: str, nguon: str, ten_nguon: str) -> tuple[list[Tin], list[str]]:
    """Trang HTML -> (tin từ các liên kết bài viết, địa chỉ RSS khai báo trên trang)."""
    p = _TrangHTML()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 — HTML hỏng: lấy được bao nhiêu dùng bấy nhiêu
        pass
    out, da = [], set()
    for href, chu in p.links:
        link = urljoin(nguon, href)
        tieu_de = _sach(chu, 250)
        if len(tieu_de) < 20 or link in da or not _cung_mien(link, nguon):
            continue
        da.add(link)
        out.append(Tin(tieu_de, link, ten_nguon))
    feeds = [urljoin(nguon, f) for f in p.feed_urls if _cung_mien(urljoin(nguon, f), nguon)]
    return out, feeds


def _tai(session, url: str) -> tuple[bytes, str]:
    with session.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent": UA},
                     allow_redirects=True) as r:
        r.raise_for_status()
        buf = b""
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > TOI_DA_BYTE:
                break
        return buf, (r.headers.get("Content-Type") or "").lower()


def _giai_ma(b: bytes) -> str:
    m = re.search(rb'charset=["\']?([\w-]+)', b[:2000])
    try:
        return b.decode(m.group(1).decode() if m else "utf-8", errors="replace")
    except LookupError:
        return b.decode("utf-8", errors="replace")


def lay_nguon(session, ten: str, url: str) -> tuple[list[Tin], str]:
    """Tin tuyển sinh của một nguồn + trạng thái ("" nếu đọc được)."""
    try:
        b, loai = _tai(session, url)
        tins = doc_feed(b, url, ten) if ("xml" in loai or b.lstrip()[:5] in (b"<?xml", b"<rss ")) \
            else None
        if tins is None:
            trang, feeds = doc_trang(_giai_ma(b), url, ten)
            tins = None
            for f in feeds[:3]:  # trang có khai báo RSS
                try:
                    fb, _ = _tai(session, f)
                    tins = (tins or []) + (doc_feed(fb, f, ten) or [])
                except Exception:  # noqa: BLE001
                    continue
            if not tins or not any(la_tin_tuyen_sinh(t.tieu_de, t.tom_tat) for t in tins):
                tins = trang
        return [t for t in tins if la_tin_tuyen_sinh(t.tieu_de, t.tom_tat)], ""
    except Exception as e:  # noqa: BLE001 — một nguồn lỗi không ảnh hưởng nguồn khác
        return [], type(e).__name__


def lay_tin(nguon: tuple[tuple[str, str], ...] = NGUON_MAC_DINH, session=None,
            toi_da: int = 40) -> tuple[list[Tin], dict[str, str]]:
    """Đọc song song mọi nguồn. Trả về (tin mới nhất trước, {nguồn: lỗi hoặc ""})."""
    if session is None:
        import requests
        session = requests.Session()
    with ThreadPoolExecutor(max_workers=max(1, len(nguon))) as pool:
        kq = list(pool.map(lambda n: lay_nguon(session, *n), nguon))
    tins, trang_thai, da = [], {}, set()
    for (ten, _), (ds, loi) in zip(nguon, kq):
        trang_thai[ten] = loi
        for t in ds:
            if t.lien_ket not in da:
                da.add(t.lien_ket)
                tins.append(t)
    moc = datetime(1970, 1, 1, tzinfo=timezone.utc)
    tins.sort(key=lambda t: t.ngay or moc, reverse=True)  # tin có ngày lên trước
    return tins[:toi_da], trang_thai


def nguon_tu_cau_hinh(v) -> tuple[tuple[str, str], ...]:
    """Secrets TIN_TUC_NGUON: ["Tên|https://...", ...] hoặc [{ten=..., url=...}]."""
    out = []
    for x in v or ():
        if isinstance(x, str) and "|" in x:
            ten, url = x.split("|", 1)
        elif isinstance(x, dict):
            ten, url = x.get("ten", ""), x.get("url", "")
        else:
            continue
        if urlparse(url.strip()).scheme in ("http", "https"):
            out.append((ten.strip() or urlparse(url).hostname, url.strip()))
    return tuple(out) or NGUON_MAC_DINH
