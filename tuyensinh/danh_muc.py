"""Danh mục dùng chung: địa giới hành chính mới (Tỉnh → Phường/Xã), dân tộc, tôn giáo, ...
và danh mục trường học theo phường/xã.

- danh_muc.json: cập nhật địa giới bằng `python scripts/update_danh_muc.py`
- truong_hoc.csv: danh mục trường (Tỉnh/Thành phố, Phường/Xã, Tên trường, Cấp học),
  nhập bằng `python scripts/import_truong_hoc.py <file Excel/CSV>`
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .schema import Field

_DIR = Path(__file__).parent / "data"
_PATH = _DIR / "danh_muc.json"
TRUONG_CSV = _DIR / "truong_hoc.csv"  # từ OpenStreetMap (workflow hằng tháng ghi đè)
# Trường bổ sung từ dữ liệu tuyển sinh (không có trên OpenStreetMap) — không bị ghi đè
TRUONG_BO_SUNG_CSV = _DIR / "truong_hoc_bo_sung.csv"


def _truong_rows():
    for path in (TRUONG_CSV, TRUONG_BO_SUNG_CSV):
        if path.exists():
            with path.open(encoding="utf-8-sig") as fh:
                yield from csv.DictReader(fh)


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def fold(s: str) -> str:
    """Chuỗi so khớp: bỏ dấu, chữ thường, gộp khoảng trắng."""
    return _fold(str(s or ""))


@lru_cache(maxsize=1 << 16)  # cùng một chuỗi được so khớp rất nhiều lần (lọc, tìm, danh mục)
def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", s)


def normalize_tinh(v: str) -> str:
    """Tên tỉnh cũ (vd "Tỉnh Đồng Nai") → tên hiện hành ("Thành phố Đồng Nai")."""
    return load().get("tinh_cu", {}).get(v, v) if v else v


def xa_of(tinh: str) -> list[str]:
    return list(load()["xa_theo_tinh"].get(normalize_tinh(tinh or ""), []))


@lru_cache(maxsize=1)
def _truong_cap() -> dict:
    """{(fold tỉnh, fold xã, fold tên): cấp học}."""
    out = {}
    for row in _truong_rows():
        out[(fold(normalize_tinh(row.get("Tỉnh/Thành phố") or "")),
             fold(row.get("Phường/Xã") or ""), fold(row.get("Tên trường") or ""))] = \
            (row.get("Cấp học") or "").strip()
    return out


@lru_cache(maxsize=1)
def _truong_cap_tinh() -> dict:
    """{(fold tỉnh, fold tên): cấp học} — tra khi không khớp đúng phường/xã."""
    out = {}
    for (t, _, n), c in _truong_cap().items():
        out.setdefault((t, n), c)
    return out


def cap_hoc(ten: str, tinh: str = "", xa: str = "") -> str:
    t, n = fold(normalize_tinh(tinh)), fold(ten)
    return _truong_cap().get((t, fold(xa), n)) or _truong_cap_tinh().get((t, n), "")


def cap_truoc_khoi(khoi) -> tuple[str, ...]:
    """Cấp học của trường cũ thường gặp với khối đăng ký (vd khối 10 → THCS)."""
    m = re.match(r"\s*(\d{1,2})", str(khoi or ""))  # "10", "10A1" -> 10
    if not m:
        return ()
    k = int(m.group(1))
    if k <= 1:
        return ("Mầm non",)
    if k <= 6:
        return ("Tiểu học",)
    if k <= 10:
        return ("THCS",)
    return ("THPT",)


@lru_cache(maxsize=1)
def _truong_index() -> dict:
    """{(fold tỉnh, fold xã): [tên trường]} và {(fold tỉnh, ""): [...]} từ truong_hoc.csv."""
    idx: dict[tuple[str, str], dict[str, None]] = {}  # dict giữ thứ tự, tra trùng O(1)
    for row in _truong_rows():
        ten = (row.get("Tên trường") or "").strip()
        if not ten:
            continue
        t = fold(normalize_tinh((row.get("Tỉnh/Thành phố") or "").strip()))
        x = fold(row.get("Phường/Xã") or "")
        for k in ((t, x), (t, "")):
            idx.setdefault(k, {})[ten] = None
    return {k: list(v) for k, v in idx.items()}


def truong_hoc(tinh: str, xa: str = "") -> list[str]:
    """Trường trong danh mục thuộc phường/xã (hoặc cả tỉnh nếu chưa chọn xã)."""
    return list(_truong_index().get((fold(normalize_tinh(tinh)), fold(xa)), []))


def options_for(f: Field, record: dict | None = None) -> list[str]:
    """Trả về danh sách lựa chọn cho trường `f`.

    "@ten" lấy danh mục trong danh_muc.json; "@xa:TruongTinh" lấy phường/xã theo tỉnh ở
    trường TruongTinh của `record`; "@truong:TruongTinh,TruongXa" lấy trường học theo xã.
    """
    opts = f.options
    if isinstance(opts, tuple):
        return list(opts)
    name = opts.lstrip("@")
    record = record or {}
    if name == "nam_hoc":
        from . import config

        return config.school_years()
    if name.startswith("xa:"):
        return xa_of(record.get(name[3:]) or "")
    if name.startswith("truong:"):
        tinh_key, xa_key = name[7:].split(",")
        return truong_hoc(record.get(tinh_key) or "", record.get(xa_key) or "")
    return list(load()[name])


def parents(f: Field) -> list[str]:
    """Các trường mà lựa chọn của `f` phụ thuộc vào (theo thứ tự)."""
    if isinstance(f.options, str):
        if f.options.startswith("@xa:"):
            return [f.options[4:]]
        if f.options.startswith("@truong:"):
            return f.options[8:].split(",")
    return []


def lam_nong() -> None:
    """Dựng sẵn các chỉ mục danh mục (gọi nền lúc khởi động) để lần mở hồ sơ đầu không chờ."""
    load()
    _truong_cap()
    _truong_cap_tinh()
    _truong_index()
