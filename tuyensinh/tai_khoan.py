"""Tài khoản đăng nhập của app (khi chưa dùng được đăng nhập Microsoft 365).

Danh sách lưu trên list SharePoint DanhMuc_TaiKhoan; mật khẩu chỉ lưu dạng băm PBKDF2-SHA256
(không lưu mật khẩu gốc). Vai trò "Quản trị" vào được trang Cài đặt và quản lý tài khoản.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from .schema import QUYEN_MAC_DINH, TAI_KHOAN, TRANG, VAI_TRO
from .storage.base import Storage

ITER = 200_000


def bam(mat_khau: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mat_khau.encode(), bytes.fromhex(salt), ITER).hex()
    return f"pbkdf2${ITER}${salt}${h}"


def dung_mat_khau(mat_khau: str, chuoi_bam: str) -> bool:
    try:
        _, it, salt, h = str(chuoi_bam).split("$")
        tinh = hashlib.pbkdf2_hmac("sha256", mat_khau.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(tinh.hex(), h)
    except (ValueError, TypeError):
        return False


def _ten(v) -> str:
    return str(v or "").strip().lower()


def dang_hoat_dong(items: list[dict]) -> list[dict]:
    return [t for t in items if _ten(t.get("TenDangNhap")) and
            str(t.get("HoatDong") or "Có").strip() != "Không"]


def quyen(t: dict) -> list[str]:
    """Các trang tài khoản được vào (Quản trị: tất cả)."""
    vai = t.get("VaiTro") or VAI_TRO[1]
    if vai == "Quản trị":
        return list(TRANG)
    ds = [x.strip() for x in str(t.get("Quyen") or "").split(";") if x.strip() in TRANG]
    return ds or list(QUYEN_MAC_DINH.get(vai, ("Tổng quan",)))


def _phien(t: dict) -> dict:
    return {"id": str(t.get("id")), "HoTen": t.get("HoTen") or t.get("TenDangNhap"),
            "TenDangNhap": t.get("TenDangNhap"), "VaiTro": t.get("VaiTro") or VAI_TRO[1],
            "Quyen": quyen(t)}


def dang_nhap(items: list[dict], ten_dang_nhap: str, mat_khau: str) -> dict | None:
    """Trả về phiên đăng nhập nếu đúng tên đăng nhập + mật khẩu và đang hoạt động."""
    for t in dang_hoat_dong(items):
        if _ten(t.get("TenDangNhap")) == _ten(ten_dang_nhap) and \
                dung_mat_khau(mat_khau, t.get("MatKhau")):
            return _phien(t)
    return None


# ---------------------------------------------------------------- ghi nhớ trên máy (cookie)
def tao_ma_ghi_nho(t: dict, bi_mat: str, so_ngay: int = 30) -> str:
    """Mã lưu trong cookie: id.hạn.chữ-ký. Chữ ký gồm cả mật khẩu đã băm -> đổi mật khẩu
    là mọi máy đang ghi nhớ phải đăng nhập lại."""
    han = int(time.time()) + so_ngay * 86400
    sig = hmac.new(bi_mat.encode(), f"{t.get('id')}.{han}.{t.get('MatKhau')}".encode(),
                   hashlib.sha256).hexdigest()[:40]
    return f"{t.get('id')}.{han}.{sig}"


def tu_ma_ghi_nho(items: list[dict], ma: str, bi_mat: str) -> dict | None:
    try:
        tid, han, sig = str(ma).split(".")
        if int(han) < time.time():
            return None
    except ValueError:
        return None
    for t in dang_hoat_dong(items):
        if str(t.get("id")) == tid:
            dung = hmac.new(bi_mat.encode(), f"{tid}.{han}.{t.get('MatKhau')}".encode(),
                            hashlib.sha256).hexdigest()[:40]
            return _phien(t) if hmac.compare_digest(dung, sig) else None
    return None


def luu(storage: Storage, items: list[dict], ho_ten: str, ten_dang_nhap: str,
        vai_tro: str, mat_khau: str | None = None, hoat_dong: bool = True,
        item_id: str | None = None, trang: list[str] | None = None) -> dict:
    """Thêm / sửa tài khoản. Tên đăng nhập không được trùng."""
    ten = _ten(ten_dang_nhap)
    if not ten or not ho_ten.strip():
        raise ValueError("Cần nhập **Họ tên** và **Tên đăng nhập**.")
    if any(_ten(t.get("TenDangNhap")) == ten and str(t.get("id")) != str(item_id)
           for t in items):
        raise ValueError(f"Tên đăng nhập **{ten}** đã có.")
    if not item_id and not mat_khau:
        raise ValueError("Tài khoản mới cần **mật khẩu**.")
    if mat_khau is not None and mat_khau and len(mat_khau) < 6:
        raise ValueError("Mật khẩu cần ít nhất **6 ký tự**.")
    trang = list(TRANG) if vai_tro == "Quản trị" else [
        x for x in (trang or QUYEN_MAC_DINH.get(vai_tro, ())) if x in TRANG]
    data = {"HoTen": ho_ten.strip(), "TenDangNhap": ten, "VaiTro": vai_tro,
            "HoatDong": "Có" if hoat_dong else "Không", "Quyen": "; ".join(trang)}
    if mat_khau:
        data["MatKhau"] = bam(mat_khau)
    if item_id:
        return storage.update_item(TAI_KHOAN.name, item_id, data)
    return storage.create_item(TAI_KHOAN.name, data)


def doi_mat_khau(storage: Storage, item_id: str, cu: str, moi: str, items: list[dict]) -> dict:
    tk = next((t for t in items if str(t.get("id")) == str(item_id)), None)
    if tk is None or not dung_mat_khau(cu, tk.get("MatKhau")):
        raise ValueError("Mật khẩu hiện tại không đúng.")
    if len(moi) < 6:
        raise ValueError("Mật khẩu mới cần ít nhất **6 ký tự**.")
    return storage.update_item(TAI_KHOAN.name, item_id, {"MatKhau": bam(moi)})
