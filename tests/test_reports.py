"""Mọi mẫu báo cáo chạy được trên dữ liệu mẫu và dữ liệu rỗng, xuất được Excel."""
import io
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import reports, services  # noqa: E402
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH  # noqa: E402

TS = [
    {"id": "1", "NamHoc": "2026-2027", "HoTenHS": "An", "Khoi": "10", "TrangThai": "Nhập học",
     "Nguon": "Hotline", "NgayLienHe": "2026-06-01", "CheDo": "Nội trú", "PhanHe": "IEP",
     "GiuCho": "Đã giữ chỗ", "SoTienXacNhan": 2000000, "TruongCu": "THCS A",
     "TruongCu_Tinh": "Tây Ninh", "NguoiNhanHoSo": "Cô Lan", "TinhTrang": "Nhập học"},
    {"id": "2", "NamHoc": "2026-2027", "HoTenHS": "Bình", "Khoi": "6", "TrangThai": "Tư vấn",
     "Nguon": "", "NgayLienHe": "2026-01-10", "CheDo": "Bán trú"},
    {"id": "3", "NamHoc": "2025-2026", "HoTenHS": "Cúc", "Khoi": "7", "TrangThai": "Rút hồ sơ",
     "NgayLienHe": "2025-05-01", "GiuCho": "Hủy giữ chỗ", "SoTienXacNhan": 1000000},
]
NH = [
    {"id": "9", "NamHoc": "2026-2027", "HoTen": "An", "Khoi": "10", "PhanHe": "IEP",
     "LopHoc": "10A1", "GioiTinh": "Nam", "NoiTruBanTru": "Nội trú", "DangKyXe": "Vũng Tàu",
     "DiemDonTra": "Chợ", "LuaChon1": "Lý-Hóa-Địa-Tin học", "HocLuc1": "Giỏi", "Toan1": 9,
     "SoTienThanhToan": 10000000, "TongDaThu": 4000000, "SoTienConLai": 6000000,
     "HoSoDaNop": "Ngày đã nộp 01/07/2026\nGiấy khai sinh - Bản sao",
     "ChoO_Tinh": "Thành phố Hồ Chí Minh", "ChoO_Xa": "Phường Tân Phú",
     "TinhTrangHS": "Đang đóng phí"},
    {"id": "10", "NamHoc": "2026-2027", "HoTen": "Dũng", "Khoi": "7", "LopHoc": "",
     "GioiTinh": "Nữ", "NoiTruBanTru": "Bán trú", "TinhTrangHS": "Đang nhập hồ sơ"},
]


def _ctx(ts, nh):
    ts_all = services.to_df(TUYEN_SINH, ts)
    return reports.Ctx(ts=ts_all[ts_all["NamHoc"] == "2026-2027"].reset_index(drop=True),
                       nh=services.to_df(NHAP_HOC, nh), ts_all=ts_all, nam_hoc="2026-2027",
                       params={"ky": "Tháng", "top": 10, "ngay": 14})


def test_moi_bao_cao_chay_va_xuat_excel():
    for ctx in (_ctx(TS, NH), _ctx([], [])):
        items = []
        for rep in reports.REPORTS:
            res = rep.fn(ctx)
            assert isinstance(res.table, pd.DataFrame), rep.id
            items += reports.export_items(rep, res)
        wb = load_workbook(io.BytesIO(reports.excel(items, "Trường Tân Phú", "2026-2027")))
        assert len(wb.sheetnames) >= len(reports.REPORTS)


def test_so_lieu():
    ctx = _ctx(TS, NH)
    t = reports.ts_khoi(ctx).table
    tong = t[t["Khối"] == "Tổng cộng"].iloc[0]
    assert tong["Tổng"] == 2 and tong["Nhập học"] == 1 and tong["Tỷ lệ nhập học (%)"] == 50.0
    assert reports.kt_congno(ctx).table["Còn lại (đ)"].tolist() == [6000000]
    assert reports.nh_xe(ctx).kpis[0] == ("HS đăng ký xe", 1)
    siso = reports.nh_siso(ctx).table
    assert siso[siso["Lớp"] == "10A1"]["Sĩ số"].tolist() == [1]
    assert len(reports.ts_sosanh(ctx).table) == 2
