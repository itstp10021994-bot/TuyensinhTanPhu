"""Phân hệ nội trú: phòng, quyền nhập, lưu đánh giá theo học sinh-tháng, báo cáo."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import noi_tru as NT  # noqa: E402
from tuyensinh.schema import NOI_TRU_DANH_GIA, NOI_TRU_PHONG  # noqa: E402
from tuyensinh.storage.local import LocalStorage  # noqa: E402

NAM = "2026-2027"
GV1 = {"id": "11", "HoTen": "Cô Hoa", "VaiTro": "GV quản nhiệm"}
GV2 = {"id": "12", "HoTen": "Thầy Nam", "VaiTro": "GV quản nhiệm"}
TT = {"id": "13", "HoTen": "Cô Tổ trưởng", "VaiTro": "Tổ trưởng quản nhiệm"}


@pytest.fixture
def st_(tmp_path):
    return LocalStorage(tmp_path / "nt.sqlite3")


def test_phong_va_quyen(st_):
    p1 = NT.luu_phong(st_, [], NAM, "P101", "Nam", GV1, ["1", "2"])
    phongs = st_.list_items(NOI_TRU_PHONG.name)
    with pytest.raises(ValueError, match="đã có"):
        NT.luu_phong(st_, phongs, NAM, "p101", "", GV2, [])
    with pytest.raises(ValueError, match="phòng khác"):
        NT.luu_phong(st_, phongs, NAM, "P102", "", GV2, ["2", "3"])
    p2 = NT.luu_phong(st_, phongs, NAM, "P102", "", GV2, ["3"])
    assert NT.hs_ids(p1) == ["1", "2"]
    # GV chỉ nhập phòng mình; tổ trưởng / quản trị nhập mọi phòng
    assert NT.duoc_nhap(p1, GV1) and not NT.duoc_nhap(p1, GV2)
    assert NT.duoc_nhap(p1, TT) and NT.duoc_nhap(p2, {"id": "", "VaiTro": "Quản trị"})
    assert NT.duoc_nhap(p2, GV2)
    assert NT.la_quan_ly(TT) and not NT.la_quan_ly(GV1) and NT.la_quan_ly(None)


def test_thang_cua_nam_va_doc_thang():
    ds = NT.thang_cua_nam(NAM)
    assert ds[0] == "2026-08" and ds[-1] == "2027-07" and len(ds) == 12
    assert NT.thang_mac_dinh(NAM, date(2026, 11, 3)) == "2026-11"
    assert NT.thang_mac_dinh(NAM, date(2028, 1, 1)) == "2027-07"
    assert NT.thang_mac_dinh(NAM, date(2025, 1, 1)) == "2026-08"
    assert NT.ten_thang("2026-10") == "Tháng 10/2026"
    for v in ("10/2026", "Tháng 10/2026", "2026-10", "15/10/2026", date(2026, 10, 5),
              "2026-10-01 00:00:00"):
        assert NT.chuan_thang(v) == "2026-10", v
    assert NT.chuan_thang("13/2026") == "" and NT.chuan_thang("") == ""


def test_luu_danh_gia_thang_ghi_de_va_bao_cao(st_):
    p = NT.luu_phong(st_, [], NAM, "P101", "", GV1, ["1", "2", "3"])
    an, binh = {"id": "1", "ten": "An", "lop": "6A1"}, {"id": "2", "ten": "Bình", "lop": "6A1"}
    NT.luu_danh_gia_thang(st_, [], NAM, "2026-10", an, p,
                          {"NeNep": "Tốt", "HocTap": "Chưa tốt",
                           "HocTap_NX": "Chưa thuộc bài", "SucKhoe": "Khá",
                           "DiemSang": "Giúp bạn dọn phòng", "DinhHuong": "Nhắc giờ ngủ"},
                          "Cô Hoa")
    NT.luu_danh_gia_thang(st_, st_.list_items(NOI_TRU_DANH_GIA.name), NAM, "2026-10", binh, p,
                          {}, "Cô Hoa")  # để trống = Tốt
    dg = st_.list_items(NOI_TRU_DANH_GIA.name)
    assert len(dg) == 2
    r = NT.tim_danh_gia(dg, "1", "2026-10", NAM)
    assert r["HocTap"] == "Chưa tốt" and r["Phong"] == "P101" and NT.can_chu_y(r)
    assert r["NgayDanhGia"][:10] == date.today().isoformat()
    # lưu lại cùng em, cùng tháng -> ghi đè, không tạo bản ghi mới
    NT.luu_danh_gia_thang(st_, dg, NAM, "2026-10", an, p,
                          {"HocTap": "Khá", "HocTap_NX": "Đã tiến bộ"}, "Cô Hoa")
    NT.luu_danh_gia_thang(st_, st_.list_items(NOI_TRU_DANH_GIA.name), NAM, "2026-09", an, p,
                          {"NeNep": "Trung bình"}, "Cô Hoa")
    dg = st_.list_items(NOI_TRU_DANH_GIA.name)
    assert len(dg) == 3
    long = NT.bang_thang(dg, NAM)
    an10 = long[(long["Tháng"] == "2026-10") & (long["Học sinh"] == "An")].iloc[0]
    assert an10["Học tập"] == "Khá" and an10["Nhận xét học tập"] == "Đã tiến bộ"
    assert an10["Điểm sáng trong tháng"] == ""  # ghi đè cả bản ghi theo cửa sổ đánh giá
    with pytest.raises(ValueError, match="không hợp lệ"):
        NT.luu_danh_gia_thang(st_, dg, NAM, "2026-10", an, p, {"NeNep": "Xuất sắc"}, "x")
    with pytest.raises(ValueError, match="quá dài"):
        NT.luu_danh_gia_thang(st_, dg, NAM, "2026-10", an, p,
                              {"DiemSang": "x" * (NT.MAX_LOI + 1)}, "x")
    with pytest.raises(ValueError, match="không thuộc năm học"):
        NT.luu_danh_gia_thang(st_, dg, NAM, "2027-09", an, p, {}, "x")

    x = long[long["Tháng"] == "2026-10"]
    th = NT.tong_hop_phong(x, [p], {"1", "2", "3"}).iloc[0]
    assert th["Số HS"] == 3 and th["Đã đánh giá"] == 2 and th["Chưa đánh giá"] == 1
    assert th["Hoàn thành (%)"] == 66.7 and th["Học tập Tốt (%)"] == 50.0
    assert th["Em cần chú ý"] == 0
    assert NT._ty_le_tot(long.iloc[0:0]["Nề nếp"]) is None  # chưa đánh giá: "—", không phải 0%
    cc = NT.hoc_sinh_can_chu_y(long)
    assert cc["Học sinh"].tolist() == ["An"] and cc.iloc[0]["Tháng"] == "Tháng 9/2026"
    assert len(NT.nhan_xet(x)) == 1
    xh = NT.xu_huong(long, NT.thang_cua_nam(NAM))
    assert xh["Tháng"].unique().tolist() == ["9/2026", "10/2026"]
    assert xh[(xh["Tháng"] == "9/2026") & (xh["Mục"] == "Nề nếp")].iloc[0]["Tỷ lệ Tốt (%)"] == 0
    pb = NT.phan_bo_muc(x)
    assert pb[(pb["Mục"] == "Học tập") & (pb["Mức"] == "Khá")].iloc[0]["Số HS"] == 1
    # đánh giá nhanh: chỉ em chưa có đánh giá tháng đó
    n = NT.danh_gia_nhanh(st_, dg, NAM, "2026-10",
                          [(an, p), (binh, p), ({"id": "3", "ten": "Chi"}, p)], "Cô Hoa")
    assert n == 1
    dg = st_.list_items(NOI_TRU_DANH_GIA.name)
    assert NT.tim_danh_gia(dg, "3", "2026-10")["NeNep"] == "Tốt"
    assert NT.tim_danh_gia(dg, "1", "2026-10")["HocTap"] == "Khá"


def test_nhap_phan_phong_tu_excel(st_, tmp_path):
    """File kiểu "DSHS" của Tổ quản nhiệm: ghép theo tên (+lớp/giới tính khi trùng tên),
    đổi sang Nội trú, tạo phòng; chạy lại cập nhật phòng, không tạo trùng."""
    from openpyxl import Workbook

    from tuyensinh.schema import NHAP_HOC

    wb = Workbook()
    ws = wb.active
    ws.title = "DSHS"
    ws.append(["TRƯỜNG …"])
    ws.append(["DANH SÁCH HSNT"])
    ws.append(["STT", "Họ và tên", "Lớp", "Giới tính", "Phòng \nNT", "QN\n quản lý"])
    ws.append([1, "Trần  An", 6.2, "Nam", 508, "Cô Hoa"])
    ws.append([2, "Lê Bình", "10A1ESL", "Nữ", 507, "Thầy Nam"])
    ws.append([3, "Phạm Chi", "6,1ESL", "Nữ", 507, "Thầy Nam"])     # trùng tên: chọn theo lớp
    ws.append([4, "Võ Dũng", 7.1, "Nam", 508, "Cô Hoa"])           # chưa có hồ sơ
    ws.append([5, "Bùi Em", 9.1, "Nam", None, None])               # không có phòng: bỏ qua
    f = tmp_path / "ds.xlsx"
    wb.save(f)
    for d in ({"HoTen": "Trần An", "Khoi": "6", "LopHoc": "6.2", "NoiTruBanTru": "Bán trú"},
              {"HoTen": "Lê Bình", "Khoi": "10", "LopHoc": "10A1E", "NoiTruBanTru": "Nội trú"},
              {"HoTen": "Phạm Chi", "Khoi": "6", "LopHoc": "6.1E", "GioiTinh": "Nữ"},
              {"HoTen": "Phạm Chi", "Khoi": "8", "LopHoc": "8.2", "GioiTinh": "Nữ"}):
        st_.create_item(NHAP_HOC.name, dict(d, NamHoc=NAM, TinhTrangHS="Học tiếp"))
    assert NT.sheet_phong(f) == ["DSHS"]
    ds, sheet = NT.doc_ds_phong(f)
    assert len(ds) == 4 and ds.iloc[0]["Họ tên"] == "Trần An" and ds.iloc[2]["Lớp"] == "6.1"
    nh = st_.list_items(NHAP_HOC.name)
    g = NT.ghep_hs(ds, nh, NAM)
    assert g["Kết quả"].tolist() == [NT.TT_KHOP, NT.TT_KHOP, NT.TT_KHOP, NT.TT_KHONG_THAY]
    chi = next(r for r in nh if r["HoTen"] == "Phạm Chi" and r["Khoi"] == "6")
    assert g.iloc[2]["HocSinhID"] == str(chi["id"])
    kh = NT.ke_hoach_phong(g, [GV1])
    assert [(k["TenPhong"], k["GiaoVien"], len(k["HocSinhIDs"])) for k in kh] == \
        [("507", "Thầy Nam", 2), ("508", "Cô Hoa", 1)]
    assert kh[1]["TaiKhoan"] == GV1 and kh[0]["TaiKhoan"] is None
    kq = NT.ap_dung_phan_phong(st_, [], NAM, g, kh, NHAP_HOC.name)
    assert kq["doi_che_do"] == 2  # Trần An (Bán trú) + Phạm Chi (trống)
    nh = {r["HoTen"] + r["Khoi"]: r for r in st_.list_items(NHAP_HOC.name)}
    assert nh["Trần An6"]["NoiTruBanTru"] == "Nội trú" and nh["Phạm Chi8"].get("NoiTruBanTru") in (None, "")
    phongs = st_.list_items(NOI_TRU_PHONG.name)
    assert sorted(p["TenPhong"] for p in phongs) == ["507", "508"]
    p507 = next(p for p in phongs if p["TenPhong"] == "507")
    # GV chưa có tài khoản: ghi tên, tự khớp khi đăng nhập bằng tài khoản cùng họ tên
    assert p507["GiaoVienID"] == "" and NT.duoc_nhap(p507, {"id": "99", "HoTen": "thầy nam",
                                                             "VaiTro": "GV quản nhiệm"})
    NT.ap_dung_phan_phong(st_, phongs, NAM, g, kh, NHAP_HOC.name)  # chạy lại: không tạo trùng
    assert len(st_.list_items(NOI_TRU_PHONG.name)) == 2


def test_nhap_danh_gia_tu_file_mau(st_):
    """File mẫu đánh giá tháng: ghép học sinh theo tên (trong phòng hoặc mọi phòng)."""
    from tuyensinh import importer
    from tuyensinh.schema import NHAP_HOC
    from tests.test_importer import _dien

    a = st_.create_item(NHAP_HOC.name, {"HoTen": "Trần An", "LopHoc": "6.1", "NamHoc": NAM})
    b = st_.create_item(NHAP_HOC.name, {"HoTen": "Lê Bình", "LopHoc": "6.1", "NamHoc": NAM})
    p = NT.luu_phong(st_, [], NAM, "507", "", GV1, [str(a["id"]), str(b["id"])])
    NT.luu_danh_gia_thang(st_, [], NAM, "2026-10", {"id": str(b["id"]), "ten": "Lê Bình"}, p,
                          {"NeNep": "Khá", "DiemSang": "Chăm chỉ"}, "Cô Hoa")
    hdr_hoc = NT.TEN_MUC["HocTap"]
    buf, hdr = _dien(NOI_TRU_DANH_GIA, [
        {"Tháng": "10/2026", "Phòng": 507, "Học sinh": "trần an", hdr_hoc: "Chưa tốt",
         NT.TEN_NX["HocTap"]: "Chưa thuộc bài"},
        {"Tháng": "10/2026", "Học sinh": "Lê Bình", hdr_hoc: "Khá"},  # không ghi phòng
        {"Tháng": "10/2026", "Phòng": "999", "Học sinh": "Lê Bình"},
        {"Tháng": "10/2026", "Phòng": "507", "Học sinh": "Võ C"},
        {"Tháng": "10/2026", "Phòng": "507", "Học sinh": "Trần An", hdr_hoc: "Giỏi"},
        {"Tháng": "10/2027", "Phòng": "507", "Học sinh": "Trần An"}])
    assert "Người đánh giá" in hdr and "Tháng" in hdr
    df, skipped = importer.read_frame(buf, NOI_TRU_DANH_GIA)
    assert not skipped
    res = NT.nhap_danh_gia(st_, df, st_.list_items(NOI_TRU_PHONG.name),
                           st_.list_items(NOI_TRU_DANH_GIA.name), NAM,
                           st_.list_items(NHAP_HOC.name), "Admin")
    assert res["ok"] == 2 and [e["Dòng"] for e in res["errors"]] == [4, 5, 6, 7]
    long = NT.bang_thang(st_.list_items(NOI_TRU_DANH_GIA.name), NAM).set_index("Học sinh")
    assert len(long) == 2
    assert long.loc["Trần An", "Học tập"] == "Chưa tốt"
    assert long.loc["Trần An", "Người đánh giá"] == "Admin"
    assert long.loc["Trần An", "Phòng"] == "507"
    # em đã có đánh giá: cột có trong file ghi đè, ô trống giữ nội dung cũ
    assert long.loc["Lê Bình", "Học tập"] == "Khá" and long.loc["Lê Bình", "Nề nếp"] == "Khá"
    assert long.loc["Lê Bình", "Điểm sáng trong tháng"] == "Chăm chỉ"
    # file báo cáo (Tháng dạng "Tháng 10/2026") nhập lại được
    xuat = long.reset_index().drop(columns=["PhongID", "HocSinhID", "Ngày đánh giá"])
    xuat["Tháng"] = xuat["Tháng"].map(NT.ten_thang)
    import io
    bio = io.BytesIO()
    xuat.to_excel(bio, index=False, sheet_name=NOI_TRU_DANH_GIA.name)
    bio.seek(0)
    df2, skipped = importer.read_frame(bio, NOI_TRU_DANH_GIA)
    assert not skipped and len(df2) == 2
    res = NT.nhap_danh_gia(st_, df2, st_.list_items(NOI_TRU_PHONG.name),
                           st_.list_items(NOI_TRU_DANH_GIA.name), NAM,
                           st_.list_items(NHAP_HOC.name), "Admin")
    assert res["ok"] == 2 and not res["errors"]
    assert len(st_.list_items(NOI_TRU_DANH_GIA.name)) == 2


def test_mau_phan_phong_doc_duoc():
    from tests.test_importer import _dien
    buf, _ = _dien(NOI_TRU_PHONG, [{"Họ và tên": "Trần  An", "Lớp": "6.2", "Giới tính": "Nam",
                                    "Phòng NT": "508", "QN quản lý": "Cô Hoa"}])
    ds, sheet = NT.doc_ds_phong(buf)
    assert sheet == NOI_TRU_PHONG.name
    assert ds.iloc[0].tolist() == ["Trần An", "6.2", "Nam", "508", "Cô Hoa"]


def test_them_vao_phong(st_):
    p = NT.luu_phong(st_, [], NAM, "P1", "Nam", GV1, ["1"])
    NT.them_vao_phong(st_, st_.list_items(NOI_TRU_PHONG.name), NAM, p, "", ["2", "1"])
    p = st_.list_items(NOI_TRU_PHONG.name)[0]
    assert NT.hs_ids(p) == ["1", "2"] and p["GiaoVienID"] == "11" and p["Khu"] == "Nam"
    with pytest.raises(ValueError, match="phòng khác"):
        NT.them_vao_phong(st_, [p], NAM, None, "P2", ["2"])
    NT.them_vao_phong(st_, [p], NAM, None, "P2", ["3"])
    assert len(st_.list_items(NOI_TRU_PHONG.name)) == 2


def test_bo_khoi_phong(st_):
    NT.luu_phong(st_, [], NAM, "P1", "", GV1, ["1", "2"])
    NT.luu_phong(st_, st_.list_items(NOI_TRU_PHONG.name), NAM, "P2", "", GV1, ["3"])
    assert NT.bo_khoi_phong(st_, st_.list_items(NOI_TRU_PHONG.name), ["2", "9"]) == 1
    assert [NT.hs_ids(p) for p in st_.list_items(NOI_TRU_PHONG.name)] == [["1"], ["3"]]


def test_ghep_trung_ten_cung_lop_chon_em_noi_tru():
    import pandas as pd
    ds = pd.DataFrame([{"Họ tên": "Lê Văn A", "Lớp": "12C2", "Giới tính": "Nam", "Phòng": "404",
                        "Giáo viên": ""}])
    nh = [{"id": 1, "HoTen": "Lê Văn A", "LopHoc": "12C2", "GioiTinh": "Nam",
           "NoiTruBanTru": "Bán trú", "NamHoc": NAM},
          {"id": 2, "HoTen": "Lê Văn A", "LopHoc": "12C2", "GioiTinh": "Nam",
           "NoiTruBanTru": "Nội trú", "NamHoc": NAM}]
    g = NT.ghep_hs(ds, nh, NAM)
    assert g.iloc[0]["Kết quả"] == NT.TT_KHOP and g.iloc[0]["HocSinhID"] == "2"


def test_theo_ho_so_ten_lop_hien_tai_bo_hs_da_xoa(st_):
    from tuyensinh.schema import NHAP_HOC
    a = st_.create_item(NHAP_HOC.name, {"HoTen": "An", "Khoi": "6", "NamHoc": NAM})
    b = st_.create_item(NHAP_HOC.name, {"HoTen": "Bình", "Khoi": "9", "NamHoc": NAM})
    p = NT.luu_phong(st_, [], NAM, "308", "", GV1, [str(a["id"]), str(b["id"])])
    for h in ({"id": str(a["id"]), "ten": "An", "lop": "Khối 6"},
              {"id": str(b["id"]), "ten": "Bình", "lop": "Khối 9"}):
        NT.luu_danh_gia_thang(st_, [], NAM, "2026-10", h, p, {}, "x")
    st_.update_item(NHAP_HOC.name, a["id"], {"LopHoc": "6.2"})
    st_.delete_item(NHAP_HOC.name, b["id"])
    long = NT.theo_ho_so(NT.bang_thang(st_.list_items(NOI_TRU_DANH_GIA.name), NAM),
                         st_.list_items(NHAP_HOC.name))
    assert long[["Học sinh", "Lớp"]].values.tolist() == [["An", "6.2"]]


def test_chuyen_ban_tru(st_):
    from tuyensinh.schema import NHAP_HOC, TUYEN_SINH
    t = st_.create_item(TUYEN_SINH.name, {"HoTenHS": "An", "CheDo": "Nội trú", "NamHoc": NAM})
    a = st_.create_item(NHAP_HOC.name, {"HoTen": "An", "NoiTruBanTru": "Nội trú", "NamHoc": NAM,
                                        "TuyenSinhID": str(t["id"])})
    b = st_.create_item(NHAP_HOC.name, {"HoTen": "Bình", "NoiTruBanTru": "Nội trú", "NamHoc": NAM})
    c = st_.create_item(NHAP_HOC.name, {"HoTen": "Chi", "NoiTruBanTru": "Nội trú", "NamHoc": NAM})
    n = NT.chuyen_ban_tru(st_, st_.list_items(NHAP_HOC.name), st_.list_items(TUYEN_SINH.name),
                          [str(a["id"]), str(b["id"])])
    assert n == 2
    assert [st_.get_item(NHAP_HOC.name, x["id"])["NoiTruBanTru"] for x in (a, b, c)] == \
        ["Bán trú", "Bán trú", "Nội trú"]
    assert st_.get_item(TUYEN_SINH.name, t["id"])["CheDo"] == "Bán trú"
