"""Bảo mật: che bí mật trong thông báo lỗi, khóa tạm khi đăng nhập sai nhiều lần."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import tai_khoan  # noqa: E402
from tuyensinh.ui import an_bi_mat  # noqa: E402


def test_che_bi_mat_trong_loi():
    m = ("HTTPSConnectionPool(host='prod-12.logic.azure.com', port=443): Max retries exceeded "
         "with url: /workflows/0123456789abcdef0123456789abcdef/triggers/manual/paths/invoke?"
         "api-version=2016-06-01&sp=%2Ftriggers&sv=1.0&sig=AbCdEf123_xyz "
         '{"key": "bi-mat-flow"} Authorization: Bearer eyJ0eXAi.abc-def')
    out = an_bi_mat(m)
    for bi_mat in ("AbCdEf123_xyz", "bi-mat-flow", "eyJ0eXAi", "0123456789abcdef0123"):
        assert bi_mat not in out
    assert "api-version=2016-06-01" in out and "sig=***" in out


def test_khoa_tam_khi_sai_nhieu_lan():
    ten = "kiem_tra_khoa"
    tai_khoan.xoa_sai(ten)
    for _ in range(tai_khoan.SAI_TOI_DA - 1):
        tai_khoan.ghi_sai(ten)
    assert tai_khoan.con_khoa(ten) == 0
    tai_khoan.ghi_sai(ten)
    assert 0 < tai_khoan.con_khoa(ten) <= tai_khoan.KHOA_GIAY + 1
    assert tai_khoan.con_khoa("KIEM_TRA_KHOA ") > 0  # không phân biệt hoa thường / khoảng trắng
    tai_khoan.xoa_sai(ten)
    assert tai_khoan.con_khoa(ten) == 0


def test_kiem_tra_o_nhap():
    from tuyensinh.ui import kiem_tra_o, loai_o_nhap
    assert loai_o_nhap("DienThoaiMe") == "sdt" and loai_o_nhap("KhanCap_SDT") == "sdt"
    assert loai_o_nhap("EmailCha") == "email" and loai_o_nhap("CanCuocNGH") == "can_cuoc"
    assert loai_o_nhap("HoTen") == ""
    assert kiem_tra_o("sdt", "0901 234 567") == "" and kiem_tra_o("sdt", "12345")
    assert kiem_tra_o("email", "a@b.vn") == "" and kiem_tra_o("email", "ab.vn")
    assert kiem_tra_o("can_cuoc", "079 215 016 553") == "" and kiem_tra_o("can_cuoc", "123")
    assert kiem_tra_o("sdt", "") == ""
