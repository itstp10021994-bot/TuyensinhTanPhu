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
