"""Phân hệ nội trú: phòng, quyền nhập, lưu đánh giá theo phòng-ngày, báo cáo."""
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


def test_luu_danh_gia_ghi_de_va_bao_cao(st_):
    p = NT.luu_phong(st_, [], NAM, "P101", "", GV1, ["1", "2"])
    ngay = date(2026, 10, 19)  # thứ Hai
    dong = [{"id": "1", "ten": "An", "lop": "6A1", "NeNep": "Tốt", "HocTap": "Chưa tốt",
             "HocTap_NX": "Ngủ gật khi học bài", "SucKhoe": "Khá",
             "DiemSang": "Giúp bạn dọn phòng", "DinhHuong": "Nhắc giờ ngủ"},
            {"id": "2", "ten": "Bình", "lop": "6A1"}]  # để trống = Tốt
    NT.luu_danh_gia(st_, [], NAM, ngay, p, dong, "Cô Hoa")
    dg = st_.list_items(NOI_TRU_DANH_GIA.name)
    assert len(dg) == 1 and dg[0]["SoChuaTot"] == 1
    # lưu lại cùng phòng, cùng ngày -> ghi đè, không tạo bản ghi mới
    dong[0]["HocTap"] = "Khá"
    NT.luu_danh_gia(st_, dg, NAM, ngay, p, dong, "Cô Hoa")
    NT.luu_danh_gia(st_, st_.list_items(NOI_TRU_DANH_GIA.name), NAM, date(2026, 10, 20), p,
                    [dict(dong[0], NeNep="Trung bình", HocTap="Chưa tốt"), dong[1]], "Cô Hoa")
    dg = st_.list_items(NOI_TRU_DANH_GIA.name)
    assert len(dg) == 2
    long = NT.bang_dai(dg, NAM)
    assert len(long) == 4
    an = long[(long["Ngày"] == ngay) & (long["Học sinh"] == "An")].iloc[0]
    assert an["Học tập"] == "Khá" and an["Sức khỏe - Tâm lý"] == "Khá"
    assert an["Điểm sáng trong tháng"] == "Giúp bạn dọn phòng"
    assert an["Nhận xét học tập"] == "Ngủ gật khi học bài"
    with pytest.raises(ValueError, match="không hợp lệ"):
        NT.luu_danh_gia(st_, dg, NAM, ngay, p, [{"id": "1", "NeNep": "Xuất sắc"}], "x")
    with pytest.raises(ValueError, match="quá dài"):
        NT.luu_danh_gia(st_, dg, NAM, ngay, p, [{"id": "1", "DiemSang": "x" * 301}], "x")

    ngays = NT.ngay_trong_khoang(date(2026, 10, 19), date(2026, 10, 25), [0, 1, 2, 3, 4])
    assert len(ngays) == 5
    th = NT.tong_hop_phong(long, [p], ngays).iloc[0]
    assert th["Ngày đã nhập"] == 2 and th["Ngày chưa nhập"] == 3
    assert th["Nề nếp Tốt (%)"] == 75.0 and th["Lượt học tập TB/CT"] == 1
    assert NT._ty_le_tot(long.iloc[0:0]["Nề nếp"]) is None  # chưa đánh giá: "—", không phải 0%
    cc = NT.hoc_sinh_can_chu_y(long, 2)
    assert cc["Học sinh"].tolist() == ["An"] and cc.iloc[0]["Tổng lượt"] == 2
    assert cc.iloc[0]["Nhận xét gần nhất"] == "Ngủ gật khi học bài"
    assert len(NT.nhan_xet(long)) == 2  # 2 ngày của An có lời nhận xét
    assert set(NT.theo_ngay(long)["Mục"]) == set(NT.COT_MUC)
    tn = NT.tinh_hinh_nhap(long, [p], ngays[:3])
    assert tn.iloc[0][["19/10", "20/10", "21/10"]].tolist() == ["✓", "✓", "✗"]


