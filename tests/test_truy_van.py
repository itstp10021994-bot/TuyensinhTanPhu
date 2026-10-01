"""Ý định có cấu trúc (từ Gemini): kết hợp nhiều bộ lọc cùng lúc."""
from datetime import date

import pandas as pd

from tuyensinh import ai_gemini, tro_ly, truy_van

TS = pd.DataFrame([
    {"id": "1", "NamHoc": "2026-2027", "HoTenHS": "Trần Thị An", "Khoi": "10", "PhanHe": "IEP",
     "TrangThai": "Nhập học", "CheDo": "Nội trú", "GioiTinh": "Nữ", "Nguon": "Hotline",
     "TruongCu_Tinh": "Tỉnh Tây Ninh", "TruongCu": "THCS Phước Thái", "NgayLienHe": "2026-04-05"},
    {"id": "2", "NamHoc": "2026-2027", "HoTenHS": "Lê Văn Bình", "Khoi": "11", "PhanHe": "ESL",
     "TrangThai": "Nhập học", "CheDo": "Nội trú", "GioiTinh": "Nam", "Nguon": "Mạng xã hội",
     "TruongCu_Tinh": "Thành phố Đồng Nai", "TruongCu": "THCS Xuân Diệu", "NgayLienHe": "2026-05-10"},
    {"id": "3", "NamHoc": "2026-2027", "HoTenHS": "Phạm Thu An", "Khoi": "11", "PhanHe": "IEP",
     "TrangThai": "Tư vấn", "CheDo": "Bán trú", "GioiTinh": "Nữ", "Nguon": "Hotline",
     "TruongCu_Tinh": "Thành phố Đồng Nai", "TruongCu": "THCS Xuân Diệu", "NgayLienHe": "2026-06-20"},
    {"id": "4", "NamHoc": "2025-2026", "HoTenHS": "Võ Minh", "Khoi": "10", "PhanHe": "IEP",
     "TrangThai": "Nhập học", "CheDo": "Nội trú", "GioiTinh": "Nam", "Nguon": "Hotline",
     "TruongCu_Tinh": "Tỉnh Tây Ninh", "NgayLienHe": "2025-04-07"},
])
C = tro_ly.Ctx(TS[TS.NamHoc == "2026-2027"], pd.DataFrame(), "2026-2027",
               hom_nay=date(2026, 7, 1), ts_all=TS)


def test_nhieu_bo_loc_cung_luc():
    r = truy_van.thuc_hien({"loai": "dem", "doi_tuong": "nhap_hoc", "khoi": ["10", "11"],
                            "che_do": ["Nội trú"], "tinh": ["Tây Ninh", "Đồng Nai"]}, C)
    assert "**2** học sinh nhập học" in r.text
    r = truy_van.thuc_hien({"loai": "dem", "gioi_tinh": "Nữ", "nguon": ["Hotline"],
                            "tu_ngay": "2026-04-01", "den_ngay": "2026-04-30"}, C)
    assert "**1** liên hệ" in r.text and "từ 01/04/2026 đến 30/04/2026" in r.text
    r = truy_van.thuc_hien({"loai": "danh_sach", "ten": "An", "khoi": ["11"]}, C)
    assert r.table["Học sinh"].tolist() == ["Phạm Thu An"]
    r = truy_van.thuc_hien({"loai": "dem", "khoi": ["11-IEP"]}, C)
    assert "**1** liên hệ" in r.text


def test_xep_hang_ty_le_va_so_sanh_nam():
    r = truy_van.thuc_hien({"loai": "xep_hang", "theo": "truong_cu", "top": 1}, C)
    assert "**THCS Xuân Diệu** với **2**" in r.text and len(r.table) == 1
    r = truy_van.thuc_hien({"loai": "ty_le", "theo": "nguon"}, C)
    assert "**66,7%** (2/3 liên hệ)" in r.text
    r = truy_van.thuc_hien({"loai": "dem", "doi_tuong": "nhap_hoc", "tinh": ["Tây Ninh"],
                            "so_sanh_nam": True}, C)
    assert "2025-2026: **1** → 2026-2027: **1**" in r.text
    # cùng kỳ: tháng 4/2026 so với tháng 4/2025
    r = truy_van.thuc_hien({"loai": "dem", "tu_ngay": "2026-04-01", "den_ngay": "2026-04-30",
                            "so_sanh_nam": True}, C)
    assert "2025-2026: **1** → 2026-2027: **1**" in r.text


def test_tra_loi_dung_y_dinh_cua_ai():
    def ai(cau, truoc):
        return ai_gemini.KetQua("Bao nhiêu học sinh nữ nhập học khối 10 từ Tây Ninh?",
                                mo_hinh="gemini-x", y_dinh={
                                    "loai": "dem", "doi_tuong": "nhap_hoc", "khoi": ["10"],
                                    "gioi_tinh": "Nữ", "tinh": ["Tây Ninh"]})
    r = tro_ly.tra_loi("mấy bé gái lớp mười ở tây ninh vô học rồi", C, ai=ai)
    assert "**1** học sinh nhập học" in r.text and r.ai_mo_hinh == "gemini-x"
    # ý định lỗi -> quay về câu viết lại
    def ai_loi(cau, truoc):
        return ai_gemini.KetQua("bao nhiêu liên hệ", y_dinh={"loai": "dem", "khoi": 5})
    assert "liên hệ" in tro_ly.tra_loi("x", C, ai=ai_loi).text
