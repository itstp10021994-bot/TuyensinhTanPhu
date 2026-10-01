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


# ------------------------------------------------------------------ nhiều năm, ngữ cảnh
TS_ALL = pd.concat([TS.assign(NamHoc="2026-2027"), pd.DataFrame([
    {"id": "11", "NamHoc": "2025-2026", "HoTenHS": "Võ Thị Hoa", "Khoi": "10", "TrangThai": "Nhập học",
     "NgayLienHe": "2025-07-03", "Nguon": "Hotline", "GioiTinh": "Nữ"},
    {"id": "12", "NamHoc": "2025-2026", "HoTenHS": "Đỗ Minh", "Khoi": "6", "TrangThai": "Tư vấn",
     "NgayLienHe": "2025-04-03", "Nguon": "Hotline", "GioiTinh": "Nam"},
])], ignore_index=True)


def ctx_all():
    return tro_ly.Ctx(TS, NH, "2026-2027", hom_nay=date(2026, 7, 25), ts_all=TS_ALL,
                      nh_all=NH.assign(NamHoc="2026-2027"))


def test_chuan_hoa_dong_nghia_va_go_sai():
    assert tro_ly.chuan_hoa("bn hs trúng tuyển lớp 10") == "bao nhieu hoc sinh nhap hoc khoi 10"
    assert tro_ly.chuan_hoa("thongg kê theo nguonn") == "thong ke theo nguon"
    assert tro_ly.chuan_hoa("Hoàng") == "hoang"  # tên riêng (viết hoa) không bị sửa


def test_so_sanh_nam():
    c = ctx_all()
    r = tro_ly.tra_loi("nhập học so với năm trước", c)
    assert "2025-2026: **1** → 2026-2027: **1** (+0,0%)" in r.text
    r = tro_ly.tra_loi("năm học 2025-2026 có bao nhiêu liên hệ", c)
    assert r.text.startswith("Năm học 2025-2026: **2** liên hệ")
    r = tro_ly.tra_loi("liên hệ theo khối qua các năm", c)
    assert list(r.table.columns[:3]) == ["Khối", "2025-2026", "2026-2027"]
    assert r.chart.shape[1] == 3  # biểu đồ nhóm theo năm
    # cùng kỳ: tháng 7/2026 so với tháng 7/2025
    r = tro_ly.tra_loi("liên hệ tháng 7 so với năm trước", c)
    assert "2025-2026: **1** → 2026-2027: **2**" in r.text
    assert "2025-2026" in tro_ly.tra_loi("Võ Thị Hoa", c).text  # tìm ở năm khác


def test_ngu_canh_va_gioi_tinh():
    c = ctx_all()
    r1 = tro_ly.tra_loi("bao nhiêu học sinh nhập học khối 10", c)
    r2 = tro_ly.tra_loi("còn khối 6 thì sao?", c, r1.hieu_la)
    assert r2.da_ghep and "**0** học sinh nhập học (khối 6)" in r2.text
    r3 = tro_ly.tra_loi("năm trước?", c, r2.hieu_la)
    assert r3.text.startswith("Năm học 2025-2026: **0** học sinh nhập học (khối 6)")
    r4 = tro_ly.tra_loi("học sinh nữ khối 10", c, r3.hieu_la)  # chỉ có bộ lọc -> hỏi tiếp
    assert r4.da_ghep and "(khối 10, học sinh nữ)" in r4.text and "2025-2026" in r4.text
    r5 = tro_ly.tra_loi("danh sách tư vấn khối 6", c, r4.hieu_la)
    assert not r5.da_ghep  # câu hỏi mới có ý định riêng, không ghép
    c2 = tro_ly.Ctx(TS_ALL[TS_ALL.NamHoc == "2025-2026"], NH.iloc[0:0], "2025-2026",
                    hom_nay=date(2026, 7, 25), ts_all=TS_ALL)
    assert "**1** liên hệ (học sinh nữ)" in tro_ly.tra_loi("học sinh nữ", c2).text
    assert tro_ly.tra_loi("Nguyễn Văn Nam", c).text.startswith("Không tìm thấy")


def test_ty_le_va_so_sanh_khoi():
    c = ctx()
    r = tro_ly.tra_loi("tỷ lệ nhập học", c)
    assert "**33,3%** (1/3 liên hệ)" in r.text
    r = tro_ly.tra_loi("so sánh khối 6 và khối 10", c)
    assert r.table["Khối"].tolist() == ["6", "10"] and r.table["Liên hệ"].tolist() == [1, 2]
