from datetime import date

import pandas as pd

from tuyensinh import tro_ly

TS = pd.DataFrame([
    {"id": "1", "HoTenHS": "Trần Huy Long", "Khoi": "10", "PhanHe": "IEP", "TrangThai": "Nhập học",
     "GiuCho": "Đã giữ chỗ", "SoTienXacNhan": 5_000_000, "SDT": "0927666649",
     "NgayLienHe": "2026-07-05", "Nguon": "Mạng xã hội", "CheDo": "Nội trú",
     "TruongCu": "THCS Phước Thái", "TruongCu_Tinh": "Tỉnh Đồng Nai"},
    {"id": "2", "HoTenHS": "Lê Minh Anh", "Khoi": "6", "PhanHe": "", "TrangThai": "Tư vấn",
     "GiuCho": "", "SoTienXacNhan": None, "SDT": "0909000111", "NgayLienHe": "2026-06-01",
     "Nguon": "Hotline", "CheDo": "Bán trú", "TruongCu": "TH Lê Lợi", "TruongCu_Tinh": ""},
    {"id": "3", "HoTenHS": "Phạm Anh Thư", "Khoi": "10", "PhanHe": "ESL", "TrangThai": "Nộp hồ sơ",
     "GiuCho": "", "SoTienXacNhan": None, "SDT": "0911222333", "NgayLienHe": "2026-07-20",
     "Nguon": "Hotline", "CheDo": "Nội trú", "TruongCu": "thcs phuoc thai ",
     "TruongCu_Tinh": "Tỉnh Đồng Nai"},
])
NH = pd.DataFrame([
    {"id": "9", "TuyenSinhID": "1", "HoTen": "Trần Huy Long", "Khoi": "10", "PhanHe": "IEP",
     "LopHoc": "10A1", "HoSoDaNop": "", "TongDaThu": 10_000_000, "SoTienConLai": 2_000_000},
])


def ctx(quyen=None):
    return tro_ly.Ctx(TS, NH, "2026-2027", quyen=quyen, hom_nay=date(2026, 7, 25))


def test_kd():
    assert tro_ly.kd("Học Sinh  Đã nộp?") == "hoc sinh da nop"


def test_dem_theo_trang_thai_va_khoi():
    r = tro_ly.tra_loi("Có bao nhiêu học sinh nhập học khối 10?", ctx())
    assert "**1** học sinh nhập học (khối 10)" in r.text
    r = tro_ly.tra_loi("liên hệ khối 10 nội trú", ctx())
    assert "**2** liên hệ" in r.text and len(r.table) == 2


def test_thoi_gian_va_nguon():
    assert "**2** liên hệ (tháng 7/2026)" in tro_ly.tra_loi("liên hệ tháng 7", ctx()).text
    assert "**2** liên hệ (nguồn Hotline)" in tro_ly.tra_loi("lien he hotline", ctx()).text


def test_thong_ke_theo():
    r = tro_ly.tra_loi("thống kê theo nguồn", ctx())
    assert "chia theo nguồn" in r.text
    assert dict(zip(r.table["Nguồn"], r.table["Số lượng"])) == {"Hotline": 2, "Mạng xã hội": 1}


def test_tra_cuu_ten_va_sdt():
    r = tro_ly.tra_loi("tìm tran huy long", ctx())
    assert "**Trần Huy Long**" in r.text and "10A1" in r.text and "2.000.000 đ" in r.text
    assert "Trần Huy Long" in tro_ly.tra_loi("0927 666 649", ctx()).text
    r = tro_ly.tra_loi("tìm anh", ctx())
    assert "Tìm thấy **2**" in r.text


def test_quyen():
    r = tro_ly.tra_loi("tìm Trần Huy Long", ctx(quyen={"Tổng quan", "Data tuyển sinh"}))
    assert "Học phí" not in r.text and "Hồ sơ nhập học" not in r.text
    assert "không được xem" in tro_ly.tra_loi("học phí còn nợ", ctx(quyen={"Tổng quan"})).text
    assert "không được xem" in tro_ly.tra_loi("tìm Long", ctx(quyen={"Báo cáo"})).text


def test_tai_chinh_va_qua_han():
    c = ctx()
    assert "**1** học sinh đã nộp hồ sơ" in tro_ly.tra_loi("danh sách chưa giữ chỗ", c).text
    assert "**1** học sinh còn nợ" in tro_ly.tra_loi("hs còn nợ học phí", c).text
    assert "**1** liên hệ đang ở bước Tư vấn quá **14 ngày**" in \
        tro_ly.tra_loi("tư vấn quá hạn", c).text


def test_giay_to_va_khong_hieu():
    r = tro_ly.tra_loi("học sinh nào thiếu giấy tờ", ctx())
    assert "**1/1** hồ sơ" in r.text
    assert "chưa hiểu" in tro_ly.tra_loi("xyz qwe", ctx()).text


def test_xep_hang():
    r = tro_ly.tra_loi("Trường cũ nào có học sinh nhiều nhất", ctx())
    # gộp "THCS Phước Thái" và "thcs phuoc thai " thành một trường
    assert "**THCS Phước Thái** với **2** liên hệ" in r.text
    assert list(r.table.columns) == ["Hạng", "Trường cũ", "Số lượng"]
    r = tro_ly.tra_loi("tỉnh nào nhiều hs nhập học nhất", ctx())
    assert "**Tỉnh Đồng Nai** với **1** học sinh nhập học" in r.text
    r = tro_ly.tra_loi("nguồn nào ít nhất", ctx())
    assert "ít liên hệ nhất: **Mạng xã hội**" in r.text
    assert "chia theo tháng" in tro_ly.tra_loi("liên hệ theo tháng", ctx()).text
    # "khối 10" vẫn là bộ lọc
    assert "(khối 10)" in tro_ly.tra_loi("khối 10 có bao nhiêu liên hệ", ctx()).text
    r = tro_ly.tra_loi("liên hệ nguồn Ban TS đến trường tư vấn", ctx())
    assert r.text.startswith("Năm học 2026-2027: **0** liên hệ (nguồn Ban TS")