def test_doc_du_lieu_cu_hai_muc():
    """Bản ghi cũ (Nề nếp + Học bài tối + Ghi chú) vẫn hiện đúng ở mục Học tập."""
    import json
    r = {"NamHoc": NAM, "Ngay": "2026-10-01", "PhongID": "1", "Phong": "P1",
         "DuLieu": json.dumps([{"id": "1", "ten": "An", "NeNep": "Khá", "HocBaiToi": "Chưa tốt",
                                "GhiChu": "Ồn ào"}])}
    row = NT.bang_dai([r], NAM).iloc[0]
    assert row["Nề nếp"] == "Khá" and row["Học tập"] == "Chưa tốt"
    assert row["Nhận xét nề nếp"] == "Ồn ào" and row["Sức khỏe - Tâm lý"] == ""


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
    """File mẫu đánh giá: ghép học sinh trong phòng theo tên, gộp với đánh giá đã có."""
    from tuyensinh import importer
    from tuyensinh.schema import NHAP_HOC
    from tests.test_importer import _dien

    a = st_.create_item(NHAP_HOC.name, {"HoTen": "Trần An", "LopHoc": "6.1", "NamHoc": NAM})
    b = st_.create_item(NHAP_HOC.name, {"HoTen": "Lê Bình", "LopHoc": "6.1", "NamHoc": NAM})
    p = NT.luu_phong(st_, [], NAM, "507", "", GV1, [str(a["id"]), str(b["id"])])
    ngay = date(2026, 10, 19)
    NT.luu_danh_gia(st_, [], NAM, ngay, p, [{"id": str(a["id"]), "ten": "Trần An"},
                                            {"id": str(b["id"]), "ten": "Lê Bình",
                                             "NeNep": "Khá"}], "Cô Hoa")
    hdr_ngay, hdr_hoc = "Ngày", NT.TEN_MUC["HocTap"]
    buf, hdr = _dien(NOI_TRU_DANH_GIA, [
        {hdr_ngay: "19/10/2026", "Phòng": 507, "Học sinh": "trần an", hdr_hoc: "Chưa tốt",
         NT.TEN_NX["HocTap"]: "Chưa thuộc bài"},
        {hdr_ngay: "20/10/2026", "Phòng": "507", "Học sinh": "Lê Bình"},
        {hdr_ngay: "20/10/2026", "Phòng": "999", "Học sinh": "Lê Bình"},
        {hdr_ngay: "20/10/2026", "Phòng": "507", "Học sinh": "Võ C"},
        {hdr_ngay: "20/10/2026", "Phòng": "507", "Học sinh": "Trần An", hdr_hoc: "Giỏi"}])
    assert "Người đánh giá" in hdr
    df, skipped = importer.read_frame(buf, NOI_TRU_DANH_GIA)
    assert not skipped
    res = NT.nhap_danh_gia(st_, df, st_.list_items(NOI_TRU_PHONG.name),
                           st_.list_items(NOI_TRU_DANH_GIA.name), NAM,
                           st_.list_items(NHAP_HOC.name), "Admin")
    assert res["ok"] == 2 and res["ban_ghi"] == 2 and [e["Dòng"] for e in res["errors"]] == [4, 5, 6]
    long = NT.bang_dai(st_.list_items(NOI_TRU_DANH_GIA.name), NAM)
    ngay1 = long[long["Ngày"] == ngay].set_index("Học sinh")
    assert ngay1.loc["Trần An", "Học tập"] == "Chưa tốt"
    assert ngay1.loc["Lê Bình", "Nề nếp"] == "Khá"  # em không có trong file: giữ nguyên
    assert ngay1.loc["Trần An", "Người đánh giá"] == "Cô Hoa"
    assert len(long) == 3
    # file tải từ trang Nội trú (Xem → Tải Excel) nhập lại được
    xuat = long.drop(columns=["PhongID", "HocSinhID"])
    import io
    bio = io.BytesIO()
    xuat.to_excel(bio, index=False, sheet_name=NOI_TRU_DANH_GIA.name)
    bio.seek(0)
    df2, skipped = importer.read_frame(bio, NOI_TRU_DANH_GIA)
    assert not skipped and len(df2) == 3


def test_mau_phan_phong_doc_duoc():
    from tests.test_importer import _dien
    buf, _ = _dien(NOI_TRU_PHONG, [{"Họ và tên": "Trần  An", "Lớp": "6.2", "Giới tính": "Nam",
                                    "Phòng NT": "508", "QN quản lý": "Cô Hoa"}])
    ds, sheet = NT.doc_ds_phong(buf)
    assert sheet == NOI_TRU_PHONG.name
    assert ds.iloc[0].tolist() == ["Trần An", "6.2", "Nam", "508", "Cô Hoa"]
