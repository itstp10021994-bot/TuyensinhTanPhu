import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import tai_khoan  # noqa: E402
from tuyensinh.schema import TAI_KHOAN  # noqa: E402
from tuyensinh.storage.local import LocalStorage  # noqa: E402


def test_bam_va_kiem_tra():
    h = tai_khoan.bam("matkhau123")
    assert "matkhau123" not in h and tai_khoan.dung_mat_khau("matkhau123", h)
    assert not tai_khoan.dung_mat_khau("sai", h) and not tai_khoan.dung_mat_khau("x", "")


def test_tao_dang_nhap_doi_mat_khau(tmp_path):
    st = LocalStorage(str(tmp_path / "t.db"))
    tk = tai_khoan.luu(st, [], "Lê Thiên An", "An.Le", "Quản trị", "abc123")
    items = st.list_items(TAI_KHOAN.name)
    with pytest.raises(ValueError):  # trùng tên đăng nhập
        tai_khoan.luu(st, items, "Khác", "an.le", "Tuyển sinh", "xyz789")
    u = tai_khoan.dang_nhap(items, " AN.LE ", "abc123")
    assert u["HoTen"] == "Lê Thiên An" and u["VaiTro"] == "Quản trị"
    assert tai_khoan.dang_nhap(items, "an.le", "sai") is None
    tai_khoan.doi_mat_khau(st, tk["id"], "abc123", "moi4567", items)
    items = st.list_items(TAI_KHOAN.name)
    assert tai_khoan.dang_nhap(items, "an.le", "moi4567")
    tai_khoan.luu(st, items, "Lê Thiên An", "an.le", "Quản trị", None, False, tk["id"])
    assert tai_khoan.dang_nhap(st.list_items(TAI_KHOAN.name), "an.le", "moi4567") is None


def test_phan_quyen_va_ghi_nho(tmp_path):
    st = LocalStorage(str(tmp_path / "t.db"))
    tai_khoan.luu(st, [], "Kế toán A", "kt", "Kế toán", "abc123")
    tai_khoan.luu(st, st.list_items(TAI_KHOAN.name), "Tuyển sinh B", "ts", "Tuyển sinh",
                  "abc123", trang=["Data tuyển sinh", "Báo cáo"])
    items = st.list_items(TAI_KHOAN.name)
    kt = tai_khoan.dang_nhap(items, "kt", "abc123")
    assert "Kế toán" in kt["Quyen"] and "Data tuyển sinh" not in kt["Quyen"]
    assert tai_khoan.dang_nhap(items, "ts", "abc123")["Quyen"] == ["Data tuyển sinh", "Báo cáo"]
    t = next(x for x in items if x["TenDangNhap"] == "kt")
    ma = tai_khoan.tao_ma_ghi_nho(t, "bi-mat")
    assert tai_khoan.tu_ma_ghi_nho(items, ma, "bi-mat")["HoTen"] == "Kế toán A"
    assert tai_khoan.tu_ma_ghi_nho(items, ma, "khac") is None
    assert tai_khoan.tu_ma_ghi_nho(items, ma[:-1] + "0", "bi-mat") is None
    tai_khoan.doi_mat_khau(st, t["id"], "abc123", "moi4567", items)  # đổi mật khẩu -> mã hết hiệu lực
    assert tai_khoan.tu_ma_ghi_nho(st.list_items(TAI_KHOAN.name), ma, "bi-mat") is None
